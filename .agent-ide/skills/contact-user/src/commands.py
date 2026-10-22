"""The read-only commands: inventory, reads, and the pre-report view.

One function per flag. Each returns an exit code and prints through
`session.emit`, so `--out` behaves the same everywhere.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime

from . import config, session
from .gate import parse_when, read_marker, read_token, window_start, write_token
from .ide.base import SessionStore, iso


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


def _select(store, since, until, conversation):
    """The `(conversation, messages)` view, optionally narrowed to one."""
    if not conversation:
        return session.window(store, since, until)
    conv = session.resolve_conversation(store, conversation)
    messages = [m for m in store.read_messages(conv, since) if until is None or m.at is None or m.at <= until]
    return [(conv, messages)]


# ------------------------------------------------------------------ inventory


def session_list(limit=0, since_raw=None, until_raw=None, as_json=False, out=None) -> int:
    try:
        store, since, until = _open(since_raw, until_raw)
    except config.ConfigError as exc:
        return fail(exc)
    rows = session.inventory(store, since, until, limit)
    if as_json:
        session.emit_json(
            {"ide": store.ide_id, "root": str(store.root),
             "conversations": [row.as_dict() for row in rows]},
            out,
        )
        return 0
    session.emit(session.format_inventory(rows), out)
    return 0


def session_months(exact=False, as_json=False, out=None) -> int:
    try:
        store = config.make_store()
    except config.ConfigError as exc:
        return fail(exc)
    rows = session.months(store, exact)
    if as_json:
        session.emit_json(
            {"ide": store.ide_id, "root": str(store.root),
             "basis": "message timestamp" if exact else "file write time",
             "months": [{"month": key, "messages": count} for key, count in rows]},
            out,
        )
        return 0
    session.emit(session.format_months(rows), out)
    return 0


# ---------------------------------------------------------------------- reads


def session_read(spec, since_raw=None, until_raw=None, *, with_tools=False,
                 with_reasoning=False, full=False, as_json=False, out=None) -> int:
    try:
        store, since, until = _open(since_raw, until_raw)
        conv = session.resolve_conversation(store, spec)
    except config.ConfigError as exc:
        return fail(exc)
    except LookupError as exc:
        return fail(exc)

    messages = [
        m for m in store.read_messages(conv, since) if until is None or m.at is None or m.at <= until
    ]
    if as_json:
        session.emit_json(
            {"ide": store.ide_id, "conversation": store.label(conv),
             "since": iso(since) if since else None,
             "until": iso(until) if until else None,
             "messages": session.messages_json(messages)},
            out,
        )
        return 0
    session.emit(
        session.render(store, since, until=until, full=full, view=[(conv, messages)],
                       with_tools=with_tools, with_reasoning=with_reasoning),
        out,
    )
    return 0


def changes(agent_id, since_raw=None, max_messages=0, *, with_tools=False,
            with_reasoning=False, conversation=None, until_raw=None, out=None) -> int:
    try:
        store, since, until = _open(since_raw, until_raw)
        if since is None:
            since, _ = window_start(agent_id, None, first_hours=None)
        view = _select(store, since, until, conversation)
    except (config.ConfigError, LookupError) as exc:
        return fail(exc)
    session.emit(
        session.render(store, since, until=until, view=view, max_messages=max_messages,
                       with_tools=with_tools, with_reasoning=with_reasoning),
        out,
    )
    return 0


def ide_context(agent_id, since_raw=None, conversation=None, until_raw=None, out=None) -> int:
    """Print the whole window untruncated, then unlock one round."""
    try:
        store, since, until = _open(since_raw, until_raw)
        window = f"--since {since_raw}" if since_raw else "since the previous round"
        if since is None:
            since, window = window_start(agent_id, None, first_hours=24)
        view = _select(store, since, until, conversation)
    except (config.ConfigError, LookupError) as exc:
        return fail(exc)

    text = session.render(store, since, until=until, full=True, view=view)
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

    scope = f"conversation:{store.label(view[0][0])}" if conversation else "all"
    token = write_token(
        agent_id, ide=store.ide_id, store=str(store.root), since=since, until=until,
        window=window, scope=scope, conversations=len(view),
        messages=sum(len(messages) for _, messages in view), text=text,
    )
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


# --------------------------------------------------------------------- status


def status(agent_id: str | None) -> int:
    try:
        store = config.make_store()
    except config.ConfigError as exc:
        return fail(exc)

    summary = session.store_summary(store)
    print(
        f"ide={store.ide_id} convs={summary['conversations']} "
        f"msgs={summary['messages']} size={session.human_size(summary['size'])} "
        f"newest={summary['newest']} mirror={'on' if config.mirror_enabled() else 'off'}"
    )
    print(f"store={store.root}")
    if agent_id:
        marker = read_marker(agent_id)
        token = read_token(agent_id)
        state = (
            f"token={token['at']} scope={token.get('scope') or 'all'} "
            f"delivery={token.get('delivery') or 'stdout'}"
            if token else "token=none (round blocked)"
        )
        print(f"round={iso(marker) if marker else '-'} {state}")
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
