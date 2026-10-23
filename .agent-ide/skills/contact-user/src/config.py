"""`data/config.json`: which IDE's transcript to read, and where it lives.

The store path is configuration, never detection at read time: an agent must
pin it explicitly once, and every later read uses exactly that path.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

from .ide import registry
from .ide.base import SessionStore
from .paths import config as config_path

HISTORY_ROOT = "session_history_root"
SESSION_IDE = "session_ide"
MIRROR = "session_mirror_enabled"
BINDINGS = "conversation_bindings"
WINDOW_GEOMETRY = "window_geometry"
WINDOW_FONT = "window_font"
WINDOW_FONT_SIZE = "window_font_size"
WINDOW_ROWS = "window_rows"
BELL_INTERVAL = "bell_interval"
GUI_ATTEMPTS = "gui_attempts"
AUTOSAVE_MS = "autosave_ms"

FALLBACK_GEOMETRY = "360x280"
FALLBACK_FONT = "Arial"
FALLBACK_FONT_SIZE = 14
FALLBACK_ROWS = 15
FALLBACK_BELL = 90
FALLBACK_ATTEMPTS = 5
FALLBACK_AUTOSAVE = 1000
GEOMETRY_SPEC = re.compile(r"^\d+x\d+([+-]\d+[+-]\d+)?$")

DEFAULTS = {
    HISTORY_ROOT: "",
    SESSION_IDE: registry.DEFAULT_IDE,
    MIRROR: True,
    BINDINGS: {},
    WINDOW_GEOMETRY: FALLBACK_GEOMETRY,
    WINDOW_FONT: FALLBACK_FONT,
    WINDOW_FONT_SIZE: FALLBACK_FONT_SIZE,
    WINDOW_ROWS: FALLBACK_ROWS,
    BELL_INTERVAL: FALLBACK_BELL,
    GUI_ATTEMPTS: FALLBACK_ATTEMPTS,
    AUTOSAVE_MS: FALLBACK_AUTOSAVE,
}


class ConfigError(RuntimeError):
    """A setting is missing, unknown, or points at something unusable."""


def load() -> dict:
    try:
        doc = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)
    if not isinstance(doc, dict):
        return dict(DEFAULTS)
    return {**DEFAULTS, **{k: v for k, v in doc.items() if isinstance(k, str)}}


def save(cfg: dict) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(
        json.dumps({**DEFAULTS, **cfg}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ------------------------------------------------------------------ IDE choice


def session_ide() -> str:
    ide = str(load().get(SESSION_IDE) or "").strip() or registry.DEFAULT_IDE
    if ide not in registry.ide_ids():
        raise ConfigError(
            f"session_ide {ide!r} is not a known adapter "
            f"(known: {', '.join(registry.ide_ids())})"
        )
    return ide


def set_session_ide(ide: str) -> str:
    key = str(ide or "").strip()
    if key not in registry.ide_ids():
        raise ConfigError(f"unknown ide {ide!r}; known: {', '.join(registry.ide_ids())}")
    save({**load(), SESSION_IDE: key})
    return key


# ------------------------------------------------------------------ store root


def history_root(required: bool = False) -> Path | None:
    """The pinned store, resolved so two spellings of one path compare equal."""
    raw = str(load().get(HISTORY_ROOT) or "").strip()
    if not raw:
        if required:
            raise ConfigError(
                "session_history_root is not configured, so this agent cannot read "
                "the conversation it is expected to report on.\n"
                f"{setup_hint()}\n"
                "Then: contact-user --set-history-root <absolute path>"
            )
        return None
    path = Path(os.path.expanduser(raw))
    try:
        path = path.resolve()
    except OSError:
        pass
    if path.is_dir():
        return path
    if required:
        raise ConfigError(
            f"session_history_root points at a missing directory: {path}\n"
            "Fix: contact-user --set-history-root <absolute path>"
        )
    return None


def setup_hint() -> str:
    try:
        return registry.store_class(session_ide()).setup_hint()
    except (ConfigError, KeyError):
        return registry.store_class(registry.DEFAULT_IDE).setup_hint()


def set_history_root(raw: str, ide: str | None = None) -> Path:
    path = Path(os.path.expanduser(str(raw).strip()))
    if not path.is_absolute():
        raise ConfigError(f"an absolute path is required, got: {raw}")
    if not path.is_dir():
        raise ConfigError(f"not a directory: {path}")
    key = ide or session_ide()
    store_cls = registry.store_class(key)
    if not store_cls.validate_root(path):
        raise ConfigError(
            f"{path} is not a usable {key} transcript store "
            f"(nothing under it looks like a conversation with messages/)\n{store_cls.setup_hint()}"
        )
    path = path.resolve()
    save({**load(), HISTORY_ROOT: str(path), SESSION_IDE: key})
    return path


def make_store() -> SessionStore:
    root = history_root(required=True)
    assert root is not None
    return registry.create(session_ide(), root)


# ---------------------------------------------------------------- id ↔ conv


def bindings() -> dict[str, str]:
    """agent id -> conversation id, as registered by `--bind-conversation`."""
    raw = load().get(BINDINGS)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str) and value.strip()
    }


def binding(agent_id: str) -> str | None:
    return bindings().get(agent_id)


def set_binding(agent_id: str, conversation: str) -> str:
    table = bindings()
    table[agent_id] = conversation
    save({**load(), BINDINGS: table})
    return conversation


def clear_binding(agent_id: str) -> bool:
    table = bindings()
    if agent_id not in table:
        return False
    table.pop(agent_id)
    save({**load(), BINDINGS: table})
    return True


# --------------------------------------------------------------------- mirror


def mirror_enabled() -> bool:
    return bool(load().get(MIRROR, True))


def set_mirror_enabled(enabled: bool) -> None:
    save({**load(), MIRROR: bool(enabled)})


# ------------------------------------------------------------------- ui defaults


def window() -> dict:
    """The contact window's defaults: geometry, font, and editor rows.

    A value that cannot be used falls back to the built-in one instead of
    failing the round: a typo in `data/config.json` must not cost a reply.
    """
    cfg = load()
    geometry = str(cfg.get(WINDOW_GEOMETRY) or "").strip()
    if not GEOMETRY_SPEC.match(geometry):
        geometry = FALLBACK_GEOMETRY
    font = str(cfg.get(WINDOW_FONT) or "").strip() or FALLBACK_FONT
    return {
        "geometry": geometry,
        "font": font,
        "font_size": _number(cfg.get(WINDOW_FONT_SIZE), FALLBACK_FONT_SIZE, 8, 72),
        "rows": _number(cfg.get(WINDOW_ROWS), FALLBACK_ROWS, 3, 200),
    }


def bell_interval() -> int:
    """Seconds between bells while a window is open; 0 rings once."""
    return _number(load().get(BELL_INTERVAL), FALLBACK_BELL, 0, 3600)


def gui_attempts() -> int:
    """How many windows a round opens before it gives up (1..10)."""
    return _number(load().get(GUI_ATTEMPTS), FALLBACK_ATTEMPTS, 1, 10)


def autosave_ms() -> int:
    """Draft autosave period in milliseconds; 0 saves only on change/close."""
    return _number(load().get(AUTOSAVE_MS), FALLBACK_AUTOSAVE, 0, 60000)


def _number(value: object, fallback: int, low: int, high: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return number if low <= number <= high else fallback
