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
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Two different things share one folder name, and they travel differently.
#
# The *log* (`events.jsonl`) is project state: it differs per project by
# construction, so it lives with the project and is never pushed anywhere.
# The *catalogue* (`violations.json`, `violations.md`, `method.md`) is package
# content: it is the same list of judgement codes everywhere, so it ships with
# the skill and is seeded into a project the first time that project needs one.
#
# Reading order is project first, package second -- a project may extend the
# catalogue, but a project with no catalogue of its own must still get the
# shipped one instead of an empty ledger that looks like "no violations".
# `AGENT_IDE_LEDGER` overrides the project side only.
LEDGER = Path(os.environ.get("AGENT_IDE_LEDGER", Path.cwd() / "staging" / "ledger"))
EVENTS = LEDGER / "events.jsonl"
PACKAGE_LEDGER = Path(__file__).resolve().parent.parent / "ledger"
CATALOGUE = ("violations.json", "violations.md", "method.md")


def catalogue(name: str) -> Path:
    """Where the catalogue file `name` is readable from: project, else package."""
    local = LEDGER / name
    if local.exists():
        return local
    shipped = PACKAGE_LEDGER / name
    return shipped if shipped.exists() else local


def seed() -> list[str]:
    """Copy the shipped catalogue into the project ledger, once.

    Without this each project invents its own catalogue (measured: two projects
    had 18,889 and 22,233 bytes under the same filename), and a `--log` against
    the wrong copy reports a streak for a catalogue nobody else has.
    """
    LEDGER.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in CATALOGUE:
        target = LEDGER / name
        source = PACKAGE_LEDGER / name
        if target.exists() or not source.exists():
            continue
        shutil.copy2(source, target)
        copied.append(name)
    return copied


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
    seed()
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


