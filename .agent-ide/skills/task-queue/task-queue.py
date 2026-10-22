#!/usr/bin/env python3
"""task-queue — one durable FIFO per id, and a verdict back to task_tree.

A queue is an index (`data/<id>/queue.json`) plus one YAML file per item under
`data/<id>/tasks/`. The index is the only authority on order, so it survives a
crash and can be reconciled against disk with `check --fix`.

The two verbs that matter are `push` (append, or `--front` to jump the line) and
`resolve` (take the head, record pass/fail/marginal, archive it, and write the
same verdict back to a `task_tree` node when one is installed).
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

VERDICTS = ("pass", "fail", "marginal")
STATUS = {"pass": "passed", "fail": "failed", "marginal": "marginal"}


# ------------------------------------------------------------------- layout


def project_root() -> Path:
    """Nearest ancestor of this script that holds `.agent-ide/skills`."""
    script = Path(__file__).resolve()
    for parent in script.parents:
        if (parent / ".agent-ide" / "skills").is_dir():
            return parent
    print("task-queue: no .agent-ide/skills above this script", file=sys.stderr)
    raise SystemExit(2)


def queue_dir(qid: str) -> Path:
    return project_root() / ".agent-ide" / "skills" / "task-queue" / "data" / qid


def index_path(qid: str) -> Path:
    return queue_dir(qid) / "queue.json"


def tasks_dir(qid: str) -> Path:
    return queue_dir(qid) / "tasks"


def task_path(qid: str, key: str) -> Path:
    return tasks_dir(qid) / f"{key}.yaml"


def fail(message: str, code: int = 2) -> "NoReturn":
    print(f"task-queue: {message}", file=sys.stderr)
    raise SystemExit(code)


# -------------------------------------------------------------------- index


def load_index(qid: str) -> list[str]:
    path = index_path(qid)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"unreadable queue index {path}: {exc}")
    if not isinstance(data, list) or not all(isinstance(k, str) for k in data):
        fail(f"queue index is not a list of ids: {path}")
    return data


def save_index(qid: str, index: list[str]) -> None:
    path = index_path(qid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------- item


def slug(text: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in text).strip("_")
    return (cleaned or "item")[:60]


def new_key(qid: str, title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{stamp}_{slug(title)}"
    key, n = base, 2
    while task_path(qid, key).exists():
        key = f"{base}-{n}"
        n += 1
    return key


def read_item(source: Path, title: str | None) -> dict:
    """A pushed file becomes one item: YAML keeps its fields, text becomes body."""
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() in (".yaml", ".yml"):
        try:
            doc = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            fail(f"{source.name}: invalid YAML: {exc}")
        if not isinstance(doc, dict):
            fail(f"{source.name}: YAML must be a mapping")
        return {
            "title": str(doc.get("title") or title or source.stem),
            "status": str(doc.get("status") or "pending"),
            "node": str(doc.get("node") or ""),
            "body": str(doc.get("body") or ""),
        }
    first = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()), "")
    return {"title": title or first[:80] or source.stem, "status": "pending", "node": "", "body": text}


def write_item(qid: str, key: str, item: dict) -> Path:
    path = task_path(qid, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"id": key, **item, "created": datetime.now().astimezone().isoformat(timespec="seconds")}
    if not doc.get("node"):
        doc.pop("node", None)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def load_item(qid: str, key: str) -> dict:
    path = task_path(qid, key)
    if not path.is_file():
        fail(f"queue '{qid}' lists '{key}' but {path} is missing; run: task-queue check --fix")
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        fail(f"{path.name}: invalid YAML: {exc}")
    if not isinstance(doc, dict):
        fail(f"{path.name}: YAML must be a mapping")
    return doc


def archive(qid: str, key: str) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = queue_dir(qid) / "_archived" / f"{stamp}_{key}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(task_path(qid, key), dest)
    task_path(qid, key).unlink()


def head(qid: str) -> tuple[list[str], str]:
    index = load_index(qid)
    if not index:
        fail(f"queue '{qid}' is empty", 3)
    return index, index[0]


# ----------------------------------------------------------------- commands


def cmd_push(args: argparse.Namespace) -> None:
    source = Path(args.file).expanduser()
    if not source.is_file():
        fail(f"no such file: {source}")
    item = read_item(source, args.title)
    key = new_key(args.id, item["title"])
    write_item(args.id, key, item)
    index = load_index(args.id)
    index.insert(0, key) if args.front else index.append(key)
    save_index(args.id, index)
    source.unlink()
    where = "front" if args.front else "tail"
    print(f"pushed {key} to {where} of '{args.id}' ({len(index)} waiting)")


def cmd_next(args: argparse.Namespace) -> None:
    index, key = head(args.id)
    item = load_item(args.id, key)
    print(f"{key}  [{item.get('status', 'pending')}]  {item.get('title', '')}")
    print(f"{len(index)} waiting in '{args.id}'")
    if args.body:
        print()
        print(str(item.get("body") or "").rstrip())


def cmd_list(args: argparse.Namespace) -> None:
    index = load_index(args.id)
    if not index:
        print(f"queue '{args.id}' is empty")
        return
    for position, key in enumerate(index, 1):
        item = load_item(args.id, key)
        print(f"{position:>3}  {key}  [{item.get('status', 'pending')}]  {item.get('title', '')}")
    print(f"{len(index)} waiting in '{args.id}'")


def cmd_pop(args: argparse.Namespace) -> None:
    index, key = head(args.id)
    item = load_item(args.id, key)
    item["status"] = "popped"
    task_path(args.id, key).write_text(
        yaml.safe_dump(item, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    archive(args.id, key)
    save_index(args.id, index[1:])
    print(f"popped {key}  {item.get('title', '')}")
    print(f"{len(index) - 1} waiting in '{args.id}'")


def cmd_resolve(args: argparse.Namespace) -> None:
    index, key = head(args.id)
    item = load_item(args.id, key)
    item["status"] = STATUS[args.verdict]
    item["verdict"] = args.verdict
    task_path(args.id, key).write_text(
        yaml.safe_dump(item, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    archive(args.id, key)
    save_index(args.id, index[1:])
    print(f"resolved {key} -> {args.verdict}")
    print(f"{len(index) - 1} waiting in '{args.id}'")
    if args.tree_id:
        # A queue item may name the tree node it settles; otherwise its own key is
        # the node id, which is what a task-queue-first workflow produces.
        _resolve_in_tree(args.tree_id, str(item.get("node") or key), args.verdict)


def _resolve_in_tree(tree_id: str, key: str, verdict: str) -> None:
    """Write the same verdict to the tree node; a missing tree is not a failure."""
    root = project_root()
    candidates = [
        root / ".agent-tools" / "task_tree",
        root / ".agent-tools" / "task-tree",
        shutil.which("task_tree"),
        shutil.which("task-tree"),
    ]
    exe = next((Path(c) for c in candidates if c and Path(c).is_file()), None)
    if exe is None:
        print(f"tree '{tree_id}': task_tree not installed, verdict not mirrored", file=sys.stderr)
        return
    done = subprocess.run(
        [str(exe), "--id", tree_id, "resolve", key, verdict,
         "--evidence", f"settled from task-queue item {key}"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        print(f"tree '{tree_id}': {done.stderr.strip() or f'exit {done.returncode}'}", file=sys.stderr)
        return
    print(f"tree '{tree_id}': {key} -> {verdict}")


def cmd_check(args: argparse.Namespace) -> None:
    qid = args.id
    if not queue_dir(qid).is_dir():
        print(f"queue '{qid}' does not exist")
        return
    index = load_index(qid)
    on_disk = {p.stem for p in tasks_dir(qid).glob("*.yaml")} if tasks_dir(qid).is_dir() else set()
    orphaned = [k for k in index if k not in on_disk]
    unlisted = sorted(on_disk - set(index))
    if not orphaned and not unlisted:
        print(f"queue '{qid}' is consistent ({len(index)} items)")
        return
    for key in orphaned:
        print(f"indexed but missing: {key}")
    for key in unlisted:
        print(f"on disk but unindexed: {key}")
    if not args.fix:
        print("run with --fix to reconcile")
        return
    save_index(qid, [k for k in index if k in on_disk] + unlisted)
    print(f"fixed: {len(index) - len(orphaned) + len(unlisted)} items in '{qid}'")


# ------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="task-queue", description="One durable FIFO per id, ordered by a single index"
    )
    parser.add_argument("--id", default="default", metavar="QUEUE",
                        help="queue id (default: default)")
    # SUPPRESS lets the flag sit before or after the subcommand: the parent sets
    # the value, and the subparser only overrides it when it appears again.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--id", default=argparse.SUPPRESS, metavar="QUEUE")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("push", parents=[common], help="add a file to the queue")
    p.add_argument("file", metavar="FILE")
    p.add_argument("--front", action="store_true", help="jump the line")
    p.add_argument("--title", help="override the title taken from the file")
    p.set_defaults(run=cmd_push)

    p = sub.add_parser("next", parents=[common], help="show the head of the queue")
    p.add_argument("--body", action="store_true", help="print the full body")
    p.set_defaults(run=cmd_next)

    p = sub.add_parser("list", parents=[common], help="one line per waiting item")
    p.set_defaults(run=cmd_list)

    p = sub.add_parser("pop", parents=[common], help="take the head off the queue, archived as popped")
    p.set_defaults(run=cmd_pop)

    p = sub.add_parser("resolve", parents=[common], help="record the head's verdict and archive it")
    p.add_argument("verdict", choices=VERDICTS)
    p.add_argument("--tree-id", metavar="TREE", help="mirror the verdict to task_tree")
    p.set_defaults(run=cmd_resolve)

    p = sub.add_parser("check", parents=[common], help="compare the index with the files on disk")
    p.add_argument("--fix", action="store_true", help="reconcile instead of reporting")
    p.set_defaults(run=cmd_check)
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
