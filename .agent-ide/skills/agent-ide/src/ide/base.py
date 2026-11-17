"""The IDE-neutral half of session reading.

An IDE differs in where conversations live, how a message file is shaped, and
how role/timestamp are spelled. Everything else — ordering, window filtering —
is the same for all of them, so it lives here.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import bisect
import os
import time
import sys
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


PROGRESS_MARKS = (0.01, 0.02, 0.05, 0.10, 0.20, 0.50)


class Progress:
    """The one progress reporter a long scan uses.

    Prints the first item, then the 1/2/5/10/20/50% marks, then the last item,
    on stderr; stdout stays the rendered text. A second reporter anywhere else
    is a fork of this one — every scan calls `tick` and nothing prints its own.
    """

    def __init__(self, total: int, label: str) -> None:
        self.total = total
        self.label = label
        self.marks = [max(1, int(total * m)) for m in PROGRESS_MARKS]
        self.marks.append(total)
        self.index = 0
        self.t0 = time.monotonic()

    def tick(self, done: int, extra: str = "") -> None:
        first = done == 1
        reached = self.index < len(self.marks) and done >= self.marks[self.index]
        if not (first or reached):
            return
        if reached:
            self.index += 1
        pct = done / self.total if self.total else 1.0
        tail = f"  {extra}" if extra else ""
        print(f"\r{self.label}: {pct:4.0%} ({done}/{self.total}) "
              f"{time.monotonic() - self.t0:5.1f}s{tail}",
              end="\n" if done >= self.total else "",
              file=sys.stderr, flush=True)


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

    def _stamped(self, conv: Path) -> list[tuple[float, Path]]:
        """Message files with their mtime, sorted oldest first.

        One `scandir` + `stat` pass. Measured on a 110k-file conversation:
        0.6 s to list, 3.5 s to stat them all cold (0.7 s warm). Parsing the
        same set is 28 s, so the whole point of this pass is to decide what
        *not* to parse.
        """
        out: list[tuple[float, Path]] = []
        folder = conv / "messages"
        if not folder.is_dir():
            return out
        with os.scandir(folder) as it:
            for entry in it:
                if not entry.name.endswith(".json"):
                    continue
                try:
                    out.append((entry.stat().st_mtime, Path(entry.path)))
                except OSError:
                    continue
        out.sort(key=lambda pair: pair[0])
        return out

    def read_messages(
        self,
        conv: Path,
        since: datetime | None = None,
        margin_secs: int = 120,
        until: datetime | None = None,
        tail: int | None = None,
    ) -> list[Message]:
        """Chronological messages of one conversation, filtered by timestamp.

        Only the files that can contribute are parsed. mtime decides the
        candidate window -- it tracks the message timestamp to within seconds,
        and the authoritative filter is still the message's own `at`, so a file
        written late but stamped early stays included.

        `tail` is a hint from `--last N`: N messages that survive filtering are
        wanted from the end, so parsing starts at the end and walks backwards
        until N are in hand. It is a hint, not a contract -- the caller still
        slices.
        """
        stamped = self._stamped(conv)
        if not stamped:
            return []

        lo, hi = 0, len(stamped)
        if since is not None or until is not None:
            mtimes = [m for m, _ in stamped]
            if since is not None:
                lo = bisect.bisect_left(mtimes, since.timestamp() - margin_secs)
            if until is not None:
                hi = bisect.bisect_right(mtimes, until.timestamp() + margin_secs)
            hi = max(hi, lo)

        if tail and since is None and until is None:
            # Start with a generous block: many files are tool results that
            # filter out, so N files yield well under N messages.
            want = max(tail * 4 + 50, tail)
            start = max(lo, len(stamped) - want)
            while True:
                msgs = self._parse_span(stamped, start, len(stamped), None, until)
                if len(msgs) >= tail or start == 0:
                    return msgs
                start = max(0, start - want)
                # Guard against a conversation whose newest files are all
                # empty: widen, but do not re-parse the same span twice.
                if start == 0:
                    return msgs

        return self._parse_span(stamped, lo, hi, since, until)

    def _parse_span(
        self,
        stamped: list[tuple[float, Path]],
        lo: int,
        hi: int,
        since: datetime | None,
        until: datetime | None,
    ) -> list[Message]:
        out: list[Message] = []
        span = hi - lo
        # Parsing is the expensive half (0.25 ms per file, 28 s over 110k).
        # A silent 28 s looks like a hang, so show the count when it is long
        # enough to matter. stderr only: stdout stays the rendered text.
        progress = Progress(span, "read") if span >= 2000 else None
        for done, (_, path) in enumerate(stamped[lo:hi], 1):
            message = self.parse_file(path)
            if message is None or message.is_empty:
                continue
            if since and message.at and message.at < since:
                continue
            if until and message.at and message.at > until:
                continue
            out.append(message)
            if progress:
                progress.tick(done, f"{len(out)} kept")
        if progress:
            progress.tick(span, f"{len(out)} kept")
        out.sort(key=lambda m: (m.at or datetime.min.replace(tzinfo=timezone.utc), m.mid))
        return out
