#!/usr/bin/env python3
"""agent-ide — move skill packages between project, global project and GitHub.

    install       write .agent-tools/<skill> launchers for local packages
    push          project -> global (default) or global -> project (--from-global)
    publish       global -> GitHub (or --from-github)
    inject        link a package's SKILL.md into an IDE domain

`--project` names the project a command acts on, defaulting to the one holding
this script. `--global` names the global project to import from, so joining the
ecosystem is `push --from-global --global <path> <skill>...` and nothing else.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from replicas import ReplicaError, Replicator, targets
from src import config, install, inject, paths, publish, transfer
from src.errors import AgentIdeError, Exit, fail


# ------------------------------------------------------------------- commands


def _project(args: argparse.Namespace) -> Path:
    """The project a command acts on: `--project`, else the script's own.

    A relative `--project` is read against this script's own project, not the
    shell's cwd: the same command must name the same project from anywhere.
    """
    own = paths.project_root(Path(__file__))
    if args.project:
        raw = Path(args.project).expanduser()
        return raw.resolve() if raw.is_absolute() else (own / raw).resolve()
    return own


def cmd_install(args: argparse.Namespace) -> None:
    install.run(_project(args), args.skills)


def cmd_push(args: argparse.Namespace) -> None:
    root = _project(args)
    if args.global_home is not None and not args.from_global:
        raise fail(Exit.Cli.USAGE, "--global names the import source; use it with --from-global")
    if args.from_global:
        home = _named_global(args.global_home) or config.global_home(root, seed=True)
        paths.skills_dir(root).mkdir(parents=True, exist_ok=True)
        transfer.batch(args.skills, paths.skills_dir(home), paths.skills_dir(root),
                       "push --from-global")
        # The path the user gave is the answer to "where is the global project",
        # so it is recorded — never over a different global the project already
        # points at, and never only when some particular package came along with
        # it: the pointer is what `install` needs to find that project's runtime.
        config.adopt_global_home(root, home)
    else:
        home = config.global_home(root, seed=True)
        transfer.batch(args.skills, paths.skills_dir(root), paths.skills_dir(home), "push")


def _named_global(raw: str | None) -> Path | None:
    if raw is None:
        return None
    home = config.valid_global_home(raw)
    if home is None:
        raise fail(
            Exit.Config.MISSING_GLOBAL,
            f"--global is not a project (no {paths.IDE_DIR}/skills there): {raw}",
        )
    return home


def cmd_publish(args: argparse.Namespace) -> None:
    publish.run(paths.project_root(Path(__file__)), args.skills, from_github=args.from_github)


def cmd_replicas(args: argparse.Namespace) -> None:
    skills_root = paths.skills_dir(paths.project_root(Path(__file__)))
    if args.skills:
        pkgs = [skills_root / name for name in args.skills]
        missing = [p.name for p in pkgs if not (p / paths.MANIFEST).is_file()]
        if missing:
            raise fail(Exit.Replica.FAILED, f"replicas: no such package: {', '.join(missing)}")
    else:
        pkgs = targets(skills_root)
        if not pkgs:
            raise fail(Exit.Replica.FAILED, "replicas: no skill declares a block")

    drifted: list[str] = []
    for pkg_dir in pkgs:
        try:
            worker = Replicator.for_skill(pkg_dir)
            report = worker.sync() if args.action == "sync" else worker.status()
        except ReplicaError as exc:
            raise fail(Exit.Replica.FAILED, str(exc)) from exc
        print(report.line())
        if not report.ok:
            drifted.append(report.skill)

    if drifted:
        raise fail(
            Exit.Replica.FAILED,
            f"{', '.join(drifted)}: copy differs from source, left untouched",
        )


def cmd_inject(args: argparse.Namespace) -> None:
    inject.run(
        paths.project_root(Path(__file__)),
        args.domain,
        args.action,
        args.skills,
    )


# --------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-ide", description="Skill package transfer for the agent-ide ecosystem"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("install", help="write .agent-tools launchers for local packages")
    p.add_argument("skills", nargs="+", metavar="SKILL")
    p.add_argument("--project", metavar="PATH", help="project to act on")
    p.set_defaults(run=cmd_install)

    p = sub.add_parser("push", help="copy packages project <-> global")
    p.add_argument("skills", nargs="+", metavar="SKILL")
    p.add_argument("--from-global", action="store_true", help="global -> project")
    p.add_argument("--global", dest="global_home", metavar="PATH",
                   help="the global project to import from (recorded in the project's config)")
    p.add_argument("--project", metavar="PATH", help="project to act on")
    p.set_defaults(run=cmd_push)

    p = sub.add_parser("publish", help="copy packages global <-> GitHub")
    p.add_argument("skills", nargs="+", metavar="SKILL")
    p.add_argument("--from-github", action="store_true", help="GitHub -> global")
    p.set_defaults(run=cmd_publish)

    p = sub.add_parser("replicas", help="append-only copies of a skill's data/")
    p.add_argument("action", choices=("status", "sync"))
    p.add_argument("skills", nargs="*", metavar="SKILL",
                   help="default: every skill that declares a replicas block")
    p.set_defaults(run=cmd_replicas)

    p = sub.add_parser("inject", help="link SKILL.md into an IDE domain")
    p.add_argument("domain", metavar="DOMAIN", help="e.g. .cursor or .codebuddy/skills")
    p.add_argument("action", choices=("add-skill", "remove-skill"))
    p.add_argument("skills", nargs="*", metavar="SKILL", help="default: all")
    p.set_defaults(run=cmd_inject)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except AgentIdeError as exc:
        print(exc.message, file=sys.stderr)
        return exc.code
    return Exit.OK


if __name__ == "__main__":
    raise SystemExit(main())
