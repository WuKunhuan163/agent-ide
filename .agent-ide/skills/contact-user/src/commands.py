"""The read-only commands: the pre-report view and the transcript mirror.

One function per flag. Each returns an exit code and prints through
`session.emit`, so `--out` behaves the same everywhere.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime

from . import config, session
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
                until_raw=None, out=None) -> int:
    """Print the last `rounds` rounds untruncated, then unlock one round.

    With no `--conversation`, the id's registered binding stands in for it: a
    pair registered once with `--bind-conversation` is what every later read
    uses. A bound read is the whole of that id's context, so it reports
    `scope=all` and unlocks the round; an explicit `--conversation` still
    narrows and stays locked.
    """
    bound = False
    try:
        store, since, until = _open(since_raw, until_raw)
        spec = conversation or (config.binding(agent_id) if agent_id else None)
        bound = bool(spec) and not conversation
        conv = session.resolve_conversation(store, spec) if spec else None
        if since is None:
            since = session.rounds_start(store, rounds, conv)
        if since_raw:
            window = f"--since {since_raw}"
        elif bound:
            window = f"last {rounds} rounds of bound {conv.name if conv else spec}"
        else:
            window = f"last {rounds} rounds"
        view = _select(store, since, until, conv)
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

    scope = "all" if conv is None or bound else f"conversation:{store.label(conv)}"
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