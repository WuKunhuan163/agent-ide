"""Per-agent config.json under data/agents/<agent_id>/."""
from __future__ import annotations

import json
import os

from src.paths import require_ctx


def load_config() -> dict:
    config_file = require_ctx().config_file
    if not os.path.isfile(config_file):
        return {}
    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


DEFAULT_GPU_INTERLOCK = True


def gpu_interlock_enabled() -> bool:
    """True while a push still owes a human accelerator choice (the legacy P100 guard)."""
    return bool(load_config().get("gpu_interlock", DEFAULT_GPU_INTERLOCK))


def set_gpu_interlock(enabled: bool) -> None:
    config = load_config()
    config["gpu_interlock"] = bool(enabled)
    save_config(config)


def save_config(config: dict) -> None:
    p = require_ctx()
    os.makedirs(p.agent_dir, exist_ok=True)
    with open(p.config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
