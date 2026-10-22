"""`data/config.json`: which IDE's transcript to read, and where it lives.

The store path is configuration, never detection at read time: an agent must
pin it explicitly once, and every later read uses exactly that path.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

from .ide import registry
from .ide.base import SessionStore
from .paths import config as config_path

HISTORY_ROOT = "session_history_root"
SESSION_IDE = "session_ide"
MIRROR = "session_mirror_enabled"

DEFAULTS = {HISTORY_ROOT: "", SESSION_IDE: registry.DEFAULT_IDE, MIRROR: True}


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


# --------------------------------------------------------------------- mirror


def mirror_enabled() -> bool:
    return bool(load().get(MIRROR, True))


def set_mirror_enabled(enabled: bool) -> None:
    save({**load(), MIRROR: bool(enabled)})
