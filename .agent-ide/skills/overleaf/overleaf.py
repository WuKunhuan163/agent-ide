"""Overleaf CLI: thin entry wiring the store and template layers.

The surface is split by intent, not by object:

- **reads** are one verb each — `list-templates`, `tree`, `show-project`,
  `show-block`, `show-content`, `indexes`, `validate`, `search`;
- **every mutation** goes through the single `edit` command, which carries one
  verb per document edit — `add`, `set`, `move`, `duplicate`, `delete`,
  `replace`, `meta` — and every address is a selector (`--at` / `--to`).

`init`, `migrate`, `delete-project`, `build` and `clean` sit outside `edit`: they
act on a project's lifecycle or its products, not on its document.
"""
from __future__ import annotations

import argparse
import json
import sys

from src import build as build_pipeline
from src.store import api as store_api
from src.store import content_id
from src.store.errors import DataError
from src.store.migrate import migrate_legacy
from src.store.schema import Manifest
from src.template.compile import CompileError
from src.template.registry import list_instances, load_instance, manifest_for


def _json_arg(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError("MALFORMED_FILE", None, f"invalid JSON argument: {exc}")
    if not isinstance(value, dict):
        raise DataError("MALFORMED_FILE", None, "JSON argument must be an object")
    return value


def _manifest(project_or_instance) -> Manifest:
    return Manifest(manifest_for(project_or_instance))


def _read_source(raw: str | None, path: str | None, flag: str) -> str | None:
    """Resolve an inline / '-' / file payload source into raw text."""
    if path:
        if raw is not None:
            raise DataError("MALFORMED_FILE", None, f"use either --{flag} or --{flag}-file")
        if path == "-":
            return sys.stdin.read()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as exc:
            raise DataError("MALFORMED_FILE", path, f"cannot read file: {exc}")
    if raw == "-":
        return sys.stdin.read()
    return raw


def _content_arg(args) -> dict | None:
    """Resolve `--content` / `--content-file` ('-' = stdin) into a JSON object."""
    raw = _read_source(args.content, args.content_file, "content")
    return None if raw is None else _json_arg(raw)


def _value_arg(args):
    """Resolve `--value` / `--value-file` ('-' = stdin) into a JSON value of any type.

    Unlike `_content_arg` this does not insist on an object: a selector may address
    a string, a number, a boolean, a list or an object.
    """
    raw = _read_source(args.value, args.value_file, "value")
    if raw is None:
        raise DataError("MALFORMED_FILE", None, "a value is required (--value or --value-file)")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError("MALFORMED_FILE", None, f"invalid JSON value: {exc}")


def _display_arg(args) -> bool | None:
    display = getattr(args, "display", None)
    return None if display is None else display == "true"


# --------------------------------------------------------------------------- edit


def run_edit(agent_id: str, args) -> None:
    """Dispatch one document edit. The verb is `args.edit_op`; addresses are selectors."""
    p = args.proj
    op = args.edit_op
    project = None

    def current():
        nonlocal project
        if project is None:
            project = store_api.read_project(agent_id, p)
        return project

    if op == "add":
        display = _display_arg(args)
        block = store_api.add_block(
            agent_id,
            p,
            args.type,
            _content_arg(args),
            _manifest(current().template_id),
            _rel(args.to),
            args.order,
            display=True if display is None else display,
            project=current(),
        )
        print(store_api.dump(block))
        return

    if op == "set":
        written = store_api.set_content(
            agent_id,
            p,
            args.at,
            _value_arg(args),
            _manifest(current().template_id),
            project=current(),
        )
        print(json.dumps(written, indent=2, ensure_ascii=False))
        return

    if op == "move":
        block = store_api.move_block(
            agent_id,
            p,
            _rel(args.at),
            _manifest(current().template_id),
            _rel(args.to),
            args.order,
            project=current(),
        )
        print(store_api.dump(block))
        return

    if op == "duplicate":
        clone, labels = store_api.duplicate_block(
            agent_id,
            p,
            _rel(args.at),
            _manifest(current().template_id),
            _rel(args.to),
            args.order,
            project=current(),
        )
        payload = json.loads(store_api.dump(clone))
        payload["labels"] = labels
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if op == "delete":
        target = _rel(args.at)
        store_api.delete_block(agent_id, p, target)
        print(json.dumps({"deleted": target}, indent=2, ensure_ascii=False))
        return

    if op == "replace":
        changed = store_api.replace_in_blocks(agent_id, p, args.old, args.new)
        print(
            json.dumps(
                {"changed": changed, "count": len(changed)}, indent=2, ensure_ascii=False
            )
        )
        return

    # meta: merge --content into the project metadata.
    merged = store_api.update_meta(agent_id, p, _content_arg(args), project=current())
    print(store_api.dump(merged))


def _rel(address: str) -> str:
    """A block address in either notation (`section/text`, `$.blocks.section.text`)."""
    return content_id.rel_path_of(address or "")


# --------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(prog="overleaf", description="Overleaf document compiler")
    parser.add_argument("--id", dest="agent_id", required=True, help="Agent ID")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-templates")

    p_init = sub.add_parser("init")
    p_init.add_argument("--proj", required=True)
    p_init.add_argument("--conf", required=True)

    p_tree = sub.add_parser("tree")
    p_tree.add_argument("--proj", required=True)

    p_showproj = sub.add_parser("show-project")
    p_showproj.add_argument("--proj", required=True)

    p_show = sub.add_parser("show-block")
    p_show.add_argument("--proj", required=True)
    p_show.add_argument("--path", required=True)

    p_showc = sub.add_parser("show-content")
    p_showc.add_argument("--proj", required=True)
    p_showc.add_argument("--at", required=True, help="content selector, e.g. $.metadata.title")

    p_ix = sub.add_parser("indexes")
    p_ix.add_argument("--proj", required=True)

    p_val = sub.add_parser("validate")
    p_val.add_argument("--proj", required=True)

    p_search = sub.add_parser("search")
    p_search.add_argument("--proj", required=True)
    p_search.add_argument("--query", required=True)

    p_edit = sub.add_parser("edit", help="edit the document; one verb per change")
    verbs = p_edit.add_subparsers(dest="edit_op", required=True, metavar="VERB")

    def verb(name: str, help_text: str):
        """One edit verb: it always edits a project, so `--proj` comes first."""
        parser = verbs.add_parser(name, help=help_text)
        parser.add_argument("--proj", required=True)
        return parser

    v_add = verb("add", "create a block")
    v_add.add_argument("--type", required=True)
    v_add.add_argument("--to", default="", help="parent block address (default: top level)")
    v_add.add_argument("--order", type=int, default=None)
    v_add.add_argument("--display", choices=("true", "false"), default=None)
    v_add.add_argument("--content", help="inline JSON object, or '-' to read stdin")
    v_add.add_argument("--content-file", help="path to a JSON file")

    v_set = verb("set", "set the one node a selector names")
    v_set.add_argument("--at", required=True, metavar="SELECTOR")
    v_set.add_argument("--value", help="inline JSON value of any type, or '-' to read stdin")
    v_set.add_argument("--value-file", help="path to a JSON value file")

    v_move = verb("move", "reparent and/or reorder a block")
    v_move.add_argument("--at", required=True, metavar="SELECTOR")
    v_move.add_argument("--to", default="", help="destination parent (default: top level)")
    v_move.add_argument("--order", type=int, default=None)

    v_dup = verb("duplicate", "deep-copy a block under a new parent")
    v_dup.add_argument("--at", required=True, metavar="SELECTOR")
    v_dup.add_argument("--to", default="", help="destination parent (default: top level)")
    v_dup.add_argument("--order", type=int, default=None)

    v_del = verb("delete", "remove a block and its whole subtree")
    v_del.add_argument("--at", required=True, metavar="SELECTOR")

    v_rep = verb("replace", "replace literal text across every block")
    v_rep.add_argument("--old", required=True)
    v_rep.add_argument("--new", default="")

    v_meta = verb("meta", "merge keys into project metadata")
    v_meta.add_argument("--content", help="inline JSON object, or '-' to read stdin")
    v_meta.add_argument("--content-file", help="path to a JSON file")

    p_delproj = sub.add_parser("delete-project")
    p_delproj.add_argument("--proj", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--proj", required=True)
    p_build.add_argument("--no-compile", dest="compile", action="store_false", default=True)

    p_clean = sub.add_parser("clean")
    p_clean.add_argument("--proj", required=True)

    p_mig = sub.add_parser("migrate", help="import a project from the pre-rewrite layout")
    p_mig.add_argument("--from", dest="source", required=True,
                       help="old project directory (the one holding metadata.json)")
    p_mig.add_argument("--as", dest="target", default=None,
                       help="project id to create (default: the source folder name)")

    args = parser.parse_args()
    if not args.command:
        parser.error("a subcommand is required")

    a = args.agent_id
    p = getattr(args, "proj", None)

    if args.command == "list-templates":
        print(json.dumps(list_instances(), indent=2, ensure_ascii=False))
        return
    if args.command == "edit":
        run_edit(a, args)
        return
    if args.command == "init":
        spec, template = load_instance(args.conf)
        project = store_api.init_project(
            a, p, args.conf, template.default_metadata(), template_version=spec.get("version", 1)
        )
    elif args.command == "tree":
        project = store_api.list_tree(a, p)
    elif args.command == "show-project":
        project = store_api.read_project(a, p)
    elif args.command == "show-content":
        matches = store_api.show_content(a, p, args.at)
        print(json.dumps(matches, indent=2, ensure_ascii=False, default=str))
        return
    elif args.command == "show-block":
        project = store_api.read_block(a, p, args.path)
    elif args.command == "indexes":
        project = store_api.indexes(a, p)
    elif args.command == "validate":
        issues = store_api.validate(a, p, _manifest(store_api.read_project(a, p).template_id))
        print(store_api.dump(issues))
        raise SystemExit(0 if not issues else 1)
    elif args.command == "search":
        hits = store_api.search_blocks(a, p, args.query)
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return
    elif args.command == "delete-project":
        target = store_api.delete_project(a, p)
        print(json.dumps({"deleted": p, "moved_to": target}, indent=2, ensure_ascii=False))
        return
    elif args.command == "migrate":
        print(json.dumps(migrate_legacy(a, args.source, args.target),
                         indent=2, ensure_ascii=False))
        return
    elif args.command == "clean":
        print(json.dumps({"cleaned": build_pipeline.clean_build(a, p)}, indent=2, ensure_ascii=False))
        return
    elif args.command == "build":
        try:
            result = build_pipeline.build(a, p, do_compile=args.compile)
        except CompileError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1)
        for warning in result["warnings"]:
            print(f"warning: {warning}", file=sys.stderr)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return
    else:  # pragma: no cover - argparse guards this
        parser.error(f"unknown command {args.command!r}")
        return

    print(store_api.dump(project))


if __name__ == "__main__":
    try:
        main()
    except DataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
