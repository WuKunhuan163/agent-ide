#!/usr/bin/env python3
"""task-tree — a hypothesis tree whose nodes carry a verdict.

One tree is one file: `data/<tree>/tree.json`. A node is a hypothesis, a check,
or a goal; `mode` says how it aggregates its children (`all`: every child must
pass, `one_of`: any child passing settles it). `resolve` records a verdict and
moves the focus to the next open node in DFS order, so "what do I test next"
never has to be decided by memory.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path

STATUSES = ("open", "passed", "failed", "marginal", "blocked")
VERDICT_TO_STATUS = {"pass": "passed", "fail": "failed", "marginal": "marginal"}


# ------------------------------------------------------------------- layout


def project_root() -> Path:
    script = Path(__file__).resolve()
    for parent in script.parents:
        if (parent / ".agent-ide" / "skills").is_dir():
            return parent
    print("task-tree: no .agent-ide/skills above this script", file=sys.stderr)
    raise SystemExit(2)


def resolve_arg(raw) -> Path:
    """A path typed on a command line: relative to the project root, never cwd."""
    path = Path(raw).expanduser()
    return path if path.is_absolute() else project_root() / path


def tree_dir(tree_id: str) -> Path:
    return project_root() / ".agent-ide" / "skills" / "task-tree" / "data" / tree_id


def tree_path(tree_id: str) -> Path:
    return tree_dir(tree_id) / "tree.json"


def fail(message: str, code: int = 2) -> "NoReturn":
    print(f"task-tree: {message}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------- tree


def load(tree_id: str) -> dict:
    path = tree_path(tree_id)
    if not path.is_file():
        fail(f"no tree '{tree_id}' ({path}); run: task-tree init --id {tree_id} --root <id> --title <t>")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"unreadable tree {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), dict):
        fail(f"{path}: not a tree document")
    return data


def save(tree_id: str, tree: dict) -> None:
    path = tree_path(tree_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def node(tree: dict, node_id: str) -> dict:
    found = tree["nodes"].get(node_id)
    if found is None:
        fail(f"no node '{node_id}' in tree '{tree.get('tree', '?')}'")
    return found


def ancestors(tree: dict, node_id: str) -> list[str]:
    out, current = [], tree["nodes"].get(node_id, {}).get("parent")
    while current:
        out.append(current)
        current = tree["nodes"].get(current, {}).get("parent")
    return out


# ------------------------------------------------------------------ progress


def settle(tree: dict, node_id: str) -> None:
    """Aggregate a parent from its children, then propagate upwards."""
    while node_id:
        current = tree["nodes"][node_id]
        children = [tree["nodes"][c] for c in current.get("children", [])]
        if children and current.get("mode") == "all":
            # A failed child rules out one branch, not the goal: the parent stays
            # open so the next route can be chosen deliberately.
            if all(c["status"] == "passed" for c in children):
                current["status"] = "passed"
            elif current["status"] in ("passed", "failed"):
                current["status"] = "open"
        elif children and current.get("mode") == "one_of":
            if any(c["status"] == "passed" for c in children):
                current["status"] = "passed"
            elif all(c["status"] in ("failed", "marginal") for c in children):
                current["status"] = "failed"
            elif current["status"] in ("passed", "failed"):
                current["status"] = "open"
        node_id = current.get("parent")


def unblock(tree: dict) -> list[str]:
    """Nodes whose `requires` are now all passed leave `blocked`."""
    opened = []
    for node_id, current in tree["nodes"].items():
        if current["status"] != "blocked":
            continue
        needs = current.get("requires") or []
        if needs and all(
            tree["nodes"].get(n, {}).get("status") == "passed" for n in needs
        ):
            current["status"] = "open"
            opened.append(node_id)
    return opened


def dfs_open(tree: dict, start: str | None) -> str | None:
    """First open node at or below `start`, then in DFS order over the whole tree."""
    root = tree["root"]

    def walk(node_id: str) -> str | None:
        current = tree["nodes"].get(node_id)
        if current is None:
            return None
        for child in current.get("children", []):
            found = walk(child)
            if found:
                return found
        # Only a leaf is work: a parent settles from its children.
        if not current.get("children") and current["status"] == "open":
            return node_id
        return None

    if start:
        for candidate in [start, *ancestors(tree, start)]:
            found = walk(candidate)
            if found:
                return found
    return walk(root)


# ----------------------------------------------------------------- commands


def cmd_init(args: argparse.Namespace) -> None:
    path = tree_path(args.id)
    if path.exists() and not args.force:
        fail(f"tree '{args.id}' already exists at {path}; pass --force to replace it")
    tree = {
        "tree": args.id,
        "root": args.root,
        "focus": args.root,
        "nodes": {
            args.root: {
                "title": args.title or args.root,
                "type": "goal",
                "desc": args.desc,
                "status": "open",
                "parent": None,
                "children": [],
                "mode": "all",
                "requires": [],
                "verdict": None,
                "evidence": "",
            }
        },
        "history": [],
    }
    save(args.id, tree)
    print(f"created '{args.id}' root={args.root}  {tree['nodes'][args.root]['title']}")


def read_body(path: str | None) -> str:
    if not path:
        return ""
    source = resolve_arg(path)
    if not source.is_file():
        fail(f"no such body file: {source}")
    return source.read_text(encoding="utf-8").strip()


def cmd_body(args: argparse.Namespace) -> None:
    tree = load(args.id)
    target = node(tree, args.node)
    target["body"] = read_body(args.file)
    save(args.id, tree)
    print(f"{args.node}: body {len(target['body'])} chars")


def cmd_add(args: argparse.Namespace) -> None:
    tree = load(args.id)
    if args.node in tree["nodes"]:
        fail(f"node '{args.node}' already exists")
    parent = node(tree, args.parent)
    needs = [n.strip() for n in args.requires if n.strip()]
    for need in needs:
        if need not in tree["nodes"]:
            fail(f"requires unknown node '{need}'")
    tree["nodes"][args.node] = {
        "title": args.title or args.node,
        "type": args.type,
        "desc": args.desc,
        "status": "blocked" if needs and not all(
            tree["nodes"][n]["status"] == "passed" for n in needs
        ) else "open",
        "parent": args.parent,
        "children": [],
        "mode": "all",
        "requires": needs,
        "verdict": None,
        "evidence": "",
        "body": read_body(args.body_file),
    }
    parent["children"].append(args.node)
    settle(tree, args.parent)
    tree["focus"] = dfs_open(tree, tree.get("focus"))
    save(args.id, tree)
    print(f"added {args.node} under {args.parent}  {tree['nodes'][args.node]['title']}"
          f"{'  (blocked)' if tree['nodes'][args.node]['status'] == 'blocked' else ''}")


def cmd_mode(args: argparse.Namespace) -> None:
    tree = load(args.id)
    target = node(tree, args.node)
    target["mode"] = args.mode
    settle(tree, args.node)
    tree["focus"] = dfs_open(tree, tree.get("focus"))
    save(args.id, tree)
    print(f"{args.node}: mode={args.mode} status={target['status']}")


def cmd_resolve(args: argparse.Namespace) -> None:
    tree = load(args.id)
    target = node(tree, args.node)
    if target["status"] in ("passed", "failed", "marginal") and not args.force:
        fail(f"'{args.node}' is already {target['status']}; pass --force to change it")
    target["status"] = VERDICT_TO_STATUS[args.verdict]
    target["verdict"] = args.verdict
    target["evidence"] = args.evidence
    tree.setdefault("history", []).append(
        {
            "node": args.node,
            "verdict": args.verdict,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "evidence": args.evidence,
        }
    )
    settle(tree, target.get("parent") or tree["root"])
    opened = unblock(tree) if args.verdict == "pass" else []
    for node_id in opened:
        print(f"unblocked {node_id}  {tree['nodes'][node_id]['title']}")

    following = dfs_open(tree, args.node)
    tree["focus"] = following
    save(args.id, tree)
    print(f"resolved {args.node} -> {args.verdict}")
    remaining = sum(
        1 for n in tree["nodes"].values() if n["status"] == "open" and not n["children"]
    )
    if args.verdict == "marginal":
        print(f"recorded {args.node} as marginal: evidence is not enough to settle it")
    elif following:
        print(f"next: {following}  {tree['nodes'][following]['title']}  ({remaining} open)")
    else:
        print(f"no open node left ({len(tree['nodes'])} nodes)")


def cmd_focus(args: argparse.Namespace) -> None:
    tree = load(args.id)
    if args.node:
        node(tree, args.node)
        tree["focus"] = args.node
        save(args.id, tree)
    target = tree.get("focus")
    if not target:
        print(f"{args.id}: no focus (nothing open)")
        return
    current = tree["nodes"][target]
    print(f"focus: {target}  [{current['status']}]  {current['title']}")


def cmd_next(args: argparse.Namespace) -> None:
    tree = load(args.id)
    focus = tree.get("focus")
    hanging = (
        focus
        if focus in tree["nodes"]
        and tree["nodes"][focus]["status"] == "marginal"
        and not tree["nodes"][focus]["children"]
        else None
    )
    target = hanging or dfs_open(tree, focus) or focus
    if not target:
        print(f"{args.id}: nothing open; every node is settled")
        return
    current = tree["nodes"][target]
    print(f"{target}  [{current['status']}]  {current['title']}")
    if current.get("type") != "goal":
        print(f"type: {current['type']}")
    if current.get("desc"):
        print(current["desc"])
    if getattr(args, "body", False) and current.get("body"):
        print()
        print(current["body"])
    needs = current.get("requires") or []
    if needs:
        state = ", ".join(f"{n}={tree['nodes'][n]['status']}" for n in needs if n in tree["nodes"])
        print(f"requires: {state}")
    parent_id = current.get("parent")
    if parent_id:
        parent = tree["nodes"][parent_id]
        if len(parent["children"]) > 1:
            print(f"parent {parent_id}: {len(parent['children'])} children, mode={parent['mode']}")
    if current["status"] == "marginal":
        print(f"split it: task-tree --id {args.id} add <child> --parent {target} --title '...'")
    else:
        print(f"settle with: task-tree --id {args.id} resolve {target} pass|fail|marginal --evidence '...'")


def cmd_show(args: argparse.Namespace) -> None:
    tree = load(args.id)
    focus = tree.get("focus")
    marks = {"open": " ", "passed": "+", "failed": "-", "marginal": "~", "blocked": "x"}

    def walk(node_id: str, depth: int) -> None:
        current = tree["nodes"][node_id]
        pointer = "*" if node_id == focus else " "
        indent = "  " * depth
        print(f"{pointer}{indent}{marks.get(current['status'], ' ')} {node_id}  {current['title']}"
              f"  [{current['status']}]")
        for child in current.get("children", []):
            walk(child, depth + 1)

    walk(tree["root"], 0)
    total = len(tree["nodes"])
    print(f"\n{total} nodes  focus={focus or '-'}  modes: all=every child must pass, one_of=any one settles")


def cmd_rm(args: argparse.Namespace) -> None:
    tree = load(args.id)
    if args.node == tree["root"]:
        fail("refusing to remove the root; delete the tree instead")
    target = node(tree, args.node)
    victims = [args.node]

    def collect(node_id: str) -> None:
        for child in tree["nodes"][node_id].get("children", []):
            victims.append(child)
            collect(child)

    collect(args.node)
    if not args.force:
        fail(f"would remove {len(victims)} node(s): {' '.join(victims)}; pass --force")
    parent = tree["nodes"].get(target.get("parent") or "")
    if parent:
        parent["children"] = [c for c in parent["children"] if c != args.node]
    for node_id in victims:
        tree["nodes"].pop(node_id, None)
    for current in tree["nodes"].values():
        current["requires"] = [r for r in current.get("requires", []) if r not in victims]
    if parent:
        settle(tree, parent["parent"] or tree["root"])
    tree["focus"] = dfs_open(tree, tree["root"])
    save(args.id, tree)
    print(f"removed {len(victims)} node(s); focus={tree['focus'] or '-'}")


def cmd_check(args: argparse.Namespace) -> None:
    tree = load(args.id)
    problems = []
    for node_id, current in tree["nodes"].items():
        for need in current.get("requires") or []:
            if need not in tree["nodes"]:
                problems.append(f"{node_id}: requires missing node '{need}'")
        parent = current.get("parent")
        if parent is None:
            if node_id != tree["root"]:
                problems.append(f"{node_id}: parentless but not the root")
        elif parent not in tree["nodes"]:
            problems.append(f"{node_id}: parent '{parent}' missing")
        elif node_id not in tree["nodes"][parent].get("children", []):
            problems.append(f"{node_id}: not listed under '{parent}'")
        for child in current.get("children", []):
            if child not in tree["nodes"]:
                problems.append(f"{node_id}: child '{child}' missing")
            elif tree["nodes"][child].get("parent") != node_id:
                problems.append(f"{node_id}: child '{child}' points elsewhere")
    if tree.get("focus") and tree["focus"] not in tree["nodes"]:
        problems.append(f"focus '{tree['focus']}' missing")
    if not problems:
        print(f"tree '{args.id}': consistent ({len(tree['nodes'])} nodes)")
        return
    for problem in problems:
        print(problem)
    if not args.fix:
        print("run with --fix to drop dangling references")
        return
    for node_id in list(tree["nodes"]):
        current = tree["nodes"][node_id]
        parent = current.get("parent")
        if node_id != tree["root"] and (parent not in tree["nodes"] or not parent):
            tree["nodes"].pop(node_id)
            continue
        current["children"] = [c for c in current.get("children", []) if c in tree["nodes"]]
        current["requires"] = [r for r in current.get("requires", []) if r in tree["nodes"]]
    if tree.get("focus") not in tree["nodes"]:
        tree["focus"] = dfs_open(tree, tree["root"])
    save(args.id, tree)
    print(f"fixed: {len(tree['nodes'])} nodes remain")


# ------------------------------------------------------------------- export


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{tree} — task-tree</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font: 15px/1.5 ui-sans-serif, -apple-system, "Segoe UI", sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; }}
h1 {{ font-size: 1.2rem; margin: 0 0 .25rem; }}
.meta {{ opacity: .7; margin-bottom: 1.5rem; }}
details {{ margin: .15rem 0 .15rem 1.1rem; border-left: 2px solid rgba(128,128,128,.25); padding-left: .8rem; }}
details > summary {{ cursor: pointer; list-style: none; }}
details > summary::-webkit-details-marker {{ display: none; }}
.focus {{ outline: 2px solid #e0a000; border-radius: 4px; }}
.dot {{ display: inline-block; width: .6rem; height: .6rem; border-radius: 50%; margin-right: .45rem; }}
.open .dot {{ background: #9aa0a6; }}
.passed .dot {{ background: #1a7f37; }}
.failed .dot {{ background: #c62828; }}
.marginal .dot {{ background: #e0a000; }}
.blocked .dot {{ background: #6a4fb3; }}
.id {{ font-family: ui-monospace, monospace; font-size: .85em; opacity: .65; margin-left: .4rem; }}
.status {{ font-size: .8em; opacity: .6; margin-left: .4rem; }}
.desc {{ margin: .2rem 0 .4rem 1.05rem; opacity: .8; font-size: .92em; }}
.body {{ margin: .2rem 0 .6rem 1.05rem; font-size: .92em; max-width: 44rem; }}
.body p {{ margin: .35rem 0; }}
.legend {{ margin-top: 2rem; font-size: .85em; opacity: .75; }}
</style></head><body>
<h1>{title}</h1>
<div class="meta">tree <b>{tree}</b> · {count} nodes · focus <b>{focus}</b> · exported {when}</div>
{body}
<div class="legend">● open ● passed ● failed ● marginal ● blocked · click a node to fold its subtree</div>
</body></html>
"""


def render_node(tree: dict, node_id: str) -> str:
    current = tree["nodes"][node_id]
    status = current["status"]
    focus = " focus" if node_id == tree.get("focus") else ""
    summary = (
        f'<span class="dot"></span>{escape(current["title"])}'
        f'<span class="id">{escape(node_id)}</span>'
        f'<span class="status">{escape(status)}</span>'
    )
    desc = f'<div class="desc">{escape(current["desc"])}</div>' if current.get("desc") else ""
    body = ""
    if current.get("body"):
        paragraphs = "".join(
            f"<p>{escape(block)}</p>" for block in current["body"].split("\n\n") if block.strip()
        )
        body = f'<div class="body">{paragraphs}</div>'
    children = "".join(render_node(tree, c) for c in current.get("children", []))
    if children:
        return f'<details open class="{status}{focus}"><summary>{summary}</summary>{desc}{body}{children}</details>'
    return f'<div class="{status}{focus}" style="margin:.15rem 0 .15rem 1.1rem">{summary}{desc}{body}</div>'


def cmd_export(args: argparse.Namespace) -> None:
    tree = load(args.id)
    body = render_node(tree, tree["root"])
    html = HTML.format(
        tree=escape(args.id),
        title=escape(tree["nodes"][tree["root"]]["title"]),
        count=len(tree["nodes"]),
        focus=escape(tree.get("focus") or "-"),
        when=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
        body=body,
    )
    out = resolve_arg(args.out) if args.out else tree_dir(args.id) / "tree.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"exported {out} ({len(html)} bytes)")


# ------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="task-tree", description="A hypothesis tree whose nodes carry a verdict"
    )
    parser.add_argument("--id", default="default", metavar="TREE", help="tree id (default: default)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--id", default=argparse.SUPPRESS, metavar="TREE")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", parents=[common], help="create a tree with one root node")
    p.add_argument("--root", required=True, metavar="NODE")
    p.add_argument("--title", default="")
    p.add_argument("--desc", default="")
    p.add_argument("--force", action="store_true")
    p.set_defaults(run=cmd_init)

    p = sub.add_parser("add", parents=[common], help="add a child node")
    p.add_argument("node", metavar="NODE")
    p.add_argument("--parent", required=True, metavar="NODE")
    p.add_argument("--title", default="")
    p.add_argument("--type", default="hypothesis", choices=("goal", "hypothesis", "check"))
    p.add_argument("--desc", default="")
    p.add_argument("--requires", nargs="*", default=[], metavar="NODE")
    p.add_argument("--body-file", metavar="FILE", help="node body, read from a file")
    p.set_defaults(run=cmd_add)

    p = sub.add_parser("body", parents=[common], help="set or replace a node's body")
    p.add_argument("node", metavar="NODE")
    p.add_argument("--file", required=True, metavar="FILE")
    p.set_defaults(run=cmd_body)

    p = sub.add_parser("mode", parents=[common], help="how a node aggregates its children")
    p.add_argument("node", metavar="NODE")
    p.add_argument("mode", choices=("all", "one_of"))
    p.set_defaults(run=cmd_mode)

    p = sub.add_parser("resolve", parents=[common], help="settle a node and advance the focus")
    p.add_argument("node", metavar="NODE")
    p.add_argument("verdict", choices=("pass", "fail", "marginal"))
    p.add_argument("--evidence", default="", metavar="TEXT")
    p.add_argument("--force", action="store_true", help="change a settled node")
    p.set_defaults(run=cmd_resolve)

    p = sub.add_parser("focus", parents=[common], help="show or set the working node")
    p.add_argument("node", nargs="?", default="")
    p.set_defaults(run=cmd_focus)

    p = sub.add_parser("next", parents=[common], help="what to work on now")
    p.add_argument("--body", action="store_true", help="print the node body")
    p.set_defaults(run=cmd_next)

    p = sub.add_parser("show", parents=[common], help="print the whole tree")
    p.set_defaults(run=cmd_show)

    p = sub.add_parser("rm", parents=[common], help="remove a subtree")
    p.add_argument("node", metavar="NODE")
    p.add_argument("--force", action="store_true")
    p.set_defaults(run=cmd_rm)

    p = sub.add_parser("check", parents=[common], help="find dangling links")
    p.add_argument("--fix", action="store_true")
    p.set_defaults(run=cmd_check)

    p = sub.add_parser("export", parents=[common], help="write a self-contained HTML view")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(run=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    args.run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
