"""Structural tree mutations. Every entry point validates fully, then writes.

Invariants enforced here:
  - block type exists in the manifest (via schema)
  - content matches the manifest entry for the type
  - sibling `order` values are unique
  - a leaf cannot receive children; a parent's allowed_children is respected
"""
from __future__ import annotations

import copy

from src.store import disk as store, errors, layout
from src.store.errors import DataError
from src.store.model import DEFAULT_ORDER_STEP, Block, Project
from src.store.schema import Manifest, check_content


# --------------------------------------------------------------------------- helpers


def _siblings_for(project: Project, parent_rel: str) -> tuple[Block, list[Block]]:
    """Return (parent_block, sibling list) for a parent rel path ('' = root)."""
    if not parent_rel:
        return project.root, project.root.children
    parent = project.find(parent_rel)
    if parent is None:
        raise DataError(errors.BLOCK_NOT_FOUND, parent_rel, "parent block does not exist")
    return parent, parent.children


def assert_order_free(siblings: list[Block], order: int, path: str, ignore: Block | None = None) -> None:
    for sib in siblings:
        if sib is ignore:
            continue
        if sib.order == order:
            raise DataError(
                errors.ORDER_CONFLICT,
                path,
                f"order {order} already used by '{sib.id}'",
                field="order",
            )


def _next_order(siblings: list[Block]) -> int:
    if not siblings:
        return DEFAULT_ORDER_STEP
    return max(sib.order for sib in siblings) + DEFAULT_ORDER_STEP


# --------------------------------------------------------------------------- mutations


def add_block(
    agent_id: str,
    project_id: str,
    project: Project,
    manifest: Manifest,
    block_type: str,
    content: dict,
    parent_rel: str = "",
    order: int | None = None,
    display: bool = True,
) -> Block:
    parent_rel = layout.normalize_rel_path(parent_rel)
    check_content(block_type, content, manifest, parent_rel or None)

    parent, siblings = _siblings_for(project, parent_rel)
    if parent is not project.root:
        spec = manifest.spec(parent.type, parent_rel or None)
        if not spec.accepts(block_type):
            if spec.leaf:
                raise DataError(
                    errors.LEAF_CANNOT_HAVE_CHILDREN,
                    parent_rel,
                    f"'{parent.type}' is a leaf and cannot have children",
                )
            raise DataError(
                errors.CHILD_NOT_ALLOWED,
                parent_rel,
                f"'{parent.type}' does not allow child type '{block_type}'",
            )

    resolved_order = _next_order(siblings) if order is None else order
    assert_order_free(siblings, resolved_order, parent_rel or "/")

    container = layout.children_dir(agent_id, project_id, parent_rel)
    slug = store.alloc_slug(container, block_type)
    rel = f"{parent_rel}/{slug}" if parent_rel else slug

    block = Block(
        id=slug,
        type=block_type,
        order=resolved_order,
        display=display,
        content=content,
        rel_path=rel,
    )
    store.write_block(agent_id, project_id, block)
    parent.children.append(block)
    _sort(parent.children)
    return block


def delete_block(
    agent_id: str,
    project_id: str,
    project: Project,
    rel_path: str,
) -> None:
    rel_path = layout.normalize_rel_path(rel_path)
    parent_rel, _, _ = rel_path.rpartition("/")
    parent, siblings = _siblings_for(project, parent_rel)
    target = next((b for b in siblings if b.rel_path == rel_path), None)
    if target is None:
        raise DataError(errors.BLOCK_NOT_FOUND, rel_path, "block does not exist")
    store.remove_block_dir(agent_id, project_id, rel_path)
    siblings.remove(target)


def move_block(
    agent_id: str,
    project_id: str,
    project: Project,
    manifest: Manifest,
    rel_path: str,
    new_parent: str = "",
    new_order: int | None = None,
) -> Block:
    rel_path = layout.normalize_rel_path(rel_path)
    new_parent = layout.normalize_rel_path(new_parent)
    if new_parent == rel_path or new_parent.startswith(rel_path + "/"):
        raise DataError(errors.PATH_UNSAFE, rel_path, "cannot move a block into itself")

    block = project.find(rel_path)
    if block is None:
        raise DataError(errors.BLOCK_NOT_FOUND, rel_path, "block does not exist")

    old_parent_rel, _, _ = rel_path.rpartition("/")
    _, old_siblings = _siblings_for(project, old_parent_rel)
    old_siblings.remove(block)

    new_parent_block, new_siblings = _siblings_for(project, new_parent)
    if new_parent_block is not project.root:
        spec = manifest.spec(new_parent_block.type, new_parent or None)
        if spec.leaf:
            raise DataError(
                errors.LEAF_CANNOT_HAVE_CHILDREN,
                new_parent,
                f"'{new_parent_block.type}' is a leaf and cannot have children",
            )
        if not spec.accepts(block.type):
            raise DataError(
                errors.CHILD_NOT_ALLOWED,
                new_parent,
                f"'{new_parent_block.type}' does not allow child type '{block.type}'",
            )

    resolved_order = _next_order(new_siblings) if new_order is None else new_order
    assert_order_free(new_siblings, resolved_order, new_parent or "/")

    if new_parent == old_parent_rel:
        new_rel = rel_path
    else:
        # A move into a parent that already holds this name re-allocates the slug,
        # exactly like `add_block` / `duplicate_block`: ids are unique per
        # directory, not globally.
        container = layout.children_dir(agent_id, project_id, new_parent)
        slug = store.alloc_slug(container, block.id)
        new_rel = f"{new_parent}/{slug}" if new_parent else slug
        store.rename_block_dir(agent_id, project_id, rel_path, new_rel)
        block.id = slug
        _rebase(block, new_rel)
    block.order = resolved_order
    store.write_block(agent_id, project_id, block)
    new_siblings.append(block)
    _sort(new_siblings)
    return block


def duplicate_block(
    agent_id: str,
    project_id: str,
    project: Project,
    manifest: Manifest,
    rel_path: str,
    new_parent: str = "",
    order: int | None = None,
) -> tuple[Block, list[str]]:
    """Deep-copy a subtree under `new_parent`, allocating fresh slugs.

    Returns the new top-level copy and every `label` found in the copied
    subtree: labels are copied verbatim, so duplicates are the caller's to fix.
    """
    rel_path = layout.normalize_rel_path(rel_path)
    new_parent = layout.normalize_rel_path(new_parent)
    if new_parent == rel_path or new_parent.startswith(rel_path + "/"):
        raise DataError(errors.PATH_UNSAFE, rel_path, "cannot duplicate a block into itself")
    source = project.find(rel_path)
    if source is None:
        raise DataError(errors.BLOCK_NOT_FOUND, rel_path, "block does not exist")

    parent, siblings = _siblings_for(project, new_parent)
    if parent is not project.root:
        spec = manifest.spec(parent.type, new_parent or None)
        if not spec.accepts(source.type):
            if spec.leaf:
                raise DataError(
                    errors.LEAF_CANNOT_HAVE_CHILDREN,
                    new_parent,
                    f"'{parent.type}' is a leaf and cannot have children",
                )
            raise DataError(
                errors.CHILD_NOT_ALLOWED,
                new_parent,
                f"'{parent.type}' does not allow child type '{source.type}'",
            )

    resolved_order = _next_order(siblings) if order is None else order
    assert_order_free(siblings, resolved_order, new_parent or "/")

    labels: list[str] = []

    def copy_into(block: Block, dest_parent: str, dest_order: int) -> Block:
        container = layout.children_dir(agent_id, project_id, dest_parent)
        slug = store.alloc_slug(container, block.type)
        rel = f"{dest_parent}/{slug}" if dest_parent else slug
        clone = Block(
            id=slug,
            type=block.type,
            order=dest_order,
            display=block.display,
            content=copy.deepcopy(block.content),
            rel_path=rel,
        )
        labels.extend(_labels_in(clone.content))
        store.write_block(agent_id, project_id, clone)
        for child in block.children:
            clone.children.append(copy_into(child, rel, child.order))
        _sort(clone.children)
        return clone

    clone = copy_into(source, new_parent, resolved_order)
    parent.children.append(clone)
    _sort(parent.children)
    return clone, labels


def _labels_in(content, out: list[str] | None = None) -> list[str]:
    out = [] if out is None else out
    if isinstance(content, dict):
        for key, value in content.items():
            if key == "label" and isinstance(value, str) and value:
                out.append(value)
            else:
                _labels_in(value, out)
    elif isinstance(content, list):
        for item in content:
            _labels_in(item, out)
    return out


# --------------------------------------------------------------------------- internals


def _sort(siblings: list[Block]) -> None:
    siblings.sort(key=lambda b: (b.order, b.id))


def _rebase(block: Block, new_rel: str) -> None:
    block.rel_path = new_rel
    for child in block.children:
        _rebase(child, f"{new_rel}/{child.id}")
