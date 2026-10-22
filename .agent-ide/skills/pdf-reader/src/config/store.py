"""Persistence of user overrides (``data/config.json``).

Only *overrides* are stored: a key absent from this file means "use the schema
default".  That keeps the file small, keeps defaults upgradeable, and makes
``config unset`` a real operation rather than writing the default back.

Values are kept as the raw strings the user typed; coercion and validation happen
in ``resolve`` so that one code path decides what a valid value is.
"""
from __future__ import annotations

import json
from typing import Any

from ..util import log, paths


def load_overrides() -> dict[str, Any]:
    path = paths.config_file()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warn(f"data/config.json is not valid JSON ({exc}); ignoring it")
        return {}
    if not isinstance(raw, dict):
        log.warn("data/config.json is not an object; ignoring it")
        return {}
    return raw


def save_overrides(overrides: dict[str, Any]) -> None:
    path = paths.config_file()
    path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_override(key: str, raw: str) -> None:
    overrides = load_overrides()
    overrides[key] = raw
    save_overrides(overrides)


def unset_override(key: str) -> bool:
    overrides = load_overrides()
    if key not in overrides:
        return False
    del overrides[key]
    save_overrides(overrides)
    return True


def reset_overrides() -> None:
    save_overrides({})
