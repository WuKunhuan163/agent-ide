"""Disk <-> memory mapping, atomic writes, slug allocation, tree traversal.

Format-level concerns only. Structural constraints (order conflicts, allowed
child types) live in `tree.py`; content schema lives in `schema.py`.
"""
from __future__ import annotations

import os
import re
import shutil

from src.store import codec, layout
from src.store import errors
from src.store.errors import DataError
from src.store.model import Block, Project

_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


# --------------------------------------------------------------------------- read


def read_project(agent_id: str, project_id: str) -> Project:
    pdir = layout.project_dir(agent_id, project_id)
    if not os.path.isdir(pdir):
        raise DataError(errors.PROJECT_NOT_FOUND, pdir, "project directory does not exist")

    pdata = codec.load_project_json(layout.project_file(agent_id, project_id))
    root = Block(
        id="",
        type="__root__",
        order=0,
        display=True,
        content={},
        rel_path="",
    )
    root.children = _read_children(layout.blocks_dir(agent_id, project_id), "")
    return Project(
        id=project_id,
        agent_id=agent_id,
        root_dir=pdir,
        template_id=pdata["template"],
        template_version=pdata["template_version"],
        metadata=pdata["metadata"],
        root=root,
    )


def _read_children(container: str, prefix: str) -> list[Block]:
    if not os.path.isdir(container):
        return []
    blocks: list[Block] = []
    for name in sorted(os.listdir(container)):
        child_dir = os.path.join(container, name)
        if not os.path.isdir(child_dir):
            continue
        rel = f"{prefix}/{name}" if prefix else name
        bpath = os.path.join(child_dir, layout.BLOCK_FILE)
        if not os.path.isfile(bpath):
            raise DataError(
                errors.MALFORMED_FILE, bpath, "block directory is missing block.json"
            )
        bdata = codec.load_block_json(bpath)
        block = Block(
            id=name,
            type=bdata["type"],
            order=bdata["order"],
            display=bdata["display"],
            content=bdata["content"],
            rel_path=rel,
        )
        block.children = _read_children(os.path.join(child_dir, layout.BLOCKS_DIRNAME), rel)
        blocks.append(block)
    blocks.sort(key=lambda b: (b.order, b.id))
    return blocks


def find_block(project: Project, rel_path: str) -> Block | None:
    return project.find(layout.normalize_rel_path(rel_path))


# --------------------------------------------------------------------------- write


def write_block(agent_id: str, project_id: str, block: Block) -> None:
    """Serialize one block in place. Leaves every other file untouched."""
    bdir = layout.block_dir(agent_id, project_id, block.rel_path)
    if not block.rel_path or not _SLUG_RE.match(block.id):
        raise DataError(errors.PATH_UNSAFE, block.rel_path, f"unsafe block id {block.id!r}")
    codec.dump_block_json(
        os.path.join(bdir, layout.BLOCK_FILE),
        {
            "type": block.type,
            "order": block.order,
            "display": block.display,
            "content": block.content,
        },
    )


def remove_block_dir(agent_id: str, project_id: str, rel_path: str) -> None:
    bdir = layout.block_dir(agent_id, project_id, rel_path)
    if os.path.isdir(bdir):
        shutil.rmtree(bdir)
    _prune_empty_containers(agent_id, project_id, bdir)


def _prune_empty_containers(agent_id: str, project_id: str, start: str) -> None:
    """Drop `blocks/` container dirs that became empty after a removal."""
    base = layout.blocks_dir(agent_id, project_id)
    parent = os.path.dirname(start)
    while parent.startswith(base) and parent != base:
        try:
            os.rmdir(parent)
        except OSError:
            break
        parent = os.path.dirname(parent)


def rename_block_dir(agent_id: str, project_id: str, old_rel: str, new_rel: str) -> None:
    src = layout.block_dir(agent_id, project_id, old_rel)
    dst = layout.block_dir(agent_id, project_id, new_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # A `blocks/` container may linger once its last child moves out.
    pruning: list[str] = []
    parent = os.path.dirname(src)
    while parent.startswith(layout.blocks_dir(agent_id, project_id)) and parent != layout.blocks_dir(
        agent_id, project_id
    ):
        pruning.append(parent)
        parent = os.path.dirname(parent)
    try:
        os.replace(src, dst)
    except OSError as exc:
        # The disk refusing the rename is a data-plane failure like any other:
        # callers see a code, never a traceback.
        raise DataError(
            errors.WRITE_FAILED, new_rel, f"cannot move the block directory: {exc}"
        )
    for stale in pruning:
        try:
            os.rmdir(stale)
        except OSError:
            break


def write_project_json(agent_id: str, project_id: str, data: dict) -> None:
    codec.dump_project_json(layout.project_file(agent_id, project_id), data)


# --------------------------------------------------------------------------- slug


def alloc_slug(container: str, base: str) -> str:
    """Pick a directory name under `container` that does not yet exist.

    `base` is usually the block type; collisions get a numeric suffix.
    """
    slug = _slugify(base)
    if not os.path.exists(os.path.join(container, slug)):
        return slug
    i = 2
    while os.path.exists(os.path.join(container, f"{slug}_{i}")):
        i += 1
    return f"{slug}_{i}"


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (text or "").strip()).strip("_")
    return cleaned or "block"
