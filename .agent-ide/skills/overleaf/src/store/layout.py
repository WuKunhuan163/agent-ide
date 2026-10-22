"""Path constants and resolvers. The only store module that knows the `data/` root.

Runtime layout (gitignored, user-owned project data):

    <skill>/data/
    └── projects/<agent_id>/<project_id>/
        ├── project.json
        ├── blocks/<slug>/block.json
        ├── assets/
        └── build/            # products only, created on demand
"""
from __future__ import annotations

import os

# Names kept in one place so no other module hardcodes them.
DATA_DIRNAME = "data"
PROJECTS_DIRNAME = "projects"
PROJECT_FILE = "project.json"
BLOCKS_DIRNAME = "blocks"
BLOCK_FILE = "block.json"
ASSETS_DIRNAME = "assets"
BUILD_DIRNAME = "build"


def skill_dir() -> str:
    """The overleaf skill package root (ancestor holding `src/`)."""
    here = os.path.abspath(__file__)  # <skill>/src/store/layout.py
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def data_root() -> str:
    return os.path.join(skill_dir(), DATA_DIRNAME)


def projects_root() -> str:
    return os.path.join(data_root(), PROJECTS_DIRNAME)


def project_dir(agent_id: str, project_id: str) -> str:
    return os.path.join(projects_root(), agent_id, project_id)


def project_file(agent_id: str, project_id: str) -> str:
    return os.path.join(project_dir(agent_id, project_id), PROJECT_FILE)


def blocks_dir(agent_id: str, project_id: str) -> str:
    return os.path.join(project_dir(agent_id, project_id), BLOCKS_DIRNAME)


def block_dir(agent_id: str, project_id: str, rel_path: str = "") -> str:
    """Map a logical rel path to its physical nested directory.

    Children sit in a `blocks/` subdir beside each block's `block.json`, so
    `a/b` maps to `blocks/a/blocks/b`.
    """
    path = blocks_dir(agent_id, project_id)
    segments = [s for s in (rel_path or "").split("/") if s]
    for i, segment in enumerate(segments):
        path = os.path.join(path, segment)
        if i < len(segments) - 1:
            path = os.path.join(path, BLOCKS_DIRNAME)
    return path


def block_file(agent_id: str, project_id: str, rel_path: str) -> str:
    return os.path.join(block_dir(agent_id, project_id, rel_path), BLOCK_FILE)


def children_dir(agent_id: str, project_id: str, rel_path: str) -> str:
    """Top-level blocks live in `blocks/`; a block's children live in a
    `blocks/` subdir beside its `block.json`."""
    if not rel_path:
        return blocks_dir(agent_id, project_id)
    return os.path.join(block_dir(agent_id, project_id, rel_path), BLOCKS_DIRNAME)


def assets_dir(agent_id: str, project_id: str) -> str:
    return os.path.join(project_dir(agent_id, project_id), ASSETS_DIRNAME)


def build_dir(agent_id: str, project_id: str) -> str:
    """Products only. Ignored by git, so it is materialized on demand."""
    path = os.path.join(project_dir(agent_id, project_id), BUILD_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def normalize_rel_path(rel_path: str) -> str:
    """Normalize a block relative path or raise on traversal / absolutes.

    Accepts POSIX-style, forward-slash separated paths. Returns a canonical
    form with no leading/trailing separators.
    """
    from src.store.errors import DataError, PATH_UNSAFE

    raw = rel_path or ""
    candidate = raw.replace("\\", "/").strip()
    candidate = candidate.strip("/")
    if os.path.isabs(raw) or candidate.startswith("/"):
        raise DataError(PATH_UNSAFE, raw, "absolute paths are not allowed")
    parts: list[str] = []
    for segment in candidate.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise DataError(PATH_UNSAFE, raw, "parent traversal is not allowed")
        if segment == BLOCK_FILE or segment == PROJECT_FILE:
            raise DataError(PATH_UNSAFE, raw, "path must address a block directory")
        parts.append(segment)
    return "/".join(parts)
