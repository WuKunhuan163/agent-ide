"""Reading a session store: windows and rendering.

One render mode — the pre-report view: every message, reasoning, tool arguments
and tool output untruncated, no cap. Nothing is elided, because this view exists
to restore context that compaction may have dropped.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .ide.base import Message, SessionStore, iso


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
    view: list[tuple[Path, list[Message]]] | None = None,
) -> str:
    conversations = view if view is not None else window(store, since, until)
    total = sum(len(messages) for _, messages in conversations)
    if not total:
        return f"no messages since {iso(since) if since else 'the beginning'}"

    head = f"# since={iso(since) if since else '-'} convs={len(conversations)} msgs={total}"
    if until is not None:
        head += f" until={iso(until)}"
    lines = [head, ""]

    for conv, messages in conversations:
        lines.append(f"## {store.label(conv)} {len(messages)} msgs")
        lines.append("")
        for message in messages:
            lines.extend(_render_message(message))
    return "\n".join(lines)


def rounds_start(
    store: SessionStore, rounds: int, conversation: Path | None = None
) -> datetime | None:
    """Timestamp of the `rounds`-th most recent user message.

    A round opens with a user message, so counting them backwards gives a window
    measured in conversation rather than in wall-clock time: a project left
    alone for a week still reads its last rounds, untouched.
    """
    conversations = [conversation] if conversation is not None else store.conversations()
    stamped: list[tuple[float, Path]] = []
    for conv in conversations:
        for path in store.message_files(conv):
            try:
                stamped.append((path.stat().st_mtime, path))
            except OSError:
                continue
    stamped.sort(reverse=True)

    seen = 0
    for _, path in stamped:
        message = store.parse_file(path)
        if message is None or message.role != "user" or message.at is None:
            continue
        seen += 1
        if seen >= rounds:
            return message.at
    return None


def _render_message(message: Message) -> list[str]:
    if not (message.text or message.calls or message.results or message.reasoning):
        return []

    stamp = message.at.astimezone().strftime("%H:%M:%S") if message.at else "??:??:??"
    lines = [f"### [{stamp}] {message.role or 'unknown'}"]
    if message.reasoning:
        lines.append("_reasoning_:")
        lines.append(message.reasoning)
    if message.text:
        lines.append(message.text)
    for call in message.calls:
        lines.append(f"  - tool `{call.name}` args: {json.dumps(call.args, ensure_ascii=False)}")
    for result in message.results:
        if result.text:
            flag = "ERROR" if result.is_error else result.status
            lines.append(f"  - result `{result.name}` [{flag}]: {result.text}")
    lines.append("")
    return lines


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
            f"(use --detect-history-root to see the store)"
        )
    return max(matches, key=store.last_write_time)


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