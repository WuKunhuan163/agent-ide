"""State: config, todos and log all live under this skill's own data/, never inside a
project directory.

Why it matters -- the previous version wrote todos to
<project>/.codebuddy/lobster/tasks.json, where another session (another agent) in the
same project could read them, turning "one session's heartbeat" into "the whole
project's heartbeat". Where the data lives decides how wide the scope is; the scope
has to equal the session, so the data has to leave the project directory.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
DATA = PKG / "data"
CONFIG = DATA / "config.json"
LOG = DATA / "heartbeat.log"
SEEN = DATA / "sessions.json"
TASKS = DATA / "tasks"

DEFAULT_CONFIG = {
    "enabled": False,
    # Allow list: when non-empty only these sessions heartbeat; empty means no limit
    # (bindings still have to match).
    "sessions": [],
    "exclude": [],
    # binding = {session: <session id>, tasks: <work root>}; session is the only identity.
    # Binding by directory does not exist: one project often runs several sessions, and
    # binding by directory catches every other agent in it -- the real contamination of
    # the previous version.
    "bindings": [],
    # How many pushes one chain (one unattended run of consecutive progress) may contain.
    "max_nudge_per_chain": 200,
    # A gap longer than this since the last push starts a new chain and resets the count.
    "chain_gap_seconds": 1800,
    # Push the same item this many times without evidence growth and it is autoblocked
    # in favour of the next one.
    "stall_limit": 6,
    # Stop intervening once todos have gone this many hours without new evidence.
    # Measured from the last progress (last_progress_at), not the last push -- counting
    # from pushes means it never expires while it keeps pushing, and the gate is gone.
    "max_age_hours": 24,
    # Optional external command run before a push: non-empty stdout is appended to the hint.
    # The previous version hardcoded "check whether the GPU is billing", which is one
    # project's coupling and does not belong in a general tool.
    "pre_nudge_check": "",
}


def config() -> dict:
    if CONFIG.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG.read_text())}
        except ValueError:
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%m-%d %H:%M:%S')} {line}\n")


def match_binding(cfg: dict, session: str = "") -> dict | None:
    """session -> the matching binding. Only an exact session match counts; nothing else
    matches.

    None means "not my session", and the caller must stay fully silent: no print, no
    log line.

    Why even the directory fallback is gone: one project usually runs several sessions
    at once (different tasks, different agents) with an identical cwd. Matching on the
    directory means "one session heartbeats, the whole project is interrupted" -- the
    contamination of the previous version. cwd carries no information here: it proves
    everyone sits in the same repository, not who should be dispatched.
    """
    for b in cfg.get("bindings") or []:
        if b.get("session") and session and session == b["session"]:
            return b
    return None


def store_key(binding: dict | None) -> str:
    """Todo file name. Isolated per session, so different sessions in one project each
    get their own file."""
    b = binding or {}
    if b.get("store"):
        return str(b["store"])
    return "s-" + str(b.get("session") or "unbound")[:16]


def tasks_path(binding: dict | None) -> Path:
    return TASKS / f"{store_key(binding)}.json"


def work_root(binding: dict | None) -> Path:
    return Path((binding or {}).get("tasks") or ".").expanduser()


def load_tasks(binding: dict | None) -> dict:
    p = tasks_path(binding)
    if not p.exists():
        return {"tasks": []}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {"tasks": []}


def save_tasks(binding: dict | None, data: dict) -> None:
    p = tasks_path(binding)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def remember_session(session: str, cwd: Path) -> None:
    """Remember sessions seen, so `bind --session` has an id to pick from.

    This is the only write that happens on the "not matched" path, and it writes once
    per session; otherwise the unmatched path does nothing at all.
    """
    if not session:
        return
    try:
        seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    except ValueError:
        seen = {}
    if seen.get(session, {}).get("cwd") == str(cwd):
        return
    seen[session] = {"cwd": str(cwd), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=2) + "\n")


def seen_sessions() -> dict:
    try:
        return json.loads(SEEN.read_text()) if SEEN.exists() else {}
    except ValueError:
        return {}
