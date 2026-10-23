"""Kaggle dev tool — entry + router; command logic lives in ``src/``.

This file is the only place that knows the command surface: it bootstraps the
agent context (``--id``), builds the parser, dispatches to a domain handler and
turns the result into an exit code. There is deliberately no ``src/cli_router``
indirection: argv -> exit code is the entry's own job, so it cannot drift from
the entry's bootstrap.

Every path returns an ``exit_codes`` value; no subcommand may silently exit 0.
Groups are registered as their slice lands (config, dataset, chrome, runtime and
notebook now; quota arrives with its own module), so ``--help`` only ever
advertises what works.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import identity
from src import kaggle_exec
from src.chrome import cmds as chrome_cmds
from src.config import cmds as config_cmds
from src.dataset import cmds as dataset_cmds
from src.exit_codes import INPUT_USAGE
from src.notebook import cmds as notebook_cmds
from src.notebook import passthrough
from src.paths import bootstrap
from src.quota import cmds as quota_cmds
from src.runtime import cmds as runtime_cmds

OWNED_GROUPS = frozenset({"config", "dataset", "chrome", "runtime", "notebook", "quota"})


class _Parser(argparse.ArgumentParser):
    """argparse that exits with INPUT_USAGE instead of argparse's own code 2."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"Error: {message}", file=sys.stderr)
        raise SystemExit(INPUT_USAGE)


def build_parser() -> _Parser:
    parser = _Parser(
        prog="kaggle",
        description="Kaggle API helper. One Kaggle account per agent (--id).",
    )
    groups = parser.add_subparsers(dest="group", metavar="<group>")

    config_cmds.register_config(groups)
    dataset_cmds.register_dataset(groups)
    chrome_cmds.register_chrome(groups)
    runtime_cmds.register_runtime(groups)
    notebook_cmds.register_notebook(groups)
    quota_cmds.register_quota(groups)
    return parser


def _passthrough(argv: list[str]) -> int:
    """Not a group we own -> official CLI, gated by the two named contracts."""
    argv = passthrough.enforce_passthrough_contract(argv)
    argv = passthrough.guard_kernels_output_passthrough(argv)
    username, token = identity.credentials()
    proc = kaggle_exec.run_kaggle_checked(argv, username=username, token=token)
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    """Run one domain handler on an already ``--id``-stripped argv."""
    parser = build_parser()
    try:
        if argv and not argv[0].startswith("-") and argv[0] not in OWNED_GROUPS:
            return _passthrough(argv)
        args = parser.parse_args(argv)
        if not args.group:
            parser.print_help(sys.stderr)
            return INPUT_USAGE
        if args.group == "config":
            return config_cmds.cmd_config(args)
        if args.group == "dataset":
            return dataset_cmds.cmd_dataset(args)
        if args.group == "chrome":
            return chrome_cmds.cmd_chrome(args)
        if args.group == "runtime":
            return runtime_cmds.cmd_runtime(args)
        if args.group == "notebook":
            return notebook_cmds.cmd_notebook(args)
        if args.group == "quota":
            return quota_cmds.cmd_quota(args)
    except identity.IdentityError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.code
    return INPUT_USAGE


if __name__ == "__main__":
    sys.exit(main(bootstrap(sys.argv[1:])))
