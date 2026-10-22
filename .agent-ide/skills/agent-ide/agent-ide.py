#!/usr/bin/env python3
"""agent-ide — move skill packages between project, global project and GitHub.

    install       write .agent-tools/<skill> launchers for local packages
    init-project  pull the default skills into a target project, then install
    push          project -> global (or --from-global)
    publish       global -> GitHub (or --from-github)
    inject        link a package's SKILL.md into an IDE domain
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from replicas import ReplicaError, Replicator, targets
from src import config, init, install, inject, paths, publish, transfer
from src.errors import AgentIdeError, Exit, fail


# ------------------------------------------------------------------- commands


def cmd_install(args: argparse.Namespace) -> None:
    install.run(paths.project_root(Path(__file__)), args.skills)


def cmd_init_project(args: argparse.Namespace) -> None:
    init.run(paths.project_root(Path(__file__)), Path(args.project), args.skills or None)


def cmd_push(args: argparse.Namespace) -> None:
    root = paths.project_root(Path(__file__))
    home = config.global_home(root, seed=True)
    local, shared = paths.skills_dir(root), paths.skills_dir(home)
    if args.from_global:
        transfer.batch(args.skills, shared, local, "push --from-global")
    else:
        transfer.batch(args.skills, local, shared, "push")


def cmd_publish(args: argparse.Namespace) -> None:
    publish.run(paths.project_root(Path(__file__)), args.skills, from_github=args.from_github)


def cmd_replicas(args: argparse.Namespace) -> None:
    skills_root = paths.skills_dir(paths.project_root(Path(__file__)))
    if args.skills:
        pkgs = [skills_root / name for name in args.skills]
        missing = [p.name for p in pkgs if not (p / paths.MANIFEST).is_file()]
        if missing:
            raise fail(Exit.Replica.FAILED, f"no such package: {', '.join(missing)}")
    else:
        pkgs = targets(skills_root)
        if not pkgs:
            raise fail(Exit.Replica.FAILED, "no skill declares a replicas block")

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
    p.set_defaults(run=cmd_install)

    p = sub.add_parser("init-project", help="bootstrap a project from the global project")
    p.add_argument("project", metavar="PATH")
    p.add_argument("skills", nargs="*", metavar="SKILL",
                   help=f"default: {' '.join(init.DEFAULT_SKILLS)}")
    p.set_defaults(run=cmd_init_project)

    p = sub.add_parser("push", help="copy packages project <-> global")
    p.add_argument("skills", nargs="+", metavar="SKILL")
    p.add_argument("--from-global", action="store_true", help="global -> project")
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
        print(f"agent-ide: {exc.message}", file=sys.stderr)
        return exc.code
    return Exit.OK


if __name__ == "__main__":
    raise SystemExit(main())
