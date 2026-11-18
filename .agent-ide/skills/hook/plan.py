#!/usr/bin/env python3
"""plan — a task-tree state machine the agent maintains while it works.

A tree is an instance in the hook's own data space: `data/plan/<instance>/tree.json`. The instance
carries the prompt that fired the rule, the tree itself, and the round log, so the
tree is both the plan and the trace of what was done with it.

Phases: build → solve → (replan → solve)* → done.
Nothing is evaluated here: `ack` asks the agent to recheck, and every transition
prints the next thing to do, so the state is readable from the command output.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

STATES = ("build", "solve", "replan", "done")
OPEN = ("pending", "active")
GOOD = ("done", "ack", "dropped")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def root(data: Path) -> Path:
    """Instances live in the hook's own data space, beside the rules that read them:
    `data/plan/<instance>/tree.json`. Deleting the project's tmp must not delete the plan."""
    return data / "plan"


def instance_dir(data: Path, name: str | None = None) -> Path | None:
    base = root(data)
    if name:
        d = base / name
        return d if (d / "tree.json").exists() else None
    live = [p for p in base.glob("*/tree.json") if p.exists()] if base.exists() else []
    if not live:
        return None
    def stamp(p: Path) -> float:
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("state") != "done"
        except Exception:
            return 0
    # prefer a live (not done) instance, then the newest; a directory touch must not steal the pointer
    return max(live, key=lambda p: (stamp(p), p.stat().st_mtime)).parent


def load(d: Path) -> dict:
    return json.loads((d / "tree.json").read_text(encoding="utf-8"))


def save(d: Path, t: dict) -> None:
    t["updated"] = now()
    tmp = d / "tree.json.tmp"
    tmp.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, d / "tree.json")


def slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", text.strip())[:28].strip("-")
    return s or "task"


def node(t: dict, nid: str) -> dict | None:
    return next((n for n in t["nodes"] if n["id"] == nid), None)


def deps_done(t: dict, n: dict) -> bool:
    for a in n.get("after", []):
        x = node(t, a)
        if not x or x["state"] not in GOOD:
            return False
    return True


def first_open(t: dict) -> dict | None:
    """DFS: the first pending leaf whose deps are done; a parent waits for its children."""
    for n in t["nodes"]:
        if n["state"] != "pending" or not deps_done(t, n):
            continue
        if has_open_descendant(t, n):
            continue
        return n
    return None

def counts(t: dict) -> dict:
    out = {k: 0 for k in ("pending", "active", "done", "ack", "dropped")}
    for n in t["nodes"]:
        out[n["state"]] = out.get(n["state"], 0) + 1
    return out


def children(t: dict, nid):
    return [n for n in t["nodes"] if (n.get("parent") or None) == nid]


def has_open_descendant(t: dict, n: dict) -> bool:
    for k in children(t, n["id"]):
        if k["state"] in OPEN or has_open_descendant(t, k):
            return True
    return False


def render(t: dict, d: Path, brief: bool = False) -> str:
    """One root, everything else under it. Indentation is the parent chain."""
    c = counts(t)
    roots = children(t, None)
    lines = ["instance  %s" % t["instance"], "state     %s" % t["state"],
             "nodes     %d  pending %d  active %d  done %d  ack %d  dropped %d"
             % (len(t["nodes"]), c["pending"], c["active"], c["done"], c["ack"], c["dropped"]),
             "roots     %d%s" % (len(roots), "" if len(roots) == 1 else "  <- 顶层只许有一个（原话那个节点）")]
    if t.get("summary"):
        lines.append("summary   %s" % t["summary"])
    if not brief:
        lines.append("")

        def walk(parent, depth):
            for n in [x for x in t["nodes"] if (x.get("parent") or None) == parent]:
                mark = {"pending": " ", "active": ">", "done": "x", "ack": "v", "dropped": "-"}[n["state"]]
                lines.append("%s[%s] %-4s %s" % ("   " * depth, mark, n["id"], n["title"]))
                if n.get("criterion"):
                    lines.append("%sdone when: %s" % ("   " * depth, n["criterion"]))
                walk(n["id"], depth + 1)

        walk(None, 1)
    return "\n".join(lines)

def next_block(t: dict, d: Path) -> str:
    if t["state"] == "replan":
        return replan_block(t, d, "")
    n = first_open(t)
    if not n:
        return close_block(t, d)
    return ("next      %s  %s\n"
            "context   %s\n"
            "done when %s\n\n%s"
            % (n["id"], n["title"], n.get("context") or "（未写，先补：读哪几处具名依据）",
               n.get("criterion") or "（未写，先补）",
               "→ 语境够就走 `hook plan start %s`；不够就先把语境补全，补完再用 `add --context` 或直接改这份树的这一项。" % n["id"]))


def close_block(t: dict, d: Path) -> str:
    bare = [n["id"] for n in t["nodes"] if n.get("root") and not children(t, n["id"])]
    if bare:
        return ("blocked   根节点 %s 还没拆子节点：注入不是规制，拆解才是。先 add 再 close。"
                % ",".join(bare))
    left = [n for n in t["nodes"] if n["state"] in OPEN]
    if left:
        return "blocked   %d 个未完成节点缺前置：%s" % (
            len(left), ", ".join("%s(deps %s)" % (n["id"], ",".join(n.get("after", [])) or "-") for n in left[:6]))
    t["state"] = "done"
    t["closed"] = now()
    save(d, t)
    c = counts(t)
    return ("state     done\n"
            "trace     %d 项：done %d，ack %d，dropped %d；这份树就是这一轮的行动轨迹。"
            % (len(t["nodes"]), c["done"], c["ack"], c["dropped"]))


def replan_block(t: dict, d: Path, reason: str) -> str:
    open_ids = [n["id"] for n in t["nodes"] if n["state"] in OPEN]
    done_ids = [n["id"] for n in t["nodes"] if n["state"] in ("done", "ack")]
    return ("state     replan%s\n"
            "may move  only what is unreached: add context (--context), reorder (--after), prune (drop), split (add --parent);\n"
            "          完成过的 %s 不许改，未行动的 %s 可以改。\n"
            "prompt    %s\n\n"
            "→ 改完 `hook plan resume`，系统按 DFS 放出第一个未开始或 pending 的项。"
            % ((" (" + reason + ")") if reason else "",
               ",".join(done_ids) or "-", ",".join(open_ids) or "-",
               (t.get("prompt") or "").strip().split("\n")[0][:120]))


READ_ONLY = ("tree", "status", "prompt")


def need(d: Path | None, command: str) -> int:
    if d is None:
        print("plan: no instance under %s\n  run `hook plan init --summary \"<一句话>\"` first" % root_path_hint())
        return 3
    if command in READ_ONLY:
        return 0
    t = load(d)
    if t["state"] == "done":
        print("plan: instance is done; `hook plan init` starts a new one")
        return 3
    return 0


def proj_name(data: Path) -> str:
    return data.parents[3].name if len(data.parents) > 3 else data.parent.name


def root_path_hint() -> str:
    return "data/plan/"


# ---------- commands ----------

def newest_capture(data: Path):
    """The newest prompt a plan-package rule fired on, with its record; None when there is none.

    Any rule whose id starts with `plan` may supply it (`plan` when the keyword matched,
    `plan-armed` when the prompt merely arrived while a tree was open) — both are written
    by the IDE's own call, never by hand.
    """
    best = None
    for txt in sorted((data / "capture").glob("plan*.txt")):
        rec = txt.with_suffix(".json")
        if not rec.exists():
            continue
        try:
            r = json.loads(rec.read_text(encoding="utf-8"))
            if r.get("sha256") != __import__("hashlib").sha256(txt.read_text(encoding="utf-8").encode("utf-8")).hexdigest():
                continue
        except Exception:
            continue
        stamp = r.get("at") or ""
        if best is None or stamp > best[0]:
            best = (stamp, txt, rec)
    return (best[1], best[2]) if best else None


def cmd_init(d, args: list) -> int:
    """The prompt is the root: one node for the prompt, its decomposition below."""
    import hashlib
    summary = args[args.index("--summary") + 1] if "--summary" in args else ""
    data = Path(globals()["HOOK_DATA"])
    cap = newest_capture(data)
    cap_txt = cap[0] if cap else data / "capture" / "plan.txt"
    cap_rec = cap[1] if cap else data / "capture" / "plan.json"
    live = instance_dir(data)
    if live and "--force" not in args:
        t0 = load(live)
        if t0["state"] != "done":
            print("blocked   还有未收束的实例 %s（state %s）：先走完或 `--force` 另起一个"
                  % (live.name, t0["state"]))
            return 1
    if not cap_txt.exists() or not cap_rec.exists():
        print("blocked   capture 没有来源记录：原话只能来自一次真实命中（IDE 的 payload 写 plan.txt 与 plan.json）")
        print("          缺 %s，拒绝建实例。" % ("plan.json" if cap_txt.exists() else "plan.txt"))
        return 1
    prompt = cap_txt.read_text(encoding="utf-8")
    rec = json.loads(cap_rec.read_text(encoding="utf-8"))
    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != rec.get("sha256"):
        print("blocked   capture 与来源记录对不上（被改过）：拒绝建实例")
        return 1
    name = "%s-%s-%s" % (proj_name(data), time.strftime("%Y%m%d-%H%M%S"), slug(summary or "task"))
    d = root(data) / name
    d.mkdir(parents=True, exist_ok=True)
    head = next((l.strip() for l in prompt.split("\n") if l.strip()), "原话")
    t = {"instance": name, "created": now(), "state": "build", "summary": summary,
         "prompt": prompt,
         "provenance": {"at": rec.get("at"), "matched": rec.get("matched"), "sha256": rec.get("sha256")},
         "nodes": [{"id": "n1", "title": head[:60], "parent": None, "after": [],
                    "context": "原话全文见 tree.json 的 prompt；这一项就是它",
                    "criterion": "这条 prompt 的每条要求都有子节点，且子节点全部 done/ack/dropped",
                    "state": "pending", "note": "", "added": now(), "root": True}],
         "rounds": [{"n": 1, "opened": now()}], "closed": None}
    save(d, t)
    print("+ %s\n  tree %s/tree.json\n" % (name, d))
    print("prompt    %s" % head[:120])
    print("provenance  at %s  matched %s" % (rec.get("at"), rec.get("matched")))
    print("\n【构建阶段】n1 就是这条原话，已建好；往下只加它的子节点：")
    print("  1. 探环境：只读与这条原话相关的那几处，把具名依据写进 --context。")
    print("  2. `hook plan add --parent n1 --title \"...\" --criterion \"...\" --context \"...\" [--after n2]`")
    print("     没有 --parent 的 add 会被拒；能拆的递归拆，子节点同样挂 --parent，先易后难。")
    print("  3. `hook plan ready`：子节点缺 context/criterion 会被点出；n1 要等子节点全部走完才轮到自己。")
    return 0

def cmd_add(d, args: list) -> int:
    if need(d, "add"):
        return 3
    t = load(d)
    def val(flag, default=""):
        return args[args.index(flag) + 1] if flag in args else default
    title = val("--title")
    if not title:
        print("plan: add needs --title")
        return 2
    if t["state"] not in ("build", "replan"):
        print("blocked   树只在 build 或 replan 期间能加节点（当前 %s）" % t["state"])
        return 1
    parent = val("--parent")
    if not parent:
        print("blocked   顶层只许有根节点（原话那个）：加子节点要给 --parent <id>")
        return 1
    if not node(t, parent):
        print("plan: --parent %s does not exist" % parent)
        return 2
    nid = "n%d" % (len(t["nodes"]) + 1)
    after = [x for x in re.split(r"[,，\s]+", val("--after")) if x]
    for a in after:
        if not node(t, a):
            print("plan: --after %s does not exist" % a)
            return 2
    n = {"id": nid, "title": title, "parent": parent, "after": after,
         "context": val("--context"), "criterion": val("--criterion"),
         "state": "pending", "note": "", "added": now()}
    t["nodes"].append(n)
    save(d, t)
    print("+ %s  %s  (parent %s)" % (nid, title, parent))
    print(render(t, d))
    return 0

def cmd_tree(d: Path | None, args: list) -> int:
    if need(d, "tree"):
        return 3
    t = load(d)
    print(render(t, d))
    print("\nprompt    %s" % (t.get("prompt", "").strip().split("\n")[0][:120] or "-"))
    return 0


def cmd_ready(d, args: list) -> int:
    if need(d, "ready"):
        return 3
    t = load(d)
    roots = children(t, None)
    if len(t["nodes"]) == 1 and roots:
        print("blocked   树只有一个根节点：先把这条原话拆成子节点（--parent %s）" % roots[0]["id"])
        return 1
    bad = [n for n in t["nodes"] if not n.get("root") and n["state"] == "pending"
           and (not n.get("context") or not n.get("criterion"))]
    if bad:
        print("blocked   %d 个节点语境或判据没写全，补完再执行：" % len(bad))
        for n in bad:
            miss = [k for k in ("context", "criterion") if not n.get(k)]
            print("  %-4s %-28s 缺 %s" % (n["id"], n["title"][:28], "/".join(miss)))
        return 1
    t["state"] = "solve"
    save(d, t)
    print("state     solve\n")
    print(next_block(t, d))
    return 0

def cmd_start(d: Path | None, args: list) -> int:
    if need(d, "start"):
        return 3
    if not args:
        print("plan: start <id>")
        return 2
    t = load(d)
    n = node(t, args[0])
    if not n:
        print("plan: no node %s" % args[0])
        return 3
    if n["state"] not in ("pending", "active"):
        print("plan: %s is %s" % (n["id"], n["state"]))
        return 3
    n["state"] = "active"
    n["started"] = now()
    save(d, t)
    print("state     %s active\ncriterion %s\n\n→ 做这一项；做完 `hook plan done %s --note \"<一句话>\"`"
          % (n["id"], n.get("criterion") or "-", n["id"]))
    return 0


def cmd_done(d: Path | None, args: list) -> int:
    if need(d, "done"):
        return 3
    if not args:
        print("plan: done <id> --note \"...\"")
        return 2
    t = load(d)
    n = node(t, args[0])
    if not n:
        print("plan: no node %s" % args[0])
        return 3
    note = ""
    if "--note" in args:
        note = args[args.index("--note") + 1]
    if n.get("root") and not children(t, n["id"]):
        print("blocked   根节点还没拆：先把这条原话拆成子节点（`hook plan add --parent %s ...`），"
              "根节点要等子节点全部 ack 之后才轮到自己" % n["id"])
        return 1
    if n.get("root"):
        left = [k["id"] for k in children(t, n["id"]) if k["state"] in OPEN]
        if left:
            print("blocked   子节点还没走完：%s" % ",".join(left))
            return 1
    n["state"] = "done"
    n["note"] = note
    n["finished"] = now()
    save(d, t)
    print("ack       %s 报完成：%s" % (n["id"], note or "（无说明）"))
    print("\n【系统收讫·不评判】复查这一项是否真的完成，再确认：")
    print("  1. 它说的完成，能不能用一条命令或一处可指的东西验一遍；")
    print("  2. 它有没有把没做的写成做过；")
    print("  3. 确认无误：`hook plan ack %s`；有问题就 `hook plan drop %s --why \"...\"` 重做。"
          % (n["id"], n["id"]))
    return 0


def cmd_ack(d: Path | None, args: list) -> int:
    if need(d, "ack"):
        return 3
    if not args:
        print("plan: ack <id>")
        return 2
    t = load(d)
    n = node(t, args[0])
    if not n:
        print("plan: no node %s" % args[0])
        return 3
    n["state"] = "ack"
    n["acked"] = now()
    save(d, t)
    prompt = (t.get("prompt") or "").strip()
    print("v %s\n" % n["id"])
    print("【重放 prompt】以下是这次计划最初要的东西，从头再读一遍：")
    print("-" * 60)
    print(prompt or "（没有存到 prompt）")
    print("-" * 60)
    print("\n【对树】基于现在的视野看这棵树有没有走偏：")
    print("  - 已完成的路径是否还指向 prompt 要的东西；")
    print("  - 剩下的节点是否还有人负责，谁先谁后是否仍然成立；")
    print("  - 语境是否掉了：掉了就用 `--context` 给自己补，不要凭记忆往下走。")
    print("  - 走偏或需要改：`hook plan replan --reason \"...\"`；没走偏：`hook plan next`。")
    return 0


def cmd_next(d: Path | None, args: list) -> int:
    if need(d, "next"):
        return 3
    t = load(d)
    if t["state"] == "build":
        print("state     build：先把树长完，再 `hook plan ready`")
        print(render(t, d, brief=True))
        return 1
    save(d, t)
    print(next_block(t, d))
    return 0


def cmd_replan(d: Path | None, args: list) -> int:
    if need(d, "replan"):
        return 3
    t = load(d)
    reason = args[args.index("--reason") + 1] if "--reason" in args else ""
    active = [n["id"] for n in t["nodes"] if n["state"] == "active"]
    if active:
        print("blocked   还有在做的节点 %s：先 done 或 drop 再重排" % ",".join(active))
        return 1
    t["state"] = "replan"
    save(d, t)
    print(replan_block(t, d, reason))
    return 0


def cmd_resume(d: Path | None, args: list) -> int:
    if need(d, "resume"):
        return 3
    t = load(d)
    if t["state"] != "replan":
        print("plan: resume only after replan (state is %s)" % t["state"])
        return 3
    bad = [n for n in t["nodes"] if n["state"] == "pending" and (not n.get("context") or not n.get("criterion"))]
    if bad:
        print("blocked   %d 个节点还缺 context/criterion：%s" % (len(bad), ",".join(n["id"] for n in bad)))
        return 1
    t["state"] = "solve"
    save(d, t)
    print("state     solve\n")
    print(next_block(t, d))
    return 0


def cmd_move(d: Path | None, args: list) -> int:
    if need(d, "move"):
        return 3
    if not args or "--before" not in args:
        print("plan: move <id> --before <id>")
        return 2
    t = load(d)
    n = node(t, args[0])
    tgt = node(t, args[args.index("--before") + 1])
    if not n or not tgt:
        print("plan: unknown id")
        return 3
    if t["state"] not in ("build", "replan"):
        print("blocked   树只在 build 或 replan 期间能重排（当前 %s）" % t["state"])
        return 1
    if n["state"] in ("done", "ack"):
        print("blocked   %s 已完成，不许挪" % n["id"])
        return 1
    t["nodes"].remove(n)
    t["nodes"].insert(t["nodes"].index(tgt), n)
    save(d, t)
    print("moved     %s before %s" % (n["id"], tgt["id"]))
    print(render(t, d, brief=True))
    return 0


def cmd_drop(d: Path | None, args: list) -> int:
    if need(d, "drop"):
        return 3
    if not args:
        print("plan: drop <id> --why \"...\"")
        return 2
    t = load(d)
    n = node(t, args[0])
    if not n:
        print("plan: no node %s" % args[0])
        return 3
    if n["state"] in ("done", "ack"):
        print("blocked   %s 已完成或已确认，不许剪；要重做就 add 新节点" % n["id"])
        return 1
    if t["state"] not in ("build", "replan", "solve"):
        print("blocked   %s 期间不能剪" % t["state"])
        return 1
    why = args[args.index("--why") + 1] if "--why" in args else ""
    n["state"] = "dropped"
    n["note"] = why
    if why:
        log_file = d / "pruned.tsv"
        head = "" if log_file.exists() else "id\ttitle\twhy\tat\n"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(head + "%s\t%s\t%s\t%s\n" % (n["id"], n["title"], why, now()))
    save(d, t)
    print("- %s  %s  (%s)" % (n["id"], n["title"], why or "no reason"))
    if t["state"] == "solve":
        print(next_block(t, d))
    else:
        print("state     %s（改完 `hook plan resume`）" % t["state"])
    return 0


def cmd_status(d: Path | None, args: list) -> int:
    if need(d, "status"):
        return 3
    print(render(load(d), d, brief=True))
    t = load(d)
    n = first_open(t)
    print("next      %s" % (("%s %s" % (n["id"], n["title"])) if n else "（无：可以 close）"))
    return 0


def cmd_prompt(d: Path | None, args: list) -> int:
    if need(d, "prompt"):
        return 3
    print((load(d).get("prompt") or "").strip() or "（没有存到 prompt）")
    return 0


def cmd_close(d: Path | None, args: list) -> int:
    if need(d, "close"):
        return 3
    t = load(d)
    print(close_block(t, load(d) and d))
    return 0


COMMANDS = {"init": cmd_init, "add": cmd_add, "tree": cmd_tree, "ready": cmd_ready,
            "start": cmd_start, "done": cmd_done, "ack": cmd_ack, "next": cmd_next,
            "replan": cmd_replan, "resume": cmd_resume, "drop": cmd_drop, "move": cmd_move,
            "status": cmd_status, "prompt": cmd_prompt, "close": cmd_close}


def auto_start(data: Path, prompt: str) -> str:
    """Called by the hook on every prompt, after the prompt has been stored.

    An open tree is continued; otherwise one is allocated now, named
    <project>-<stamp>-<summary>, with the prompt itself as the single root node.
    """
    d = instance_dir(data)
    if d is not None:
        t = load(d)
        if t["state"] != "done":
            n = first_open(t)
            if not n:
                return ("【plan｜%s 已分配给这条原话】state %s\n下一项：无（缺前置），`hook plan status` 看谁在等谁。"
                        % (t["instance"], t["state"]))
            return ("【plan｜%s 已分配给这条原话】state %s\n接下来这一项：%s  %s\ndone when %s\n"
                    "→ 语境够就 `hook plan start %s`；结果变了就 `hook plan replan --reason \"...\"`"
                    % (t["instance"], t["state"], n["id"], n["title"],
                       n.get("criterion") or "（缺）", n["id"]))
    head = next((l.strip() for l in prompt.split("\n") if l.strip()), "原话")
    name = "%s-%s-%s" % (proj_name(data), time.strftime("%Y%m%d-%H%M%S"), slug(head))
    d = root(data) / name
    d.mkdir(parents=True, exist_ok=True)
    import hashlib
    t = {"instance": name, "created": now(), "state": "build", "summary": head[:60],
         "prompt": prompt,
         "provenance": {"at": now(), "matched": "every prompt",
                        "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()},
         "nodes": [{"id": "n1", "title": head[:60], "parent": None, "after": [],
                    "context": "原话全文见 tree.json 的 prompt；这一项就是它",
                    "criterion": "这条 prompt 的每条要求都有子节点，且子节点全部 done/ack/dropped",
                    "state": "pending", "note": "", "added": now(), "root": True}],
         "rounds": [{"n": 1, "opened": now()}], "closed": None}
    save(d, t)
    return ("【plan｜新实例 %s】这条原话已存成根节点 n1。**本轮不许直接作答**：\n"
            "1. 先探环境（只读与它相关的那几处），把具名依据写进 --context；\n"
            "2. `hook plan add --parent n1 --title \"...\" --criterion \"...\" --context \"...\" [--after n2]`，"
            "先易后难、能拆就递归拆；\n"
            "3. `hook plan ready` 之后按 DFS 逐项 start → done → ack；根节点 n1 只有在子节点全部 ack 后才能 done，"
            "`close` 会拒绝没有子节点的根。" % name)


def next_text(data: Path) -> str:
    """What the open tree wants next, for the hook to inject on any prompt."""
    d = instance_dir(data)
    if d is None:
        return ""
    t = load(d)
    if t["state"] == "done":
        return ""
    n = first_open(t)
    c = counts(t)
    head = ("【plan｜树还开着】%s  state %s  pending %d active %d ack %d"
            % (t["instance"], t["state"], c["pending"], c["active"], c["ack"]))
    if not n:
        return head + "\n下一项：无（缺前置）。`hook plan status` 看谁在等谁。"
    body = ["next      %s  %s" % (n["id"], n["title"]),
            "context   %s" % (n.get("context") or "（缺）"),
            "done when %s" % (n.get("criterion") or "（缺）"),
            "→ 语境够就 `hook plan start %s`；不够先补语境；结果变了就 `hook plan replan --reason \"...\"`" % n["id"]]
    return head + "\n" + "\n".join(body)


def main(argv: list, data: Path) -> int:
    globals()["HOOK_DATA"] = data
    if not argv or argv[0] in ("-h", "--help"):
        print("plan: " + " / ".join(COMMANDS))
        print("  phase build:  init → add (many) → ready")
        print("  phase solve:  start → done → ack → (next | replan → (add|drop|move) → resume)")
        print("  finish:       close when nothing is open")
        return 0
    cmd = argv[0]
    if cmd not in COMMANDS:
        print("plan: unknown command %r; one of %s" % (cmd, ", ".join(COMMANDS)))
        return 2
    d = instance_dir(data)
    return COMMANDS[cmd](d, argv[1:])


if __name__ == "__main__":
    import sys
    data = Path(__file__).resolve().parents[1] / "data"
    raise SystemExit(main(sys.argv[1:], data))
