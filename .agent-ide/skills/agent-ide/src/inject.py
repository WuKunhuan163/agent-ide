"""Making a package visible to an IDE: `<domain>/skills/<skill>/SKILL.md` symlink.

Only `SKILL.md` is linked. The IDE reads the manifest inline, so nothing else
needs to appear there, and an unmanaged directory is never touched.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path

from . import paths
from .errors import Exit, fail


def run(project_root: Path, domain: str, action: str, names: list[str]) -> None:
    folder = _skills_folder(project_root, domain)
    if action == "add-skill":
        add(project_root, folder, names, domain)
    elif action == "remove-skill":
        remove(project_root, folder, names, domain)
    else:
        raise fail(Exit.Inject.FAILED, f"unknown inject subcommand: {action}")


def _skills_folder(project_root: Path, domain: str) -> Path:
    raw = (domain or "").strip()
    if not raw:
        raise fail(Exit.Inject.FAILED, "missing IDE domain (e.g. .cursor)")
    root = project_root.resolve()
    candidate = Path(raw).expanduser()
    candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise fail(Exit.Inject.FAILED, f"IDE domain must be inside {root}") from None
    canonical = (root / paths.IDE_DIR).resolve()
    if candidate == canonical or canonical in candidate.parents:
        raise fail(Exit.Inject.FAILED, "refusing to inject into .agent-ide itself")
    return candidate if candidate.name == "skills" else candidate / "skills"


def add(project_root: Path, folder: Path, names: list[str], domain: str) -> None:
    chosen = _chosen(project_root, names)
    folder.mkdir(parents=True, exist_ok=True)
    for name in chosen:
        _link(project_root, folder / name)
    print(f"inject {domain} add-skill: {', '.join(chosen)}")


def remove(project_root: Path, folder: Path, names: list[str], domain: str) -> None:
    wanted = set(_chosen(project_root, names)) if names else None
    removed = []
    if folder.is_dir():
        for child in sorted(folder.iterdir()):
            if not child.is_dir() or not _managed(child, project_root):
                continue
            if wanted is None or child.name in wanted:
                shutil.rmtree(child)
                removed.append(child.name)
    print(f"inject {domain} remove-skill: {', '.join(removed) or '(none)'}")


def _chosen(project_root: Path, names: list[str]) -> list[str]:
    root = paths.skills_dir(project_root)
    if not root.is_dir():
        raise fail(Exit.Inject.FAILED, f"no skills directory: {root}")
    available = sorted(
        entry.name for entry in root.iterdir()
        if entry.is_dir() and (entry / paths.SKILL_MD).is_file()
    )
    if not names:
        if not available:
            raise fail(Exit.Inject.FAILED, "no packages with SKILL.md to inject")
        return available
    chosen = []
    for raw in names:
        name = str(raw).strip()
        if not name or name in chosen:
            continue
        if not (paths.package_dir(project_root, name) / paths.SKILL_MD).is_file():
            raise fail(Exit.Inject.FAILED, f"unknown skill (no SKILL.md): {name}")
        chosen.append(name)
    return chosen


def _link(project_root: Path, target_dir: Path) -> None:
    source = paths.package_dir(project_root, target_dir.name) / paths.SKILL_MD
    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in target_dir.iterdir():
        if entry.name == paths.SKILL_MD:
            continue
        shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    link = target_dir / paths.SKILL_MD
    if link.exists() or link.is_symlink():
        link.unlink()
    os.symlink(os.path.relpath(source, target_dir), link)


def _managed(skill_dir: Path, project_root: Path) -> bool:
    link = skill_dir / paths.SKILL_MD
    if not link.is_symlink():
        return False
    expected = (paths.package_dir(project_root, skill_dir.name) / paths.SKILL_MD).resolve()
    try:
        return link.resolve() == expected
    except OSError:
        return False
