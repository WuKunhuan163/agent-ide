#!/usr/bin/env python3
"""indicator 目录与队列的结构自检（标准化用，不是文风检查）。

用法：
    python3 workspace/indicator/check.py prelim-report

检查十二项，任何一项不过就以退出码 1 结束：
  1 目录齐备：README.md / supervisor-prompt.md / LOOP_STATE.md / units/ / returns/
  2 LOOP_STATE 有两节 ## ON-RAMP 与 ## EXCLUDED，且有 `ON-RAMP LEFT: n`
  3 每个 units/#n-*.md 头四行是 id/unit/title/depends（YAML 风格），且有 `paves:` 与「合格线」
  4 编号三处一致：units 的 #n ⊆ 队列 title 的 `#n ` 前缀 ⊆ returns 的 #n
  5 队列项正文含六行：目的 / 写哪个文件 / 合格线 / 依赖 / 预算 / 交回
  6 每个 returns/#n.md 首三行是 id/unit/status，status ∈ {DONE, BLOCKED}
  7 每个 returns/#n-verdict.md 首行 `verdict:` ∈ {pass, fail, marginal}，次行 `by:` 非空
  8 没有孤立的 verdict（有 verdict 必须有对应返回件）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent          # workspace/indicator
ROOT = WS.parents[1]                          # project root
FIELDS = ["目的", "写哪个文件", "合格线", "依赖", "预算", "交回"]
fails: list[str] = []


def ok(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check.py <identifier>", file=sys.stderr)
        return 2
    ident = sys.argv[1]
    d = WS / ident
    ok(d.is_dir(), f"[1] 目录不存在: {d}")
    if not d.is_dir():
        return report()

    for name in ("README.md", "supervisor-prompt.md", "LOOP_STATE.md"):
        ok((d / name).is_file(), f"[1] 缺文件 {ident}/{name}")
    for sub in ("units", "returns"):
        ok((d / sub).is_dir(), f"[1] 缺目录 {ident}/{sub}/")

    ls = (d / "LOOP_STATE.md")
    if ls.is_file():
        t = ls.read_text(encoding="utf-8")
        ok("## ON-RAMP" in t, "[2] LOOP_STATE 缺 `## ON-RAMP`")
        ok("## EXCLUDED" in t, "[2] LOOP_STATE 缺 `## EXCLUDED`")
        ok(re.search(r"ON-RAMP LEFT:\s*\d+", t) is not None, "[2] LOOP_STATE 缺 `ON-RAMP LEFT: n`")

    units = sorted(p for p in (d / "units").glob("[0-9]*.md"))
    unit_nums = set()
    for p in units:
        head = "\n".join(p.read_text(encoding="utf-8").splitlines()[:6])
        m = re.match(r"#?(\d+)", p.name)
        n = m.group(1) if m else None
        ok(n is not None, f"[3] 单元文件名不以编号开头: {p.name}")
        if n:
            unit_nums.add(n)
        ok(p.read_text(encoding="utf-8").splitlines()[0].startswith(f"# 单元 #{n}"), f"[3] {p.name} 首行不是 `# 单元 #{n} <项名>`")
        for key in ("id:", "unit:", "depends:"):
            ok(key in head, f"[3] {p.name} 头部缺 `{key}`")
        t = p.read_text(encoding="utf-8")
        ok("paves:" in t, f"[3] {p.name} 缺 `paves:`")
        for f in ("目的", "写哪个文件", "合格线", "依赖", "预算", "交回"):
            ok(f in t, f"[3] {p.name} 缺「{f}」")
        dm = re.search(r"depends:\s*\[([^\]]*)\]", t)
        ok(dm is not None, f"[10] {p.name} 的 `depends` 不是 `[...]`")
        if dm:
            for ref in re.findall(r'"(\d+)"', dm.group(1)):
                ok(ref in {re.match(r"(\d+)", q.name).group(1) for q in (d / "units").glob("[0-9]*.md") if re.match(r"(\d+)", q.name)},
                   f"[10] {p.name} 的 depends 指向不存在的单元 #{ref}")

    queue_titles: list[str] = []
    qid = f"TEMP_{ident}"
    try:
        out = subprocess.run(
            [str(ROOT / ".agent-tools" / "task-queue"), "list", "--id", qid],
            capture_output=True, text=True, check=False,
        )
        queue_titles = [ln.strip() for ln in out.stdout.splitlines() if ln.strip().startswith(tuple("0123456789"))]
    except Exception as exc:  # noqa: BLE001
        fails.append(f"[5] 调 task-queue 失败: {exc}")
    q_nums = set()
    for ln in queue_titles:
        m = re.search(r"单元\s*#(\d+)", ln) or re.search(r"#(\d+)\s", ln)
        if m:
            q_nums.add(m.group(1))
    ok(unit_nums <= q_nums or not q_nums, "[4] units 的编号未全部出现在队列 title 的 `#n ` 前缀里")

    qdir = ROOT / ".agent-ide" / "skills" / "task-queue" / "data" / qid / "tasks"
    if qdir.is_dir():
        for p in sorted(qdir.glob("*.yaml")):
            body = p.read_text(encoding="utf-8")
            for f in FIELDS:
                ok(f in body, f"[5] 队列项 {p.name} 缺「{f}」")

    rets = sorted(p for p in (d / "returns").glob("[0-9]*.md") if "verdict" not in p.name)
    ret_nums = set()
    for p in rets:
        head = "\n".join(p.read_text(encoding="utf-8").splitlines()[:4])
        m = re.match(r"#?(\d+)", p.name)
        if m:
            ret_nums.add(m.group(1))
        for key in ("id:", "unit:", "status:"):
            ok(key in head, f"[6] {p.name} 头部缺 `{key}`")
        sm = re.search(r"status:\s*(DONE|BLOCKED)", head)
        ok(sm is not None, f"[6] {p.name} 的 status 不是 DONE/BLOCKED")
    ok(ret_nums <= unit_nums or not ret_nums, "[4] returns 里有不存在的单元编号")

    verds = sorted((d / "returns").glob("[0-9]*-verdict.md"))
    for p in verds:
        lines = p.read_text(encoding="utf-8").splitlines()
        v = lines[0] if lines else ""
        ok(re.match(r"verdict:\s*(pass|fail|marginal)\s*$", v) is not None,
           f"[7] {p.name} 首行不是 `verdict: pass|fail|marginal`")
        ok(len(lines) > 1 and re.match(r"by:\s*L\d", lines[1]) is not None,
           f"[7] {p.name} 次行不是 `by: L<行号>`")
        n = re.match(r"(\d+)", p.name).group(1)
        ok(n in ret_nums, f"[8] {p.name} 有 verdict 但没有 returns/{n}.md")

    sp = d / "supervisor-prompt.md"
    if sp.is_file():
        body = sp.read_text(encoding="utf-8")
        heads = re.findall(r"^## ROUND \d+ ·", body, re.M)
        ok(heads, "[13] supervisor-prompt.md 没有 `## ROUND n ·` 段（围栏没按轮追加）")
        ok(body.count("> 来源：") >= len(heads),
           f"[13] supervisor-prompt.md 有 {len(heads)} 段但只有 {body.count('> 来源：')} 行来源")
        if ls.is_file():
            rounds = re.findall(r"^## ROUND (\d+)", ls.read_text(encoding="utf-8"), re.M)
            if rounds and heads:
                ok(int(heads[-1].split()[2]) >= max(int(r) for r in rounds) - 1,
                   "[13] supervisor-prompt.md 的最后一段落后于 LOOP_STATE 的轮次（本轮围栏没存）")

    if queue_titles and ret_nums - q_nums:
        print(f"note: 队列里没出现的编号 {sorted(ret_nums - q_nums)}（可能已 resolve，归档在队列 data/ 里）")
    if ls.is_file():
        t = ls.read_text(encoding="utf-8")
        m = re.search(r"ON-RAMP LEFT:\s*(\d+)", t)
        empty = sum(1 for ln in t.splitlines() if "— empty" in ln)
        if m:
            ok(int(m.group(1)) == empty,
               f"[12] `ON-RAMP LEFT: {m.group(1)}` 与 `— empty` 行数 {empty} 不一致")

    tmpl = WS / "_template"
    for name in ("README.md", "LOOP_STATE.md", "intake.md", "dispatch-block.md", "closure-answers.md", "review.md"):
        ok((tmpl / name).is_file(), f"[11] 标准件缺 {name}")
    for name in ("units/_template.md", "returns/_template.md", "returns/_verdict-template.md"):
        ok((WS / name).is_file(), f"[11] 标准件缺 {name}")

    return report()


def report() -> int:
    if fails:
        print(f"FAIL {len(fails)} 项:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS 13/13")
    return 0


if __name__ == "__main__":
    sys.exit(main())
