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
    for n in t["nodes"]:
        if n["state"] == "pending" and deps_done(t, n):
            return n
    return None


def counts(t: dict) -> dict:
    out = {k: 0 for k in ("pending", "active", "done", "ack", "dropped")}
    for n in t["nodes"]:
        out[n["state"]] = out.get(n["state"], 0) + 1
    return out


def render(t: dict, d: Path, brief: bool = False) -> str:
    c = counts(t)
    lines = ["instance  %s" % t["instance"], "state     %s" % t["state"],
             "nodes     %d  pending %d  active %d  done %d  ack %d  dropped %d"
             % (len(t["nodes"]), c["pending"], c["active"], c["done"], c["ack"], c["dropped"])]
    if t.get("summary"):
        lines.append("summary   %s" % t["summary"])
    if not brief:
        lines.append("")
        seen = set()
        for i, n in enumerate(t["nodes"], 1):
            mark = {"pending": " ", "active": ">", "done": "x", "ack": "v", "dropped": "-"}[n["state"]]
            lines.append("%2d [%s] %-6s %s" % (i, mark, n["id"], n["title"]))
            seen.add(n["id"])
            if n.get("after"):
                lines.append("         after %s" % ",".join(n["after"]))
            if n.get("criterion"):
                lines.append("         done when: %s" % n["criterion"])
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


def root_path_hint() -> str:
    return "data/plan/"


# ---------- commands ----------

def cmd_init(d: Path | None, args: list) -> int:
    summary = ""
    if "--summary" in args:
        summary = args[args.index("--summary") + 1]
    data = Path(globals()["HOOK_DATA"])
    prompt = ""
    cap = data / "capture" / "plan.txt"
    if cap.exists():
        prompt = cap.read_text(encoding="utf-8")
    live = instance_dir(data)
    if live and "--force" not in args:
        t0 = load(live)
        if t0["state"] != "done":
            print("blocked   还有未收束的实例 %s（state %s）：先走完或 `--force` 另起一个"
                  % (live.name, t0["state"]))
            return 1
    proj = data.parents[3].name if len(data.parents) > 3 else data.parent.name
    name = "%s-%s-%s" % (proj, time.strftime("%Y%m%d-%H%M%S"), slug(summary or "task"))
    d = root(data) / name
    d.mkdir(parents=True, exist_ok=True)
    t = {"instance": name, "created": now(), "state": "build", "summary": summary,
         "prompt": prompt, "nodes": [], "rounds": [{"n": 1, "opened": now()}], "closed": None}
    save(d, t)
    first = (prompt or "").strip().split("\n")[0][:160]
    print("+ %s\n  tree %s/tree.json\n" % (name, d))
    print("prompt    %s" % (first or "（没有捕获到 prompt：hook 未带 capture，请把原话写进 --summary）"))
    print("\n【构建阶段】先把环境语境拿到手，再按行动顺序长树，先易后难：")
    print("  1. 有针对性地探环境：`ls`、读已有的读数/占位/日志，只读与这条 prompt 相关的那几处；把读到的东西写进节点的 --context。")
    print("  2. 加节点：`hook plan add --title \"...\" --criterion \"...\" [--context \"...\"] [--after n1,n2] [--parent n0]`")
    print("     没有依赖、能立刻做完的在前；还要语境或依赖前项的在后；能拆成子任务的必须递归拆，每棵子树同样先易后难。")
    print("  3. 认为第一项语境够了：`hook plan ready` —— 缺 context 或 criterion 的节点会被点出来，补完才放行。")
    return 0


def cmd_add(d: Path | None, args: list) -> int:
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
    nid = "n%d" % (len(t["nodes"]) + 1)
    after = [x for x in re.split(r"[,，\s]+", val("--after")) if x]
    for a in after:
        if not node(t, a):
            print("plan: --after %s does not exist" % a)
            return 2
    n = {"id": nid, "title": title, "parent": val("--parent") or None, "after": after,
         "context": val("--context"), "criterion": val("--criterion"),
         "state": "pending", "note": "", "added": now()}
    t["nodes"].append(n)
    save(d, t)
    print("+ %s  %s" % (nid, title))
    print(render(t, d))
    return 0


def cmd_tree(d: Path | None, args: list) -> int:
    if need(d, "tree"):
        return 3
    t = load(d)
    print(render(t, d))
    print("\nprompt    %s" % (t.get("prompt", "").strip().split("\n")[0][:120] or "-"))
    return 0


def cmd_ready(d: Path | None, args: list) -> int:
    if need(d, "ready"):
        return 3
    t = load(d)
    bad = [n for n in t["nodes"] if n["state"] == "pending" and (not n.get("context") or not n.get("criterion"))]
    if bad:
        print("blocked   %d 个节点语境或判据没写全，补完再执行：" % len(bad))
        for n in bad:
            miss = [k for k in ("context", "criterion") if not n.get(k)]
            print("  %-4s %-28s 缺 %s" % (n["id"], n["title"][:28], "/".join(miss)))
        return 1
    if not t["nodes"]:
        print("blocked   树是空的：先 `add`")
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
    d = Path(__file__).resolve().parents[1]
    raise SystemExit(main(sys.argv[1:], d))
