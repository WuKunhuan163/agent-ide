"""The project's `quick_access/COLDSTART.md` entry point.

It is a relative symlink into this package, re-created on every invocation, so
the documented path stays valid even after a round that died before its
checkpoint.
"""
from __future__ import annotations
import os
from pathlib import Path

FOLDER = "quick_access"
TARGET = "COLDSTART.md"


def ensure() -> Path:
    from .paths import pkg_dir, project_root

    folder = project_root() / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    link = folder / TARGET
    wanted = os.path.relpath(pkg_dir() / TARGET, folder)
    try:
        if link.is_symlink() and os.readlink(link) == wanted:
            return folder
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(wanted)
    except OSError:
        pass
    return folder


def ensure_quietly() -> None:
    try:
        ensure()
    except (OSError, RuntimeError):
        pass
