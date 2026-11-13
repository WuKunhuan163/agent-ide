"""Hook body: at the moment the session would stop, push one queued item back.

Why Stop and not a timer: a periodic heartbeat calls the model even when there is
nothing to do; the Stop hook decides only at the moment the turn ends naturally, and
with nothing pending it does nothing at no cost. Same mechanism (one turn inside the
main session, with full context), different trigger.

One iron rule runs through the whole file: **only this file may push**. No command
lets the agent push an item right now -- it can only record. "Assigning work to
itself" does not exist in the interface.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import queue, store


def message(task: dict, remaining: int, extra: str = "") -> str:
    """The text fed back to the model: which item, what counts as done, how to record
    it, and stop there."""
    hint = str(task.get("hint") or "").strip()
    if hint:
        # Anonymous mode: no id, no progress. Which item to do is decided by the
        # evidence file itself -- naming the id invites gaming the count instead of
        # looking at what was actually written.
        lines = [f"[heartbeat] {hint}"]
    else:
        total = int(task.get("total") or 0)
        done = int(task.get("done") or 0)
        head = (f"[heartbeat] {task.get('id')} progress {done}/{total}, {total - done} left."
                if total else f"[heartbeat] todos remain ({remaining} left).")
        lines = [head, f"one item this turn: {task.get('id')} - {task.get('text')}"]

    if task.get("judge"):
        lines.append(f"done means: {task['judge']}")
    if task.get("evidence"):
        pat = task.get("evidence_pattern") or queue.DEFAULT_PATTERN
        lines.append(f"evidence: {task['evidence']} (the record counts lines matching {pat})")

    arg = "" if hint else f" {task.get('id')}"      # anonymous mode passes no id; inc takes the current item
    lines.append(
        f"when done run `heartbeat.py inc{arg}` once, then end this turn."
        f" it refuses without new evidence; if it cannot be done use"
        f" `heartbeat.py block{arg} \"where it is stuck\"`, never a false claim of completion."
    )
    lines.append("Do not start a second item in the same turn. The next dispatch comes"
                 " from the hook when you stop, not from you -- and you have no command"
                 " that triggers it.")
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _pre_check(cfg: dict, root: Path) -> str:
    cmd = str(cfg.get("pre_nudge_check") or "").strip()
    if not cmd:
        return ""
    try:
        out = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _target(payload: dict) -> tuple[str, dict, dict, dict] | None:
    """Shared session resolution: whether this session is mine, where it is bound, and
    what its queue holds.

    Both mount points share this block so the precondition does not get written twice
    and drift into two rule sets. A miss returns None, and the caller must stay fully
    silent: no output, no log line -- otherwise every wrap-up of every other session
    adds a line and the real signal drowns.
    """
    cfg = store.config()
    if not cfg.get("enabled"):
        return None
    session = str(payload.get("session_id") or "")
    if session and session in (cfg.get("exclude") or []):
        return None
    allow = cfg.get("sessions") or []
    if allow and session not in allow:
        return None
    binding = store.match_binding(cfg, session)
    if binding is None:
        return None
    return session, cfg, binding, store.load_tasks(binding)


def handle(payload: dict) -> dict | None:
    """Works only on the main session's Stop; returns the JSON to emit (intervene) or
    None (stay out of it, say nothing).

    Why SubagentStop is refused: a subagent shares its parent's session_id, and no
    field in the payload separates them. Accept SubagentStop and every subagent the
    parent dispatched (downloads, builds, long jobs) looks like "the main session
    stopped" the moment it finishes, so it gets handed a completely unrelated todo.
    Session binding breaks down here -- not because the match is written wrong, but
    because a session is the wrong granularity. Better one mount point fewer than
    work dispatched to an agent busy with something else.
    """
    if (payload.get("hook_event_name") or "Stop") != "Stop":
        return None
    store.remember_session(str(payload.get("session_id") or ""),
                           Path(payload.get("cwd") or os.getcwd()))

    target = _target(payload)
    if target is None:
        return None
    session, cfg, binding, data = target

    todo = queue.pending(data)
    if not todo:
        store.log(f"idle session={session[:8]}")
        return None

    now = time.time()
    root = store.work_root(binding)

    # Gate one: stop intervening once no new evidence has appeared for too long.
    # Measured from the last progress, not the last push -- the latter refreshes on
    # every push, so as long as it keeps pushing nothing ever expires and the gate
    # does not exist.
    last_progress = float(data.get("last_progress_at") or data.get("created_at") or now)
    age_h = (now - last_progress) / 3600
    if age_h > float(cfg.get("max_age_hours") or 24):
        store.log(f"stale {age_h:.1f}h pending={len(todo)}")
        return None

    # Gate two: how many pushes one chain may contain. A long enough gap starts a new
    # chain and the count resets.
    chain = data.get("_chain") or {}
    fresh_chain = (now - float(chain.get("at") or 0)) > float(cfg.get("chain_gap_seconds") or 1800)
    chain_count = 0 if fresh_chain else int(chain.get("count") or 0)
    limit = int(cfg.get("max_nudge_per_chain") or 200)
    if chain_count >= limit:
        store.log(f"giveup chain={chain_count}/{limit} pending={len(todo)}")
        return None

    # Gate three: pushing the same item with no evidence accumulates stall; at the cap
    # it moves to the next item.
    # "Did anything progress" has exactly one criterion: the line count recorded at
    # the last push, compared with now.
    first = todo[0]
    cur = queue.evidence_lines(first, root)
    last = data.get("_last_nudge") or {}
    no_progress = (last.get("task") == first.get("id")
                   and cur is not None
                   and cur <= int(last.get("lines") or -1))
    first["_stall"] = int(first.get("_stall") or 0) + 1 if no_progress else 0

    if int(first["_stall"]) >= int(cfg.get("stall_limit") or 6):
        first["status"] = "blocked"
        first["blocked_reason"] = (f"autoblocked: {first['_stall']} pushes in a row left the"
                                  f" evidence at {cur} lines")
        store.log(f"autoblock task={first.get('id')} stall={first['_stall']} lines={cur}")
        store.save_tasks(binding, data)
        rest = queue.pending(data)
        if not rest:
            return None
        first = rest[0]
        first["_stall"] = 0
        cur = queue.evidence_lines(first, root)

    if (first.get("status") or "todo") == "todo":
        first["status"] = "doing"
    data["_chain"] = {"at": now, "count": chain_count + 1}
    data["_last_nudge"] = {"at": now, "task": first.get("id"),
                           "lines": cur if cur is not None else -1}
    store.save_tasks(binding, data)

    store.log(f"nudge session={session[:8]} chain={chain_count + 1}/{limit} "
              f"task={first.get('id')} pending={len(todo)}")
    return {"continue": False, "stopReason": message(first, len(todo), _pre_check(cfg, root))}


def dump(payload: dict) -> int:
    """Print the payload the hook received, to confirm what upstream actually sends."""
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def read_payload() -> dict:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}
