"""The adapter table. Nothing outside `src/ide/` branches on an IDE id."""
from __future__ import annotations
from pathlib import Path

from .base import Message, SessionStore, ToolCall, ToolResult, clip, iso, parse_ts
from .codebuddy import CodeBuddyStore

STORES: dict[str, type[SessionStore]] = {CodeBuddyStore.ide_id: CodeBuddyStore}
DEFAULT_IDE = CodeBuddyStore.ide_id


def ide_ids() -> list[str]:
    return sorted(STORES)


def store_class(ide: str) -> type[SessionStore]:
    try:
        return STORES[ide]
    except KeyError:
        raise KeyError(f"unknown ide '{ide}'; known: {', '.join(ide_ids())}") from None


def create(ide: str, root: Path) -> SessionStore:
    return store_class(ide)(root)


def detect(ide: str | None = None) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for key in ide_ids():
        if ide and key != ide:
            continue
        found.extend((key, root) for root in STORES[key].discover())
    return found


__all__ = [
    "DEFAULT_IDE",
    "Message",
    "SessionStore",
    "ToolCall",
    "ToolResult",
    "clip",
    "create",
    "detect",
    "ide_ids",
    "iso",
    "parse_ts",
    "store_class",
]
