"""Every path this tool owns, in one place.

The on-disk names are part of the contract: archived rounds from earlier
versions must keep working, so they are spelled out here once and never
composed ad hoc elsewhere.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

CONTACT = "contact_msg"
RESPONSE = "user_response"


def project_root() -> Path:
    """Nearest ancestor that holds `.agent-tools/` — the checkpoint target."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".agent-tools").is_dir():
            return parent
    raise RuntimeError("cannot find project root (no .agent-tools/ above this package)")


def pkg_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def data(*parts: str, create: bool = False) -> Path:
    path = pkg_dir().joinpath("data", *parts)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------- round inputs


def input_text(agent_id: str, kind: str) -> Path:
    """`kind` is `contact` or `commit`."""
    return data("input", f"{kind}_msg_{agent_id}.txt")


def archived(agent_id: str, kind: str, ts: str | None = None) -> Path:
    return data(kind, agent_id, f"{ts or stamp()}_{kind}.txt")


def autosave(agent_id: str) -> Path:
    return data("autosave", agent_id, "autosave.txt")


# ------------------------------------------------------------------- ui state


def lock(agent_id: str) -> Path:
    return data("locks", f"{agent_id}.lock")


def geometry(agent_id: str) -> Path:
    return data("window", agent_id, "geometry.txt")


def handshake(agent_id: str) -> Path:
    return data("locks", f"{agent_id}_handshake.txt")


# ------------------------------------------------------- session bookkeeping


def config() -> Path:
    return data("config.json")


def marker(agent_id: str) -> Path:
    """Start of the next `--changes` window."""
    return data("last_round", f"{agent_id}.json")


def token(agent_id: str) -> Path:
    """Proof the agent read the session before reporting."""
    return data("session_context", f"{agent_id}.json")


def mirror() -> Path:
    """Separate git repository with the mirrored transcript.

    Under `data/`, which the project `.gitignore` excludes, so it never enters
    the project's own checkpoint.
    """
    return data("session_mirror", create=True)
