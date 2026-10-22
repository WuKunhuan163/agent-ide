"""``runtime`` group: parse registration + command bodies.

The group only prints and creates paths under ``data/agents/<id>/runtime/``, so
every other command can stay side-effect free until it really needs a directory.
"""
from __future__ import annotations

import argparse
import os

from src import identity
from src.exit_codes import INPUT_USAGE, OK
from src.paths import require_ctx
from src.runtime.store import ensure_runtime_dirs, runtime_path


def register_runtime(groups) -> None:
    runtime = groups.add_parser("runtime", help="inspect this agent's runtime tree")
    verbs = runtime.add_subparsers(dest="runtime_cmd", metavar="<cmd>")

    path = verbs.add_parser("path", help="print one absolute runtime path")
    path.add_argument(
        "kind",
        nargs="?",
        default="root",
        choices=("root", "deploy", "output", "logs"),
        help="which subtree to print (default: root)",
    )
    path.add_argument("name", nargs="?", default=None, help="entry inside that subtree")
    path.add_argument("--ensure", action="store_true", help="create the printed path first")

    verbs.add_parser("ensure", help="create the whole runtime tree")


def cmd_runtime(args: argparse.Namespace) -> int:
    verb = getattr(args, "runtime_cmd", None)
    if verb == "path":
        return cmd_runtime_path(args)
    if verb == "ensure":
        return cmd_runtime_ensure()
    raise identity.IdentityError(INPUT_USAGE, "runtime: pick a subcommand (path / ensure).")


def cmd_runtime_path(args: argparse.Namespace) -> int:
    target = runtime_path(args.kind, args.name)
    if args.ensure:
        os.makedirs(target, exist_ok=True)
    print(target)
    return OK


def cmd_runtime_ensure() -> int:
    ensure_runtime_dirs()
    print(f"[OK] runtime ready under {require_ctx().runtime_dir}")
    return OK
