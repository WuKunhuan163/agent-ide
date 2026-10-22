"""Where the skill keeps its mutable state.

Every path is derived from this file's location, so the skill can be moved or
copied between checkouts without a hard-coded absolute path.  The archived tool
hard-coded ``.agent-ide/skills/pdf_reader`` and a cwd-relative temp dir; both were
sources of confusing failures.
"""
from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = SKILL_ROOT / "data"
DOCS_DIR = SKILL_ROOT / "docs"


def ensure(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return ensure(DATA_DIR / "config.json")


def token_file() -> Path:
    return ensure(DATA_DIR / "token.json")


def quota_file() -> Path:
    return ensure(DATA_DIR / "quota.json")


def runs_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "runs"


def sources_dir() -> Path:
    """Local copies of ``-u`` inputs, one directory per URL.

    A fetched source is an ordinary local file from here on, which is what lets
    its page count be measured and its windows planned before anything is sent.
    """
    path = DATA_DIR / "sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_dir(run_id: str) -> Path:
    path = runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
