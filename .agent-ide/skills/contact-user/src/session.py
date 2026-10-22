"""Reading a session store: windows, rendering, and inventory.

Two render modes, and the difference is the point:

* window (`full=False`) — the `--changes` orientation view: assistant text
  verbatim, one line per tool call, results and reasoning behind flags.
* full (`full=True`) — the pre-report view: every message, reasoning, tool
  arguments and tool output untruncated, no cap. Nothing is elided, because
  this view exists to restore context that compaction may have dropped.
"""
from __future__ import annotations
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .ide.base import Message, SessionStore, ToolCall, clip, iso

RESULT_PREVIEW = 600
REASONING_PREVIEW = 1200
ARG_KEYS = ("command", "filePath", "path", "pattern", "query", "url", "prompt")


# ------------------------------------------------------------------- rendering


def window(
    store: SessionStore, since: datetime | None, until: datetime | None = None
) -> list[tuple[Path, list[Message]]]:
    """Conversations with messages in `[since, until]`, plus those messages.

    A conversation whose own mtime is older than the window costs two stats and
    is skipped without opening a single message file.
    """
    cutoff = since.timestamp() - 300 if since else None
    found: list[tuple[Path, list[Message]]] = []
    for conv in store.conversations():
        if cutoff is not None and store.last_write_time(conv) < cutoff:
            continue
        messages = store.read_messages(conv, since)
        if until is not None:
            messages = [m for m in messages if m.at is None or m.at <= until]
        if messages:
            found.append((conv, messages))
    return found


def render(
    store: SessionStore,
    since: datetime | None,
    *,
    until: datetime | None = None,
    full: bool = False,
    with_tools: bool = False,
    with_reasoning: bool = False,
    max_messages: int = 0,
    view: list[tuple[Path, list[Message]]] | None = None,
) -> str:
    if full:
        with_tools = with_reasoning = True
        max_messages = 0

    conversations = view if view is not None else window(store, since, until)
    total = sum(len(messages) for _, messages in conversations)
    if not total:
        return f"no messages since {iso(since) if since else 'the beginning'}"

    head = f"# since={iso(since) if since else '-'} convs={len(conversations)} msgs={total}"
    if until is not None:
        head += f" until={iso(until)}"
    lines = [head, ""]

    for conv, messages in conversations:
        shown = messages[-max_messages:] if max_messages else messages
        lines.append(f"## {store.label(conv)} {len(messages)} msgs")
        if len(shown) < len(messages):
            lines.append(f"# last {len(shown)} of {len(messages)}")
        lines.append("")
        for message in shown:
            block = _render_message(message, full, with_tools, with_reasoning)
            if block:
                lines.extend(block)
    return "\n".join(lines)


def _render_message(
    message: Message, full: bool, with_tools: bool, with_reasoning: bool
) -> list[str]:
    has_body = bool(message.text or message.calls)
    if not has_body and not (with_tools and message.results) and not (
        with_reasoning and message.reasoning
    ):
        return []

    stamp = message.at.astimezone().strftime("%H:%M:%S") if message.at else "??:??:??"
    lines = [f"### [{stamp}] {message.role or 'unknown'}"]
    if with_reasoning and message.reasoning:
        lines.append("_reasoning_:")
        lines.append(message.reasoning if full else clip(message.reasoning, REASONING_PREVIEW))
    if message.text:
        lines.append(message.text)
    for call in message.calls:
        if full:
            lines.append(f"  - tool `{call.name}` args: {json.dumps(call.args, ensure_ascii=False)}")
        else:
            lines.append(f"  - tool `{call.name}`: {_arg_summary(call)}")
    if with_tools:
        for result in message.results:
            body = result.text if full else clip(result.text, RESULT_PREVIEW)
            if body:
                flag = "ERROR" if result.is_error else result.status
                lines.append(f"  - result `{result.name}` [{flag}]: {body}")
    lines.append("")
    return lines


def _arg_summary(call: ToolCall) -> str:
    args = call.args or {}
    for key in ARG_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return clip(value, 240)
    return clip(json.dumps(args, ensure_ascii=False), 240)


def messages_json(messages: list[Message]) -> list[dict]:
    """Structured form for `--json` callers."""
    return [
        {
            "id": m.mid,
            "role": m.role,
            "at": iso(m.at) if m.at else None,
            "text": m.text,
            "reasoning": m.reasoning,
            "calls": [{"name": c.name, "args": c.args} for c in m.calls],
            "results": [
                {"name": r.name, "status": r.status, "isError": r.is_error, "output": r.text}
                for r in m.results
            ],
        }
        for m in messages
    ]


# ------------------------------------------------------------------- inventory


@dataclass(frozen=True)
class Conversation:
    id: str
    first: str
    last: str
    messages: int
    text_chars: int = 0
    reasoning_chars: int = 0
    tool_chars: int = 0
    tools: int = 0
    measured: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "first": self.first,
            "last": self.last,
            "messages": self.messages,
            "text_chars": self.text_chars,
            "reasoning_chars": self.reasoning_chars,
            "tool_chars": self.tool_chars,
            "tools": self.tools,
        }


def resolve_conversation(store: SessionStore, spec: str) -> Path:
    """A conversation directory from an id, an id prefix, or `latest`."""
    convs = store.conversations()
    if not convs:
        raise LookupError(f"no conversations in {store.root}")
    key = (spec or "").strip()
    if key in ("", "latest", "newest", "current"):
        newest = store.newest_conversation()
        if newest is None:
            raise LookupError(f"no conversations in {store.root}")
        return newest
    exact = [conv for conv in convs if conv.name == key]
    if exact:
        return exact[0]
    matches = [conv for conv in convs if conv.name.startswith(key)]
    if not matches:
        raise LookupError(
            f"no conversation matching {spec!r} among {len(convs)} "
            f"(use --session-list to see them)"
        )
    return max(matches, key=store.last_write_time)


def describe(
    store: SessionStore,
    conv: Path,
    since: datetime | None = None,
    until: datetime | None = None,
    *,
    measure: bool = True,
) -> Conversation:
    files = store.message_files(conv)
    if not measure:
        # Cheap mode: one stat walk, then parse only the two boundary files,
        # so the dates are real without opening 137k message files.
        stamped = []
        for path in files:
            try:
                stamped.append((path.stat().st_mtime, path))
            except OSError:
                continue
        if not stamped:
            return Conversation(id=store.label(conv), first="?", last="?", messages=0)
        first = store.parse_file(min(stamped)[1])
        last = store.parse_file(max(stamped)[1])
        return Conversation(
            id=store.label(conv),
            first=iso(first.at) if first else "?",
            last=iso(last.at) if last else "?",
            messages=len(files),
        )
    messages = store.read_messages(conv, since)
    if until is not None:
        messages = [m for m in messages if m.at is None or m.at <= until]
    stamps = [m.at for m in messages if m.at]
    return Conversation(
        id=store.label(conv),
        first=iso(min(stamps)) if stamps else "?",
        last=iso(max(stamps)) if stamps else "?",
        messages=len(messages),
        text_chars=sum(len(m.text) for m in messages),
        reasoning_chars=sum(len(m.reasoning) for m in messages),
        tool_chars=sum(len(r.text) for m in messages for r in m.results),
        tools=sum(len(m.calls) for m in messages),
        measured=True,
    )


def inventory(
    store: SessionStore,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 0,
) -> list[Conversation]:
    """Per-conversation summary, oldest first.

    Bodies are parsed only when a window was asked for; a whole-store listing
    takes its counts from the message directory instead.
    """
    measure = since is not None or until is not None
    rows = [
        describe(store, conv, since, until, measure=measure)
        for conv in store.conversations()
    ]
    rows = [row for row in rows if row.messages]
    rows.sort(key=lambda r: r.last)
    return rows[-limit:] if limit else rows


def months(store: SessionStore, exact: bool = False) -> list[tuple[str, int]]:
    """Messages per `YYYY-MM`.

    Cheap mode buckets by message-file write time (one stat per file); `exact`
    parses every message and uses its own timestamp.
    """
    counts: dict[str, int] = {}
    for conv in store.conversations():
        if exact:
            for message in store.read_messages(conv):
                key = message.at.strftime("%Y-%m") if message.at else "unknown"
                counts[key] = counts.get(key, 0) + 1
            continue
        for path in store.message_files(conv):
            try:
                key = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m")
            except OSError:
                continue
            counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items())


def store_summary(store: SessionStore) -> dict:
    """Conversations, messages, bytes and last activity, in one stat walk."""
    conversations = store.conversations()
    messages = 0
    size = 0
    newest = 0.0
    for conv in conversations:
        for path in store.message_files(conv):
            try:
                stat = path.stat()
            except OSError:
                continue
            messages += 1
            size += stat.st_size
            newest = max(newest, stat.st_mtime)
    return {
        "conversations": len(conversations),
        "messages": messages,
        "size": size,
        "newest": (
            iso(datetime.fromtimestamp(newest, tz=timezone.utc)) if newest else "?"
        ),
    }


def format_inventory(rows: list[Conversation]) -> str:
    """One record per line: `last msgs [text reason tools] conv`."""
    if not rows:
        return ""
    measured = any(row.measured for row in rows)
    width = max(len(row.id) for row in rows)
    lines = []
    for row in rows:
        line = f"{row.last[:16].replace('T', ' ')} {row.messages:>7}"
        if measured:
            line += f" {row.text_chars:>8} {row.reasoning_chars:>8} {row.tools:>5}"
        lines.append(f"{line}  {row.id:<{width}}")
    return "\n".join(lines)


def format_months(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return ""
    return "\n".join(f"{key}  {count}" for key, count in rows)


def human_size(size: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if size < 1024 or unit == "G":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}".replace(".0", "")
        size /= 1024
    return f"{size:.1f}G"


# ---------------------------------------------------------------------- output


def emit(text: str, out: str | None = None) -> None:
    """Print, or write the same text to `out` when stdout would be truncated."""
    if not out:
        if not text:
            return
        try:
            print(text if text.endswith("\n") else text + "\n", end="")
        except BrokenPipeError:  # a closed pipe is not an error of this tool
            pass
        return
    path = Path(out).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"contact-user: -> {path} {human_size(len(text))}", file=sys.stderr)


def emit_json(payload, out: str | None = None) -> None:
    emit(json.dumps(payload, ensure_ascii=False, indent=2), out)
