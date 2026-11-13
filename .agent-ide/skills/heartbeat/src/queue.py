"""Todo queue: state machine plus evidence counting.

Core constraint: progress is not asserted by the caller, it is counted out of the
evidence file. "Remember to record" and "actually did it" therefore become the same
thing -- no new evidence, no new progress.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

DEFAULT_PATTERN = r"^\|\s*\d+\s*\|"
STATUSES = ("todo", "doing", "done", "blocked")


def pending(data: dict) -> list[dict]:
    """Items still to push: doing first (finish what is in hand), then registration
    order. blocked and done never appear."""
    items = [t for t in data.get("tasks", [])
             if (t.get("status") or "todo") in ("todo", "doing")]
    return sorted(items, key=lambda t: 0 if t.get("status") == "doing" else 1)


def find(data: dict, tid: str) -> dict | None:
    for t in data.get("tasks", []):
        if t.get("id") == tid:
            return t
    return None


def check_pattern(pattern: str | None) -> str | None:
    """Validate a pattern: None when it is fine, otherwise one readable sentence.

    Without this check a broken pattern reaches the store: `inc` raises a traceback,
    and the hook side reads it as "0 lines matched", so the stall counter climbs and
    the task ends up autoblocked -- a typo explained away as "the model is idle".
    """
    if not pattern:
        return None
    try:
        re.compile(pattern, re.M)
    except re.error as exc:
        return f"evidence_pattern is not a valid regex: {pattern!r} ({exc})"
    return None


def evidence_lines(task: dict, root: Path) -> int | None:
    """Count the lines that count in the evidence file.

    None means unverifiable (no evidence, or a broken pattern). Either way the caller
    must skip the stall check instead of reading it as "0 lines of evidence" -- a
    configuration error would otherwise masquerade as idling.
    """
    ev = task.get("evidence")
    if not ev:
        return None
    path = Path(ev)
    if not path.is_absolute():
        path = Path(root) / path
    if not path.exists():
        return 0
    pattern = task.get("evidence_pattern") or DEFAULT_PATTERN
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    if check_pattern(pattern):
        return None
    return len(re.findall(pattern, text, flags=re.M))


def add(data: dict, text: str, root: Path | None = None, **opts) -> dict:
    """Register an item. done starts at the **current** line count, not 0.

    Why it has to: the evidence file is usually not empty (the previous item just
    wrote into it). Starting from 0 means the first `inc` after registering jumps from
    0 to the existing count without writing anything -- free progress that walks
    straight around the "no new evidence, no recording" gate. The start has to line up
    with what the evidence file already holds.
    """
    tasks = data.setdefault("tasks", [])
    item = {"id": f"t{len(tasks) + 1}", "text": text, "status": "todo"}
    item.update({k: v for k, v in opts.items() if v is not None})
    if root is not None and item.get("evidence"):
        item["done"] = evidence_lines(item, root) or 0
    tasks.append(item)
    now = time.time()
    data.setdefault("created_at", now)
    data["last_progress_at"] = now      # registering counts as progress, so a fresh item is not stale at once
    return item


def bump(task: dict, root: Path) -> tuple[bool, str]:
    """Record one step. Returns (ok, note).

    Items with evidence: accepted only when the line count strictly grows; that is the
    one hard gate against false claims. Items without evidence fall back to a counter,
    but stall cannot see progress there, so max_age and the chain cap are all that
    remain.
    """
    ev = task.get("evidence")
    total = int(task.get("total") or 0)
    if not ev:
        task["done"] = int(task.get("done") or 0) + 1
    else:
        path = Path(ev)
        if not path.is_absolute():
            path = Path(root) / path
        if not path.exists():
            return False, f"evidence file does not exist: {path}"
        pattern = task.get("evidence_pattern") or DEFAULT_PATTERN
        bad = check_pattern(pattern)
        if bad:
            return False, bad
        found = len(re.findall(pattern, path.read_text(encoding="utf-8", errors="replace"), flags=re.M))
        prev = int(task.get("done") or 0)
        if found <= prev:
            return False, (f"no new entry in {path.name} ({found} lines, progress still"
                           f" {prev}) -- do the work first, then record it")
        task["done"] = found
    task["_stall"] = 0
    if total and int(task["done"]) >= total:
        task["status"] = "done"
    return True, f"{task['id']} {task['done']}/{total or '?'}"


def sync(task: dict, root: Path) -> str:
    """Pull done back to the real line count in the evidence file: overcounts are
    corrected here."""
    ev = task.get("evidence")
    if not ev:
        return "this item has no evidence file, nothing to align with"
    bad = check_pattern(task.get("evidence_pattern"))
    if bad:
        return bad
    found = evidence_lines(task, root) or 0
    old = task.get("done") or 0
    task["done"] = found
    return f"{old} -> {found}"


def set_status(task: dict, status: str, note: str = "") -> None:
    if status not in STATUSES:
        return
    task["status"] = status
    if note:
        task["blocked_reason" if status == "blocked" else "note"] = note
    if status != "blocked":
        task.pop("blocked_reason", None)
    if status in ("done", "todo"):
        task["_stall"] = 0
