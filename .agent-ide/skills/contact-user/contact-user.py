#!/usr/bin/env python3
"""contact-user — the blocking user channel of this project.

Four groups of flags, one dispatch table:

    round     --id <id>            open a round and block for the reply
              --recent [N]         read archived rounds back
    read      --ide-context        the pre-report read (unlocks a round,
                                   prints the report anchor its draft must quote)
    store     --detect-history-root / --set-history-root / --set-session-ide
              --sync-session, --session-log
    journal   --archive FILE      export archived rounds as markdown (read-only)
              --prune             move the same window's rounds to the Trash
    maintain  --merge-into/--sources, --delete-id, `resolve`
"""
from __future__ import annotations
import argparse
import sys

from src.exit_codes import Exit


def _default_sigpipe() -> None:
    """`contact-user ... | head` should stop quietly, not raise."""
    import signal

    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contact-user",
        description="Blocking user channel: write two input files, open the "
                    "window, read the reply on stdout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--id", dest="agent_id", metavar="ID",
                        help="agent id; keys the archive, the window and the lock")

    round_group = parser.add_argument_group("round")
    round_group.add_argument("--recent", nargs="?", const=8, default=None, type=int,
                             metavar="N", help="print the last N archived rounds (default 8)")
    round_group.add_argument("--ide-context", nargs="?", const=100, default=None, type=int,
                             metavar="ROUNDS",
                             help="print the last ROUNDS rounds untruncated "
                                  "(default 100) and unlock one round")

    read_group = parser.add_argument_group("read")
    read_group.add_argument("--since", default=None, metavar="WHEN", help="window start")
    read_group.add_argument("--until", default=None, metavar="WHEN", help="window end")
    read_group.add_argument("--conversation", default=None, metavar="CONV",
                            help="narrow --ide-context to one conversation")
    read_group.add_argument("--json", dest="as_json", action="store_true",
                            help="with --sync-session: machine-readable output")
    read_group.add_argument("--out", default=None, metavar="FILE",
                            help="write the text to FILE instead of stdout")

    store_group = parser.add_argument_group("store")
    store_group.add_argument("--detect-history-root", action="store_true",
                             help="print candidate stores as `ide<TAB>path`")
    store_group.add_argument("--set-history-root", default=None, metavar="PATH",
                             help="pin the transcript store by absolute path")
    store_group.add_argument("--set-session-ide", default=None, metavar="ID",
                             help="choose the adapter that reads the store")
    store_group.add_argument("--ide", default=None, metavar="ID",
                             help="adapter for --set-history-root")
    store_group.add_argument("--sync-session", action="store_true",
                             help="mirror the store into its own git repository")
    store_group.add_argument("--session-log", nargs="?", const=10, default=None, type=int,
                             metavar="N", help="last N mirror commits")

    journal_group = parser.add_argument_group("journal")
    journal_group.add_argument("--archive", default=None, metavar="FILE",
                               help="export these rounds to a markdown journal; "
                                    "the archive is left untouched")
    journal_group.add_argument("--prune", action="store_true",
                               help="move the same window's rounds to the Trash")
    journal_group.add_argument("--tail", default=5, type=int, metavar="N",
                               help="keep the last N rounds out of the export (default 5)")
    journal_group.add_argument("--title", default=None, metavar="T",
                               help="journal title (default: Journal)")
    journal_group.add_argument("--summary", default=None, metavar="FILE",
                               help="text file whose body becomes the Summary section")

    maintain_group = parser.add_argument_group("maintain")
    maintain_group.add_argument("--merge-into", default=None, metavar="ID",
                                help="move archived rounds into this agent id")
    maintain_group.add_argument("--sources", nargs="+", default=None, metavar="ID",
                                help="agent ids to move rounds from")
    maintain_group.add_argument("--delete-id", default=None, metavar="ID",
                                help="move an agent id's data to the trash")
    maintain_group.add_argument("--start-time", default=None, metavar="WHEN")
    maintain_group.add_argument("--end-time", default=None, metavar="WHEN")
    return parser


def main(argv: list[str] | None = None) -> None:
    from src.quick_access import ensure_quietly

    _default_sigpipe()
    ensure_quietly()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["resolve"]:
        from src.paths import project_root

        print(project_root().name)
        return

    parser = build_parser()
    args = parser.parse_args(argv)
    agent_id = (args.agent_id or "").strip() or None
    raise SystemExit(dispatch(parser, args, agent_id))


def dispatch(parser: argparse.ArgumentParser, args, agent_id: str | None) -> int:
    """Run the one requested command; flags are checked in a fixed order."""
    from src import archive, commands

    if args.delete_id is not None:
        target = (args.delete_id or "").strip()
        return archive.delete(target) if target else Exit.Runtime.MISSING_ID

    if args.merge_into is not None or args.sources is not None:
        target = (args.merge_into or "").strip()
        if not target:
            return Exit.Merge.MISSING_TARGET
        sources = [s.strip() for s in (args.sources or []) if s.strip()]
        if not sources:
            return Exit.Merge.MISSING_SOURCES
        return archive.merge(target, sources, args.start_time, args.end_time)

    if args.set_history_root is not None:
        return set_root(args.set_history_root, args.ide)
    if args.set_session_ide is not None:
        return set_ide(args.set_session_ide)
    if args.detect_history_root:
        return detect_roots()

    if args.sync_session:
        return commands.sync(args.as_json)
    if args.session_log is not None:
        return commands.log(args.session_log)

    if args.archive is not None or args.prune:
        if agent_id is None:
            parser.error("--archive/--prune need --id: the journal is per agent id")
        if args.archive is not None and args.prune:
            parser.error("--archive exports, --prune deletes: run them separately")
        if args.tail < 0:
            parser.error("--tail cannot be negative")
        return journal(args, agent_id)

    if args.ide_context is not None and agent_id is None:
        parser.error("--ide-context needs --id: the unlock token is per agent id")
    if args.ide_context is not None and args.ide_context < 1:
        parser.error("--ide-context ROUNDS must be at least 1")

    if args.ide_context is not None:
        return commands.ide_context(agent_id, args.ide_context, args.since,
                                    args.conversation, args.until, args.out)

    if agent_id is None:
        parser.error("--id is required (see COLDSTART.md to resolve your id)")
    if args.recent is not None:
        archive.print_recent(agent_id, args.recent)
        return Exit.OK

    from src.round import run

    return run(agent_id)


# ---------------------------------------------------------------- store setup


def journal(args, agent_id: str) -> int:
    """`--archive` writes a file; `--prune` is the only thing that moves rounds."""
    from src import config
    from src import journal as journal_mod
    from src.gate import parse_when

    try:
        since = parse_when(args.since) if args.since else None
        until = parse_when(args.until) if args.until else None
        if args.prune:
            payload = journal_mod.prune(
                agent_id, since=since, until=until, tail=args.tail
            )
        else:
            payload = journal_mod.export(
                agent_id, args.archive,
                since=since, until=until, tail=args.tail,
                title=args.title, summary_path=args.summary,
            )
    except (journal_mod.JournalError, config.ConfigError, OSError) as exc:
        return commands_fail(exc)
    print(journal_mod.dump(payload))
    return Exit.OK


def set_root(raw: str, ide: str | None) -> int:
    from src import config

    try:
        path = config.set_history_root(raw, ide)
    except (config.ConfigError, KeyError) as exc:
        return commands_fail(exc)
    print(f"{config.session_ide()} {path}")
    return Exit.OK


def set_ide(ide: str) -> int:
    from src import config

    try:
        key = config.set_session_ide(ide)
    except (config.ConfigError, KeyError) as exc:
        return commands_fail(exc)
    print(key)
    return Exit.OK


def detect_roots() -> int:
    from src.ide import registry

    found = registry.detect()
    if not found:
        print("contact-user: no transcript store found", file=sys.stderr)
        for ide in registry.ide_ids():
            print(f"{ide}: {registry.STORES[ide].setup_hint()}", file=sys.stderr)
        return 2
    for ide, path in found:
        print(f"{ide}\t{path}")
    return Exit.OK


def commands_fail(exc: Exception) -> int:
    print(f"contact-user: {exc}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    main()
