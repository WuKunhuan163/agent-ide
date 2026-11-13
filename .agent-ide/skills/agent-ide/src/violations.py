"""The violation ledger: a catalogue plus an append-only event log.

The catalogue is `staging/ledger/violations.json` — plain data, read directly by whoever
needs it. No code parses it, no command prints it: a catalogue that needs a parser
is a catalogue with a second copy of itself inside the parser.

The log (`staging/ledger/events.jsonl`) holds *events* — one line per judgement, never
edited. Only the log is written by code.

Counting rule, as the user set it: any `fail` resets the streak to 0; there is no
upper bound on consecutive passes, and no count at which an entry is retired.
Only a `clear` event (ordered by the user) ends an entry.
"""

from __future__ import annotations

import os

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# The ledger is project state, not package content: a catalogue of past verdicts and an
# append-only event log differ per project and per run, so they live with the project.
# `AGENT_IDE_LEDGER` overrides; the default is `<cwd>/staging/ledger`.
LEDGER = Path(os.environ.get("AGENT_IDE_LEDGER", Path.cwd() / "staging" / "ledger"))
EVENTS = LEDGER / "events.jsonl"


@dataclass
class Event:
    at: str
    code: int
    result: str
    test: str
    note: str


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def events() -> list[Event]:
    if not EVENTS.exists():
        return []
    out: list[Event] = []
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append(Event(
            at=doc.get("at", "?"),
            code=int(doc.get("code", 0)),
            result=doc.get("result", "?"),
            test=doc.get("test", ""),
            note=doc.get("note", ""),
        ))
    return out


def log(code: int, result: str, test: str = "", note: str = "") -> Event:
    """Append one judgement. `result` is pass | fail | clear."""
    if result not in ("pass", "fail", "clear"):
        raise ValueError("result must be pass, fail or clear")
    ev = Event(at=_now(), code=code, result=result, test=test, note=note)
    LEDGER.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev.__dict__, ensure_ascii=False) + "\n")
    return ev


def streak(code: int) -> tuple[int, Event | None]:
    """Consecutive passes since the last fail/clear, and that last event."""
    seq = [e for e in events() if e.code == code]
    if not seq:
        return 0, None
    n = 0
    for ev in reversed(seq):
        if ev.result == "pass":
            n += 1
        else:
            return n, ev
    return n, seq[0]


