"""The IDE-neutral half of session reading.

An IDE differs in where conversations live, how a message file is shaped, and
how role/timestamp are spelled. Everything else — ordering, window filtering —
is the same for all of them, so it lives here.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict


@dataclass(frozen=True)
class ToolResult:
    name: str
    is_error: bool
    status: str
    text: str  # full payload; the renderer decides how much to show


@dataclass(frozen=True)
class Message:
    mid: str
    role: str
    at: datetime | None
    text: str = ""
    reasoning: str = ""
    calls: tuple[ToolCall, ...] = ()
    results: tuple[ToolResult, ...] = ()
    extra: dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.text.strip() or self.reasoning.strip() or self.calls or self.results)


def parse_ts(value) -> datetime | None:
    """Timestamp spellings in transcripts: epoch seconds/ms, ISO 8601 with or
    without a zone. Always returned as aware UTC."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000.0 if value > 1e11 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    if raw.isdigit():
        return parse_ts(int(raw))
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime | None) -> str:
    """One timestamp spelling for all output: `2026-10-22T09:56:36Z`."""
    if value is None:
        return "?"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clip(text: str, limit: int) -> str:
    """Flatten to one line and cut at `limit` characters (0 = no cut)."""
    flat = " ".join(str(text).split())
    if limit <= 0 or len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


class SessionStore(ABC):
    """One IDE's transcript store, rooted at an absolute path."""

    ide_id: str = ""
    display_name: str = ""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ------------------------------------------------------- per-IDE contracts

    @abstractmethod
    def conversations(self) -> list[Path]:
        """Conversation directories, oldest first."""

    @abstractmethod
    def message_files(self, conv: Path) -> list[Path]:
        """Every message file of one conversation."""

    @abstractmethod
    def parse_file(self, path: Path) -> Message | None:
        """One message file -> Message, or None when unreadable."""

    @classmethod
    @abstractmethod
    def discover(cls) -> list[Path]:
        """Candidate roots in this IDE's well-known locations."""

    @classmethod
    @abstractmethod
    def setup_hint(cls) -> str:
        """How to find the root by hand, for the first-start message."""

    # ------------------------------------------------------------- shared part

    def label(self, conv: Path) -> str:
        return conv.name

    @classmethod
    def validate_root(cls, root: Path) -> bool:
        if not root.is_dir():
            return False
        try:
            return bool(cls(root).conversations())
        except OSError:
            return False

    def last_write_time(self, conv: Path) -> float:
        """Newest mtime among the entries that move when a message arrives."""
        newest = 0.0
        for path in (conv / "index.json", conv / "messages"):
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                continue
        return newest

    def newest_conversation(self) -> Path | None:
        convs = self.conversations()
        return max(convs, key=self.last_write_time) if convs else None

    def read_messages(
        self, conv: Path, since: datetime | None = None, margin_secs: int = 120
    ) -> list[Message]:
        """Chronological messages of one conversation, filtered by timestamp.

        File mtime is only a cheap pre-filter (with a margin): the authoritative
        filter is the message's own timestamp, so a file written late but
        stamped early is still included.
        """
        cutoff = since.timestamp() - margin_secs if since else None
        out: list[Message] = []
        for path in self.message_files(conv):
            if cutoff is not None:
                try:
                    if path.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
            message = self.parse_file(path)
            if message is None or message.is_empty:
                continue
            if since and message.at and message.at < since:
                continue
            out.append(message)
        out.sort(key=lambda m: (m.at or datetime.min.replace(tzinfo=timezone.utc), m.mid))
        return out
