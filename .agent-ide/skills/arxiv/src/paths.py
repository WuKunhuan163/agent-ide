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


def data_dir() -> str:
    return os.path.join(get_skills_dir(), "data", "fetch")


def results_dir() -> str:
    return os.path.join(data_dir(), "results")


def cache_file() -> str:
    return os.path.join(data_dir(), "cache.json")


def default_config_file() -> str:
    return os.path.join(data_dir(), "default.json")
