#!/usr/bin/env python3
"""agent-ide — move skill packages between project, global project and GitHub.

    install       write .agent-tools/<skill> launchers for local packages
    push          project -> global (default) or global -> project (--from-global)
    publish       global -> GitHub (or --from-github)
    inject        link a package's SKILL.md into an IDE domain
    registry      list / add / remove the projects sharing this global project

`push` also copies what it pushed into every other registered project, so one
command keeps the machine consistent instead of one command per project.

`--project` names the project a command acts on, defaulting to the one holding
this script. `--global` names the global project to import from, so joining the
ecosystem is `push --from-global --global <path> <skill>...` and nothing else.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from replicas import ReplicaError, Replicator, targets
from src import config, context, install, inject, paths, publish, registry, transfer
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
    root = _project(args)
    install.run(root, args.skills)
    registry.remember(root)


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
        registry.remember(root, home)
    else:
        home = config.global_home(root, seed=True)
        names = transfer.batch(args.skills, paths.skills_dir(root),
                               paths.skills_dir(home), "push")
        registry.remember(root, home)
        if not args.no_fanout:
            registry.report(registry.fanout(root, home, names))


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
    root = paths.project_root(Path(__file__))
    publish.run(root, args.skills, from_github=args.from_github)
    registry.remember(root)


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


def cmd_registry(args: argparse.Namespace) -> None:
    root = _project(args)
    if args.action == "list":
        found = registry.entries()
        if not found:
            print(f"registry: empty ({paths.pretty(registry.location())})")
        for item in found:
            mark = " *" if Path(item["path"]) == root.resolve() else ""
            print(f"{paths.pretty(Path(item['path']))}{mark}  ({item.get('name', '?')})")
        return
    if args.action == "add":
        targets = [Path(p) for p in (args.projects or [str(root)])]
        for target in targets:
            path = target.expanduser()
            path = path.resolve() if path.is_absolute() else (root / path).resolve()
            try:
                entry = registry.add(path, config.global_home(root, seed=False))
            except (OSError, ValueError, AgentIdeError) as exc:
                raise fail(Exit.Config.MISSING_GLOBAL,
                           f"registry add: {getattr(exc, 'message', None) or exc}") from exc
            print(f"registry: added {paths.pretty(Path(entry['path']))}")
        return
    if args.action == "remove":
        targets = [Path(p) for p in (args.projects or [str(root)])]
        for target in targets:
            if registry.remove(target):
                print(f"registry: removed {paths.pretty(target)}")
            else:
                print(f"registry: not registered: {paths.pretty(target)}")
        return

    # sync: what `push` does automatically, run on demand after a pull
    home = config.global_home(root, seed=True)
    names = args.skills or registry.fanout_names(root, home)
    if not names:
        raise fail(Exit.Package.FAILED, "registry sync: the global project has no packages")
    registry.report(registry.fanout(root, home, names))


def cmd_inject(args: argparse.Namespace) -> None:
    inject.run(
        paths.project_root(Path(__file__)),
        args.domain,
        args.action,
        args.skills,
    )


# ---------------------------------------------------------------- transcripts


def _needle_file(raw: str) -> Path:
    """The --probe argument: a FILE holding a sentence, not the sentence itself.

    Every failure here is a usage error with the same advice, because the two
    mistakes look identical from the outside — passing the quote instead of a
    file, and pointing at a path that is not there.
    """
    p = Path(raw).expanduser()
    if not p.exists():
        raise fail(
            Exit.Cli.USAGE,
            f"--probe {p}: no such file. It takes a FILE whose first non-empty "
            f"line is a sentence from the reply you are looking for — write the "
            f"quote to /tmp/needle.txt first, then pass that path.")
    if p.is_dir():
        raise fail(
            Exit.Cli.USAGE,
            f"--probe {p}: is a directory. Pass a file that holds the sentence.")
    if not p.is_file():
        raise fail(Exit.Cli.USAGE, f"--probe {p}: not a regular file.")
    return p


def _checked(args: argparse.Namespace) -> None:
    """Reject argument shapes that would otherwise fail silently."""
    chosen = [name for name in ("bindings", "probe", "key") if getattr(args, name, None)]
    if len(chosen) > 1:
        raise fail(
            Exit.Cli.USAGE,
            f"pick one of --bindings / --probe / --key, not {', '.join('--' + c for c in chosen)}. "
            f"They are three different reads, and one of them was going to be ignored.")
    if args.top is not None and args.top < 1:
        raise fail(Exit.Cli.USAGE, f"--top {args.top}: must be 1 or more.")
    if args.last is not None and args.last < 1:
        raise fail(Exit.Cli.USAGE, f"--last {args.last}: must be 1 or more.")
    if args.out:
        parent = Path(args.out).expanduser().parent
        if not parent.exists():
            raise fail(Exit.Cli.USAGE, f"--out {args.out}: {parent} does not exist.")


def _store(args: argparse.Namespace):
    if args.root and not Path(args.root).expanduser().is_dir():
        raise fail(Exit.Cli.USAGE, f"--root {args.root}: not a directory.")
    try:
        return context.store_for(args.ide, args.root)
    except LookupError as exc:
        raise fail(Exit.Cli.USAGE, f"{exc}. Pass --ide <codebuddy|cursor|...> or --root <path>.")


def cmd_context(args: argparse.Namespace) -> None:
    """Read an IDE's transcript store: probe a fragment, or render one key."""
    _checked(args)
    if args.bindings:
        table = context.bindings()
        if not table:
            print("no bindings in agent-ide's config")
            return
        for name, key in table.items():
            print(f"{name}\t{key}")
        return

    if args.id:
        args.key = context.key_for(args.id)

    store = _store(args)

    if args.probe:
        hits = context.probe_keys(store, _needle_file(args.probe), args.top)
        if not hits:
            raise AgentIdeError(
                2,
                "no conversation matches this fragment: 0 hits. "
                "The fragment is not in this store. What to do next is a rule, "
                "not a guess — see ~/.codebuddy/rules/guide-probe-miss.md "
                "(or this skill's 'A miss is a stop, not a hint to search harder'). "
                "Exit 2.")
        for key, n in hits:
            print(f"{key}\t{n}")
        return

    if not args.key:
        raise AgentIdeError(2, "--key or --probe is required")

    try:
        conv = context.resolve_key(store, args.key)
    except LookupError:
        raise fail(
            Exit.Cli.USAGE,
            f"--key {args.key}: no conversation with that key under {store.root}. "
            f"Keys come from --probe or --bindings; pass one of those instead of guessing.")
    text = context.render_conversation(
        store, conv, last=args.last, since=args.since, until=args.until,
        with_tools=not args.no_tools, stamps=args.stamps,
    )
    if args.out:
        out = Path(args.out).expanduser()
        out.write_text(text, encoding="utf-8")
        print(f"{out}: {len(text.splitlines())} lines, {len(text)} bytes")
    else:
        print(text)


def cmd_violations(args: argparse.Namespace) -> None:
    """Record one judgement. The catalogue itself is data — read the file, not a command."""
    from src import violations as V

    if args.log:
        ev = V.log(args.log, args.result, args.test or "", args.note or "")
        n, _ = V.streak(args.log)
        print(f"{ev.at}  code {args.log}  {args.result}  streak -> {n}")
        return

    raise SystemExit("agent-ide: violations takes --log only; read staging/ledger/violations.json for the catalogue")


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
    p.add_argument("--no-fanout", action="store_true",
                   help="do not copy the pushed packages into the other registered projects")
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

    p = sub.add_parser("registry", help="the projects that share this global project")
    p.add_argument("action", choices=("list", "add", "remove", "sync"))
    p.add_argument("projects", nargs="*", metavar="PATH",
                   help="add/remove targets; default: this project")
    p.add_argument("skills", nargs="*", metavar="SKILL", help="sync: default all")
    p.add_argument("--project", metavar="PATH", help="project to act on")
    p.set_defaults(run=cmd_registry)

    p = sub.add_parser("context", help="read an IDE transcript store (probe / render)")
    p.add_argument("--ide", metavar="IDE", help="codebuddy (default: first detected)")
    p.add_argument("--root", metavar="PATH", help="history root, when detection is stale")
    p.add_argument("--id", metavar="ID", help="agent id bound to a conversation (see --bindings)")
    p.add_argument("--bindings", action="store_true", help="list agent id -> conversation key")
    p.add_argument("--probe", metavar="FILE", help="file holding a reply fragment; prints keys")
    p.add_argument("--key", metavar="KEY", help="conversation key to render")
    p.add_argument("--last", type=int, metavar="N", help="only the last N messages")
    p.add_argument("--since", metavar="WHEN", help="window start (ISO or epoch)")
    p.add_argument("--until", metavar="WHEN", help="window end")
    p.add_argument("--top", type=int, metavar="N", help="probe: at most N keys")
    p.add_argument("--no-tools", action="store_true", help="render: omit tool calls/results")
    p.add_argument("--stamps", action="store_true", help="render: prefix each message with its UTC time (@HH:MM:SSZ)")
    p.add_argument("--out", metavar="FILE", help="write the rendered text here")
    p.set_defaults(run=cmd_context)

    p = sub.add_parser("violations", help="record a judgement (catalogue is staging/ledger/violations.json)")
    p.add_argument("--log", type=int, metavar="CODE", help="record a judgement for an entry")
    p.add_argument("--result", choices=["pass", "fail", "clear"], help="with --log: pass | fail | clear")
    p.add_argument("--test", help="with --log: test code (e.g. SRC-1A)")
    p.add_argument("--note", help="with --log: one checkable sentence of evidence")
    p.set_defaults(run=cmd_violations)

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
