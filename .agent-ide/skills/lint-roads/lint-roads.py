#!/usr/bin/env python3
"""Roadmark lint: the ten checks of execution-loop.md §3.15.

Usage:
    lint-roads <assemble-dir>                 # check only; every defect on its own line
    lint-roads <assemble-dir> --queue         # the work queue (id / kind / what / owner / blocks / since)
    lint-roads <assemble-dir> --queue --md    # same queue as a markdown table

Exit code: 0 clean, 1 defects.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

HEADER_KEYS = ("SECTION", "CLAIM", "NEEDS", "HANDS", "STATUS")
SIGN_KINDS = ("PENDING", "DECIDE", "ABSENT")
ID_RE = re.compile(r"^(run|read|decide|absent)-[a-z0-9]+(-[a-z0-9]+)*$")
SIGN_RE = re.compile(r"^%\s*(PENDING|DECIDE|ABSENT)\(([^)]+)\):\s*(.*)$")


def section_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(list(root.glob("2.*.draft.tex")) + list(root.glob("5.*.draft.tex")))


def thesis_sections(root: pathlib.Path) -> set[str]:
    """立意里存在的小节号，如 2.5、3.4；找不到立意就返回空集（不因此判失败）。"""
    candidates = [
        root.parent.parent.parent / "workspace" / "毕设立意.md",
        root.parent.parent.parent / "workspace" / "thesis-positioning.md",
        root / "毕设立意.md",
    ]
    for c in candidates:
        if c.exists():
            text = c.read_text(encoding="utf-8")
            ids = set(re.findall(r"^\*\*(\d+\.\d+)\s", text, re.M))
            ids |= set(re.findall(r"^## 第 (\d+) 章", text, re.M))
            return ids
    return set()


def parse_signs(text: str) -> list[dict]:
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = SIGN_RE.match(line.strip())
        if not m:
            continue
        kind, ident, rest = m.groups()
        fields = [f.strip() for f in rest.split("|")]
        out.append({"line": lineno, "kind": kind, "id": ident, "fields": fields, "raw": line})
    return out


def check(root: pathlib.Path) -> tuple[list[str], list[dict]]:
    defects: list[str] = []
    queue: list[dict] = []
    exists = thesis_sections(root)
    seen_ids: dict[str, str] = {}
    hand_targets: set[str] = set()
    files = section_files(root)

    for f in files:
        name = f.name
        lines = f.read_text(encoding="utf-8").splitlines()
        # 1) 头五行，键名与顺序
        head = lines[:5]
        keys = [re.match(r"^%\s*([A-Z]+):", h).group(1) if re.match(r"^%\s*([A-Z]+):", h) else None for h in head]
        if tuple(keys) != HEADER_KEYS:
            defects.append(f"{name}: 头部五个键不符（得到 {keys}，应为 {list(HEADER_KEYS)}）")
        text = "\n".join(lines)

        # 2) SECTION 指的立意小节存在
        m = re.search(r"^%\s*SECTION:\s*\d+\s*<-\s*thesis\s*(§[\d.]+(?:-§[\d.]+)?)", text, re.M)
        if not m:
            defects.append(f"{name}: SECTION 行缺少 `<- thesis §x.y`")
        elif exists:
            raw = m.group(1).replace("§", "")
            lo, _, hi = raw.partition("-")
            ids = [lo] if not hi else [lo, hi]
            for sid in ids:
                if sid not in exists:
                    defects.append(f"{name}: SECTION 指向不存在的立意小节 §{sid}")

        # 3) HANDS 指向存在的节（同文件 \section 或 §号）
        sec_nums = set(re.findall(r"\\section\{", text))
        for h in re.findall(r"^%\s*HANDS:.*?->\s*(§[\d.]+)", text, re.M):
            hand_targets.add(h.replace("§", ""))

        signs = parse_signs(text)
        # 4/5/6/7 逐条占位符
        for s in signs:
            if not ID_RE.match(s["id"]):
                defects.append(f"{name}:{s['line']} id 不合命名空间：{s['id']}")
            if s["id"] in seen_ids and seen_ids[s["id"]] != name:
                defects.append(f"{name}:{s['line']} id 重复出现（已在 {seen_ids[s['id']]}）：{s['id']}")
            seen_ids.setdefault(s["id"], name)
            if len(s["fields"]) != 4:
                defects.append(f"{name}:{s['line']} 字段数 {len(s['fields'])}，应为 4（what | owner | blocks | since）")
                continue
            what, owner, blocks, since = s["fields"]
            if re.search(r"\d", what):
                defects.append(f"{name}:{s['line']} what 字段含数字，疑似编造读数：{what}")
            if not re.match(r"^owner:\s*\S", owner):
                defects.append(f"{name}:{s['line']} 缺 owner 字段")
            if not re.match(r"^blocks:\s*§[\d.]+", blocks):
                defects.append(f"{name}:{s['line']} blocks 未指向任何 §")
            if not re.match(r"^since:\s*\d{4}-\d{2}-\d{2}$", since):
                defects.append(f"{name}:{s['line']} since 不是 YYYY-MM-DD")
            queue.append({"file": name, "kind": s["kind"], "id": s["id"],
                          "what": what, "owner": owner.replace("owner:", "").strip(),
                          "blocks": blocks.replace("blocks:", "").strip(),
                          "since": since.replace("since:", "").strip()})

        # 8) STATUS: blocked(x) ⇒ 该 id 在文件里
        mb = re.search(r"^%\s*STATUS:\s*blocked\(([^)]+)\)", text, re.M)
        ids_here = {s["id"] for s in signs}
        if mb and mb.group(1) not in ids_here:
            defects.append(f"{name}: STATUS blocked({mb.group(1)}) 但该占位符不在本文件")

        # 9) 裸 `--` 单元格不多于占位符数
        bare = len(re.findall(r"&\s*--\s*(?=&|\\\\)", text))
        if bare > len(signs):
            defects.append(f"{name}: 表格里有 {bare} 个 `--`，但只有 {len(signs)} 个占位符")

        # 10) 正文可见标记 [pending: id] 必须有同名 sign
        for mid in re.findall(r"\\emph\{\[pending: ([^\]]+)\]\}", text):
            if mid.strip() not in ids_here:
                defects.append(f"{name}: 正文标记 [pending: {mid.strip()}] 没有对应占位符")

    # 3b) HANDS 目标必须是本稿已有的节号（只警告，不失败）
    return defects, queue


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="report/final/assemble",
                    help="directory holding the 2.x draft files")
    ap.add_argument("--queue", action="store_true")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    defects, queue = check(root)
    if a.queue:
        if a.md:
            print("| id | 类型 | 待填 | 主人 | 阻塞 | 起始 |")
            print("|---|---|---|---|---|---|")
            for q in queue:
                print(f"| `{q['id']}` | {q['kind']} | {q['what']} | {q['owner']} | {q['blocks']} | {q['since']} |")
        else:
            for q in queue:
                print("\t".join([q["id"], q["kind"], q["what"], q["owner"], q["blocks"], q["since"]]))
    for d in defects:
        print("FAIL", d)
    print(f"files={len(section_files(root))} · signs={len(queue)} · defects={len(defects)}")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
