"""How the window reports its outcome to the parent process.

A tiny file instead of stdout: a window that crashes, or prints anything else,
still leaves the parent with a definite answer (absent = no answer).
"""
from __future__ import annotations

from .paths import handshake

STATUSES = ("SUBMITTED", "CLOSED")


def write(agent_id: str, status: str, content: str = "") -> None:
    path = handshake(agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{status}\n{content}", encoding="utf-8")


def read(agent_id: str) -> tuple[str | None, str]:
    try:
        raw = handshake(agent_id).read_text(encoding="utf-8")
    except OSError:
        return None, ""
    status, _, content = raw.partition("\n")
    status = status.strip()
    return (status, content) if status in STATUSES else (None, "")


def clear(agent_id: str) -> None:
    try:
        handshake(agent_id).unlink(missing_ok=True)
    except OSError:
        pass
