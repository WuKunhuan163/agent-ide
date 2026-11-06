"""Probe the store before a read: which conversation does this id actually mean?

The failure this module exists for is silent and expensive. With no binding, the
old read fell back to *every* conversation in the store and reported `scope=all`,
so an agent that asked for "this id's context" received several projects mixed
together and drew conclusions from them. The binding was not missing because it
was broken; it was missing because nothing checked it before the export.

So every read now starts here:

1. enumerate the store -- how many conversations, how many messages, what span;
2. resolve the binding, if any, and decide its state:

   ``ok``        bound, present, non-empty, and the conversation's own
                 ``Workspace Folder`` agrees with the current directory;
   ``unknown``   bound and present, but no workspace was recoverable, so the
                 ownership cannot be confirmed (readable, reported as a warning);
   ``mismatch``  bound and present, but the conversation belongs to another
                 working directory -- reading it would answer a different
                 project's question;
   ``empty``     bound but holding almost no messages, which is what a
                 half-created session leaves behind;
   ``missing``   bound to a conversation that the store no longer holds;
   ``unbound``   no binding at all, which is the state that used to silently
                 widen the read to the whole store.

Only ``ok`` and ``unknown`` are read by default. The rest stop the command and
print the candidates plus the one-line fix, because the alternative -- reading
the wrong history quietly -- is what produced wrong conclusions in the past.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .ide.base import SessionStore, iso

WORKSPACE = re.compile(r"Workspace Folder:\s*([^\n\\\"]+)")
EMPTY_THRESHOLD = 5
SAMPLE = 6


@dataclass(frozen=True)
class ConvInfo:
    conv: Path
    name: str
    files: int
    first: datetime | None
    last: datetime | None
    workspace: str | None = None

    @property
    def short(self) -> str:
        return self.name[:8]


@dataclass(frozen=True)
class Report:
    store_root: str
    ide: str
    conversations: int
    agent_id: str | None
    bound_spec: str | None
    bound: ConvInfo | None
    state: str
    reason: str
    cwd: str
    candidates: tuple[ConvInfo, ...] = ()

    @property
    def readable(self) -> bool:
        return self.state in ("ok", "unknown")


# --------------------------------------------------------------- enumeration


def _stamps(store: SessionStore, conv: Path) -> tuple[int, datetime | None, datetime | None]:
    files = store.message_files(conv)
    times: list[float] = []
    for path in files:
        try:
            times.append(path.stat().st_mtime)
        except OSError:
            continue
    first = datetime.fromtimestamp(min(times)) if times else None
    last = datetime.fromtimestamp(max(times)) if times else None
    return len(files), first, last


def workspace_of(store: SessionStore, conv: Path, limit: int = SAMPLE) -> str | None:
    """The `Workspace Folder` a conversation was opened in, if it recorded one.

    Glob order is not time order, so both ends are sampled: the opening messages
    carry `<user_info>` and the newest ones are the cheapest to trust when a
    session was rotated.
    """
    files = store.message_files(conv)
    if not files:
        return None
    try:
        files.sort(key=lambda p: p.stat().st_mtime)
    except OSError:
        pass
    sample = files[:limit] + files[-limit:]
    for path in sample:
        message = store.parse_file(path)
        if message is None:
            continue
        blob = "\n".join(
            [message.text or "", message.reasoning or ""]
            + [r.text or "" for r in message.results]
        )
        hit = WORKSPACE.search(blob)
        if hit:
            return hit.group(1).strip()
    return None


def survey(store: SessionStore, with_workspace: int = 0) -> list[ConvInfo]:
    """Every conversation, oldest first. `with_workspace` recovers ownership for
    that many of the largest ones (each recovery opens a few files)."""
    rows: list[ConvInfo] = []
    for conv in store.conversations():
        files, first, last = _stamps(store, conv)
        rows.append(ConvInfo(conv=conv, name=conv.name, files=files, first=first, last=last))
    if with_workspace:
        largest = sorted(rows, key=lambda r: r.files, reverse=True)[:with_workspace]
        for row in largest:
            ws = workspace_of(store, row.conv)
            if ws:
                rows[rows.index(row)] = ConvInfo(
                    conv=row.conv, name=row.name, files=row.files,
                    first=row.first, last=row.last, workspace=ws,
                )
    return rows


# ------------------------------------------------------------------ judgement


def _same_place(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    try:
        return os.path.realpath(a) == os.path.realpath(b)
    except OSError:
        return a.rstrip("/") == b.rstrip("/")


def inspect(
    store: SessionStore,
    agent_id: str | None,
    bound_spec: str | None,
    cwd: str | None = None,
) -> Report:
    """Decide whether this id's context is the one that is about to be read."""
    cwd = cwd or os.getcwd()
    rows = survey(store, with_workspace=12)

    def rank(row: ConvInfo) -> tuple:
        """Ownership beats size: a big conversation from another project is the
        wrong answer, and recommending it is how the previous confusion spread."""
        if row.workspace and _same_place(row.workspace, cwd):
            return (0, -row.files)
        if row.workspace is None:
            return (2, -row.files)
        return (3, -row.files)

    if not bound_spec:
        return Report(
            store_root=str(store.root), ide=store.ide_id, conversations=len(rows),
            agent_id=agent_id, bound_spec=None, bound=None,
            state="unbound",
            reason=f"id {agent_id!r} has no conversation binding",
            cwd=cwd,
            candidates=tuple(sorted(rows, key=rank)[:3]),
        )

    match = [r for r in rows if r.name == bound_spec]
    if not match:
        match = [r for r in rows if r.name.startswith(bound_spec)]
    if not match:
        return Report(
            store_root=str(store.root), ide=store.ide_id, conversations=len(rows),
            agent_id=agent_id, bound_spec=bound_spec, bound=None,
            state="missing",
            reason=f"bound conversation {bound_spec[:8]} is not in this store any more",
            cwd=cwd,
            candidates=tuple(sorted(rows, key=lambda r: r.files, reverse=True)[:3]),
        )

    bound = max(match, key=lambda r: r.files)
    if bound.files < EMPTY_THRESHOLD:
        state, reason = "empty", f"bound conversation holds {bound.files} messages"
    elif bound.workspace is None:
        state, reason = "unknown", "bound conversation records no workspace folder"
    elif _same_place(bound.workspace, cwd):
        state, reason = "ok", "bound conversation belongs to this directory"
    else:
        state, reason = (
            "mismatch",
            f"bound conversation belongs to {bound.workspace}, not {cwd}",
        )

    def rank(row: ConvInfo) -> tuple:
        """Ownership beats size: a big conversation from another project is the
        wrong answer, and recommending it is how the previous confusion spread."""
        if row.workspace and _same_place(row.workspace, cwd):
            return (0, -row.files)
        if row.workspace is None:
            return (2, -row.files)
        return (3, -row.files)

    candidates = tuple(sorted(rows, key=rank)[:3])
    return Report(
        store_root=str(store.root), ide=store.ide_id, conversations=len(rows),
        agent_id=agent_id, bound_spec=bound_spec, bound=bound,
        state=state, reason=reason, cwd=cwd, candidates=candidates,
    )


# --------------------------------------------------------------------- output


def _span(row: ConvInfo) -> str:
    if not row.first or not row.last:
        return "?"
    return f"{row.first:%Y-%m-%d}..{row.last:%Y-%m-%d}"


def announce(report: Report) -> None:
    """One compact line per fact, on stderr, so stdout stays the transcript."""
    print(
        f"contact-user: probe store={report.store_root} "
        f"ide={report.ide} convs={report.conversations}",
        file=sys.stderr,
    )
    if report.bound:
        b = report.bound
        mark = report.state.upper()
        print(
            f"contact-user: probe binding={report.agent_id}->{b.short} "
            f"files={b.files} span={_span(b)} ws={b.workspace or '?'} [{mark}]",
            file=sys.stderr,
        )
        if report.state != "ok":
            print(f"contact-user: probe detail: {report.reason}", file=sys.stderr)
    else:
        print(f"contact-user: probe binding=- ({report.reason})", file=sys.stderr)


def candidates_text(report: Report, limit: int = 3) -> str:
    if not report.candidates:
        return ""
    lines = ["  candidates (most messages first):"]
    for row in report.candidates[:limit]:
        lines.append(
            f"    {row.name}  msgs={row.files:<5} span={_span(row)}  ws={row.workspace or '?'}"
        )
    return "\n".join(lines)


def hint(report: Report) -> str:
    """The exact command that fixes this state, for the agent to run verbatim."""
    if report.candidates:
        best = report.candidates[0]
        return (
            f"fix: contact-user --id {report.agent_id} --bind-conversation {best.name}\n"
            f"or pass --conversation {best.short} for a single narrowed read"
        )
    return (
        "fix: contact-user --detect-history-root to confirm the store, then "
        "--bind-conversation <id> with an id from the probe line above"
    )


__all__ = [
    "ConvInfo", "Report", "announce", "candidates_text", "hint",
    "inspect", "survey", "workspace_of",
]
