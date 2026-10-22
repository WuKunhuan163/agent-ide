"""Copying a skill package under its own whitelist.

Only the manifest's files and directories move. `data/` — archives, caches,
credentials — is never declared, so it never leaves the machine it lives on.
Directories are replaced wholesale, so a deleted source file disappears at the
destination too; files are copied, never pruned, because a package's `data/`
must survive a push.
"""
from __future__ import annotations
import shutil
from pathlib import Path

from . import manifest as manif
from .errors import Exit, fail

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".git")


def package(name: str, src_root: Path, dest_root: Path, *, validate: bool = True) -> None:
    src = src_root / name
    dest = dest_root / name
    if not src.is_dir():
        raise fail(Exit.Package.FAILED, f"skill package not found: {src}")
    if src.resolve() == dest.resolve():
        return

    spec = manif.load(src)
    if validate:
        manif.validate(src, spec)

    dest.mkdir(parents=True, exist_ok=True)
    for rel in manif.files(src, spec):
        source = src / rel
        if not source.is_file():
            if validate:
                raise fail(Exit.Package.FAILED, f"{name}: declared file missing: {rel}")
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    for rel in manif.directories(spec):
        source = src / rel
        if not source.is_dir():
            if validate:
                raise fail(Exit.Package.FAILED, f"{name}: declared directory missing: {rel}")
            continue
        target = dest / rel
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, symlinks=True, ignore=IGNORE)


def batch(
    names: list[str], src_root: Path, dest_root: Path, verb: str, *, echo: bool = True
) -> list[str]:
    """Copy every named package; the first failure aborts with its own message."""
    targets = manif.packages(src_root, names)
    if src_root.resolve() != dest_root.resolve():
        dest_root.mkdir(parents=True, exist_ok=True)
        for name in targets:
            package(name, src_root, dest_root)
    if echo:
        print(f"{verb}: {', '.join(targets)} -> {dest_root}")
    return targets
