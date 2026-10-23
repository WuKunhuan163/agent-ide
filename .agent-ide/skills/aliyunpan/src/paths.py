"""Where this skill keeps state, and how an agent id names a slice of it.

Every agent id owns one credential file written by the login step (`config.json`)
plus its own resume state. Sharing them would mean two agents refreshing the same
token, which logs one of them out mid-transfer.
"""
from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def pkg_dir() -> Path:
    return SKILL_DIR


def project_root() -> Path:
    """Nearest ancestor that holds `.agent-tools/` — where generated .app bundles go."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".agent-tools").is_dir():
            return parent
    raise RuntimeError("cannot find project root (no .agent-tools/ above this package)")


def resolve_arg(raw) -> Path:
    """A path typed on a command line: relative to the project root, never cwd.

    Remote paths are absolute (`/dir`) and pass through untouched, so one
    function serves both sides of `upload`.
    """
    path = Path(raw).expanduser()
    return path if path.is_absolute() else project_root() / path


def data_root() -> Path:
    return SKILL_DIR / "data"


def agent_dir(agent_id: str) -> Path:
    return data_root() / agent_id


def config_path(agent_id: str) -> Path:
    return agent_dir(agent_id) / "config.json"


def resume_dir(agent_id: str) -> Path:
    return agent_dir(agent_id) / "resume"


def resume_path(agent_id: str, key: str) -> Path:
    return resume_dir(agent_id) / f"{key}.json"


def ensure_agent_dir(agent_id: str) -> Path:
    path = agent_dir(agent_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def binary_path() -> Path:
    """The bundled tickstep CLI, used only for the interactive login step."""
    candidates = [
        SKILL_DIR / "bin" / "aliyunpan",
        SKILL_DIR / "bin" / "aliyunpan.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"no aliyunpan binary under {SKILL_DIR / 'bin'}; install it before login"
    )


def pretty(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}TB"


def human_time(epoch: float) -> str:
    return os.strftime("%Y-%m-%d %H:%M:%S", os.localtime(epoch))
