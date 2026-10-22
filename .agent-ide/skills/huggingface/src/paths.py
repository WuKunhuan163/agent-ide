"""Path helpers for huggingface."""
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
            os.path.abspath(os.path.join(exe_dir, "..", ".agent-ide", "skills", "huggingface")),
            os.path.abspath(os.path.join(exe_dir, "..", ".cursor", "skills", "huggingface")),
        )
        return next((p for p in candidates if os.path.isdir(p)), candidates[0])
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
