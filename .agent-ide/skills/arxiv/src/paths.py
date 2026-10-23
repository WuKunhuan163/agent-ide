"""Skill directory and data path resolution."""
from __future__ import annotations

import os
import sys


def get_skills_dir() -> str:
    env = os.environ.get("AGENT_IDE_SKILL_DIR", "").strip()
    if env:
        return os.path.realpath(env)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates = (
            os.path.abspath(os.path.join(exe_dir, "..", ".agent-ide", "skills", "arxiv")),
            os.path.abspath(os.path.join(exe_dir, "..", ".cursor", "skills", "arxiv")),
        )
        return next((p for p in candidates if os.path.isdir(p)), candidates[0])
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_arg(raw) -> str:
    """A path typed on a command line: relative to the project root, never cwd.

    Absolute paths pass through; outside any project (no `.agent-tools` above
    the skill) cwd is the only remaining answer.
    """
    path = os.path.expanduser(str(raw))
    if os.path.isabs(path):
        return path
    here = get_skills_dir()
    while True:
        if os.path.isdir(os.path.join(here, ".agent-tools")):
            return os.path.join(here, path)
        parent = os.path.dirname(here)
        if parent == here:
            return os.path.abspath(path)
        here = parent


def data_dir() -> str:
    return os.path.join(get_skills_dir(), "data", "fetch")


def results_dir() -> str:
    return os.path.join(data_dir(), "results")


def cache_file() -> str:
    return os.path.join(data_dir(), "cache.json")


def default_config_file() -> str:
    return os.path.join(data_dir(), "default.json")
