"""The read-only commands: the pre-report view and the transcript mirror.

One function per flag. Each returns an exit code and prints through
`session.emit`, so `--out` behaves the same everywhere.
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime

from . import config, probe, session
from .gate import anchor_line, parse_when, write_token
from .ide.base import SessionStore


def fail(message: str) -> int:
    """Errors go to stderr in the `tool: message` form, so stdout stays data."""
    print(f"contact-user: {message}", file=sys.stderr)
    return 2


def _open(since_raw, until_raw) -> tuple[SessionStore, datetime | None, datetime | None]:
    store = config.make_store()
    return (
        store,
        parse_when(since_raw) if since_raw else None,
        parse_when(until_raw) if until_raw else None,
    )


def _select(store, since, until, conv):
    """The `(conversation, messages)` view, optionally narrowed to one."""
    if conv is None:
        return session.window(store, since, until)
    messages = [m for m in store.read_messages(conv, since) if until is None or m.at is None or m.at <= until]
    return [(conv, messages)]


# ------------------------------------------------------------------- the view


def ide_context(agent_id, rounds=100, since_raw=None, conversation=None,
                until_raw=None, out=None, allow_store=False, fix=False) -> int:
    """Print the last `rounds` rounds untruncated, then unlock one round.

    Every read is preceded by a probe (``src/probe.py``) that decides whether the
    binding actually names a conversation of *this* directory. The old behaviour --
    no binding, so read the whole store and call it `scope=all` -- is refused,
    because it silently mixed projects and made later claims unattributable.
    `--all-store` is the explicit way to ask for that wider read.
    """
    bound = False
    try:
        store, since, until = _open(since_raw, until_raw)
        spec_agent = config.binding(agent_id) if agent_id else None
        report = probe.inspect(store, agent_id, spec_agent)
        probe.announce(report)

        if fix and not conversation and not report.readable:
            if not report.candidates:
                return fail(f"no candidate to bind ({report.reason})")
            chosen = report.candidates[0]
            config.set_binding(agent_id, chosen.name)
            print(f"contact-user: bound {agent_id} -> {chosen.short}", file=sys.stderr)
            report = probe.inspect(store, agent_id, chosen.name)
            probe.announce(report)

        if conversation:
            spec, bound = conversation, False
        elif report.bound_spec and report.readable:
            spec, bound = report.bound_spec, True
        elif allow_store:
            spec, bound = None, False
        elif report.state == "unbound":
            return fail(
                f"refusing to read: no conversation is bound to {agent_id!r}.\n"
                "An unbound read returns every conversation in the store, which is "
                "not this id's context.\n"
                f"{probe.candidates_text(report)}\n{probe.hint(report)}"
            )
        else:
            return fail(
                f"refusing to read: {report.reason}\n"
                f"{probe.candidates_text(report)}\n{probe.hint(report)}"
            )

        conv = session.resolve_conversation(store, spec) if spec else None
        if since is None:
            since = session.rounds_start(store, rounds, conv)
        if since_raw:
            window = f"--since {since_raw}"
        elif bound and report.bound is not None:
            window = f"last {rounds} rounds of bound {report.bound.short}"
        elif conv is None:
            window = f"last {rounds} rounds of every conversation in the store"
        else:
            window = f"last {rounds} rounds of {conv.name[:8]}"
        view = _select(store, since, until, conv)

        extra_specs = config.extras(agent_id) if agent_id else []
        if extra_specs:
            merged = list(view)
            have = {c.name for c, _ in merged}
            for spec_extra in extra_specs:
                try:
                    extra = session.resolve_conversation(store, spec_extra)
                except LookupError:
                    print(
                        f"contact-user: [WARN] extra conversation {spec_extra[:8]} "
                        f"is not in this store any more",
                        file=sys.stderr,
                    )
                    continue
                if extra.name in have:
                    continue
                messages = [
                    m for m in store.read_messages(extra, since)
                    if until is None or m.at is None or m.at <= until
                ]
                if messages:
                    merged.append((extra, messages))
                    have.add(extra.name)
            merged.sort(
                key=lambda pair: min(
                    (m.at for m in pair[1] if m.at is not None), default=datetime.min
                )
            )
            view = merged
            window += f" + {len(extra_specs)} extra"
    except (config.ConfigError, LookupError) as exc:
        return fail(exc)

    text = session.render(store, since, until=until, view=view)
    session.emit(text, out)

    if out:
        # Export only. A token minted here would let a report open without the
        # text ever passing through the conversation, which is the one thing
        # this gate exists to prevent.
        print(
            f"contact-user: exported, round NOT unlocked "
            f"(read the file, then run --ide-context on stdout)",
            file=sys.stderr,
        )
        return 0

    if conv is None:
        scope = "all-store"
    elif bound:
        scope = "all"
    else:
        scope = f"conversation:{store.label(conv)}"
    token = write_token(
        agent_id, ide=store.ide_id, store=str(store.root), since=since, until=until,
        window=window, scope=scope, conversations=len(view),
        messages=sum(len(messages) for _, messages in view), text=text,
    )
    if scope == "all":
        print(anchor_line(token))
    size = session.human_size(token["chars"])
    if scope == "all":
        print(f"contact-user: unlocked {token['messages']} msgs {size}", file=sys.stderr)
    else:
        print(
            f"contact-user: narrowed read, round locked (scope {scope}, "
            f"{token['messages']} msgs {size})",
            file=sys.stderr,
        )
    return 0



# ------------------------------------------------------------- id ↔ conv pair


def bind(agent_id: str, spec: str) -> int:
    """Register `agent_id -> conversation` once; later reads use it by default."""
    try:
        store = config.make_store()
        conv = session.resolve_conversation(store, spec)
    except (config.ConfigError, LookupError) as exc:
        return fail(exc)
    config.set_binding(agent_id, conv.name)
    print(f"{agent_id}\t{conv.name}")
    ws = probe.workspace_of(store, conv)
    if ws and not probe._same_place(ws, os.getcwd()):
        print(
            f"contact-user: [WARN] {conv.name[:8]} records workspace {ws}, "
            f"which is not {os.getcwd()} -- reads will be refused as mismatched",
            file=sys.stderr,
        )
    return 0


def unbind(agent_id: str) -> int:
    if not config.clear_binding(agent_id):
        return fail(f"no conversation bound to {agent_id!r}")
    print(f"{agent_id}\t-")
    return 0


def list_bindings() -> int:
    table = config.bindings()
    if not table:
        print("(no bindings)")
        return 0
    known: set[str] | None = None
    try:
        known = {conv.name for conv in config.make_store().conversations()}
    except config.ConfigError:
        known = None
    for agent_id, conv_id in sorted(table.items()):
        mark = "" if known is None or conv_id in known else "  (missing)"
        print(f"{agent_id}\t{conv_id}{mark}")
    return 0


def add_extras(agent_id: str, specs: list[str]) -> int:
    """`--with-conversation`: read these alongside the bound one."""
    try:
        store = config.make_store()
    except config.ConfigError as exc:
        return fail(exc)
    for spec in specs:
        try:
            conv = session.resolve_conversation(store, spec)
        except LookupError as exc:
            return fail(exc)
        config.add_extra(agent_id, conv.name)
        print(f"{agent_id}\t+{conv.name}")
    return 0


def clear_extras(agent_id: str) -> int:
    if not config.clear_extras(agent_id):
        return fail(f"no extra conversations for {agent_id!r}")
    print(f"{agent_id}\t-")
    return 0


def list_extras(agent_id: str) -> int:
    items = config.extras(agent_id)
    if not items:
        print(f"({agent_id}: no extras)")
        return 0
    for item in items:
        print(f"{agent_id}\t+{item}")
    return 0


# --------------------------------------------------------------------- mirror


def sync(as_json: bool = False) -> int:
    from . import session_mirror

    try:
        store = config.make_store()
        result = session_mirror.sync(store)
    except (config.ConfigError, RuntimeError) as exc:
        return fail(exc)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(
        f"+{result['added']} msgs {result['messages']} total "
        f"{result['conversations']} convs "
        f"{'committed' if result['committed'] else 'clean'}"
    )
    return 0


def log(n: int = 10) -> int:
    from . import session_mirror

    print(session_mirror.log(n) or "(no commits yet)")
    return 0