"""The single facade for CLI and build. Nothing outside `src/` imports deeper."""
from __future__ import annotations

import json
import os

from src.store import content_id
from src.store import disk as store, errors, layout, tree
from src.store.errors import DataError
from src.store.index import Indexes, build_indexes
from src.store.model import Block, Project, SCHEMA_VERSION, TreeNode
from src.store.schema import Manifest, check_content
from src.store.validate import Issue, validate_project


# --------------------------------------------------------------------------- init


def init_project(
    agent_id: str,
    project_id: str,
    template_id: str,
    metadata: dict | None = None,
    template_version: int = 1,
) -> Project:
    pdir = layout.project_dir(agent_id, project_id)
    if os.path.exists(pdir):
        raise DataError(errors.PROJECT_EXISTS, pdir, f"project '{project_id}' already exists")

    os.makedirs(layout.blocks_dir(agent_id, project_id), exist_ok=True)
    os.makedirs(layout.assets_dir(agent_id, project_id), exist_ok=True)

    meta = metadata if metadata is not None else {
        "title": f"My {template_id.upper()} Paper",
        "authors": [{"name": "Author", "institution": "Inst", "email": "e@mail.com"}],
        "abstract": "Abstract.",
    }
    store.write_project_json(
        agent_id,
        project_id,
        {
            "schema": SCHEMA_VERSION,
            "template": template_id,
            "template_version": template_version,
            "metadata": meta,
        },
    )
    return store.read_project(agent_id, project_id)


# --------------------------------------------------------------------------- read


def read_project(agent_id: str, project_id: str) -> Project:
    return store.read_project(agent_id, project_id)


def read_block(agent_id: str, project_id: str, rel_path: str) -> Block:
    project = store.read_project(agent_id, project_id)
    block = store.find_block(project, rel_path)
    if block is None:
        raise DataError(errors.BLOCK_NOT_FOUND, rel_path, "block does not exist")
    return block


def list_tree(agent_id: str, project_id: str) -> TreeNode:
    project = store.read_project(agent_id, project_id)
    return _to_tree(project.root)


def _to_tree(block: Block) -> TreeNode:
    return TreeNode(
        id=block.id,
        type=block.type,
        order=block.order,
        display=block.display,
        content=block.content,
        children=[_to_tree(c) for c in block.children],
    )


# --------------------------------------------------------------------------- write


def add_block(
    agent_id: str,
    project_id: str,
    block_type: str,
    content: dict,
    manifest: Manifest,
    parent: str = "",
    order: int | None = None,
    display: bool = True,
    project: Project | None = None,
) -> Block:
    """`project` lets a caller that already read the tree avoid a second read."""
    project = project or store.read_project(agent_id, project_id)
    return tree.add_block(
        agent_id, project_id, project, manifest, block_type, content, parent, order, display
    )


def delete_block(agent_id: str, project_id: str, rel_path: str) -> None:
    project = store.read_project(agent_id, project_id)
    tree.delete_block(agent_id, project_id, project, rel_path)


def move_block(
    agent_id: str,
    project_id: str,
    rel_path: str,
    manifest: Manifest,
    new_parent: str = "",
    new_order: int | None = None,
    project: Project | None = None,
) -> Block:
    project = project or store.read_project(agent_id, project_id)
    return tree.move_block(agent_id, project_id, project, manifest, rel_path, new_parent, new_order)


def duplicate_block(
    agent_id: str,
    project_id: str,
    rel_path: str,
    manifest: Manifest,
    new_parent: str = "",
    order: int | None = None,
    project: Project | None = None,
) -> tuple[Block, list[str]]:
    project = project or store.read_project(agent_id, project_id)
    return tree.duplicate_block(
        agent_id, project_id, project, manifest, rel_path, new_parent, order
    )


def update_meta(
    agent_id: str, project_id: str, patch: dict, project: Project | None = None
) -> Project:
    project = project or store.read_project(agent_id, project_id)
    if not isinstance(patch, dict):
        raise DataError(errors.CONTENT_INVALID, None, "metadata patch must be an object")
    project.metadata.update(patch)
    store.write_project_json(
        agent_id,
        project_id,
        {
            "schema": SCHEMA_VERSION,
            "template": project.template_id,
            "template_version": project.template_version,
            "metadata": project.metadata,
        },
    )
    return project


# --------------------------------------------------------------------------- content


def show_content(agent_id: str, project_id: str, selector_text: str) -> list[dict]:
    """The node(s) a content selector addresses, each with the id that names it.

    A plain selector must resolve to exactly one node — a typo raises
    `CONTENT_PATH_NOT_FOUND` rather than reading as an empty result.
    """
    project = store.read_project(agent_id, project_id)
    selector = content_id.parse(selector_text)
    if selector.is_query:
        matches = content_id.query(project, selector)
    else:
        matches = [content_id.resolve_match(project, selector)]
    return [
        {"content_id": content_id.of_trail(match.trail), "value": match.value}
        for match in matches
    ]


def set_content(
    agent_id: str,
    project_id: str,
    selector_text: str,
    value,
    manifest: Manifest,
    project: Project | None = None,
) -> dict:
    """Assign one node, then persist the single channel the write landed in.

    A content write passes the same `check_content` as `edit --path`, so an
    unlisted field fails here instead of at render time; an `order` write passes
    the same uniqueness guard as `edit --move`.
    """
    project = project or store.read_project(agent_id, project_id)
    selector = content_id.parse(selector_text)
    write = content_id.assign(project, selector, value)

    if write.channel == content_id.CHANNEL_METADATA:
        store.write_project_json(
            agent_id,
            project_id,
            {
                "schema": SCHEMA_VERSION,
                "template": project.template_id,
                "template_version": project.template_version,
                "metadata": project.metadata,
            },
        )
    else:
        block = store.find_block(project, write.rel_path)
        if block is None:  # pragma: no cover - assign resolved it a moment ago
            raise DataError(errors.BLOCK_NOT_FOUND, write.rel_path, "block does not exist")
        if write.channel == content_id.CHANNEL_CONTENT:
            check_content(block.type, block.content, manifest, block.rel_path)
        elif selector.steps[-1] == ("child", "order"):
            _guard_order(project, block)
        store.write_block(agent_id, project_id, block)

    matches = content_id.query(project, selector)
    return {
        "content_id": content_id.of_trail(matches[0].trail) if len(matches) == 1 else selector_text,
        "channel": write.channel,
        "rel_path": write.rel_path,
    }


def _guard_order(project: Project, block: Block) -> None:
    """Guard an `order` write that did not come through `move_block`."""
    parent_rel = block.rel_path.rsplit("/", 1)[0] if "/" in block.rel_path else ""
    parent = project.root if not parent_rel else project.find(parent_rel)
    siblings = parent.children if parent is not None else []
    tree.assert_order_free(siblings, block.order, parent_rel or "/", ignore=block)


# --------------------------------------------------------------------------- validate


def validate(agent_id: str, project_id: str, manifest: Manifest) -> list[Issue]:
    project = store.read_project(agent_id, project_id)
    return validate_project(project, manifest)


def indexes(agent_id: str, project_id: str) -> Indexes:
    return build_indexes(store.read_project(agent_id, project_id))


# --------------------------------------------------------------------------- bulk


def search_blocks(agent_id: str, project_id: str, query: str) -> list[dict]:
    """Return blocks whose serialized content contains `query`."""
    project = store.read_project(agent_id, project_id)
    hits: list[dict] = []
    for block in project.blocks():
        blob = json.dumps(block.content, ensure_ascii=False)
        if query in blob:
            hits.append({"rel_path": block.rel_path, "type": block.type})
    return hits


def replace_in_blocks(agent_id: str, project_id: str, old: str, new: str) -> list[str]:
    """Replace `old` with `new` across every block content string. Returns changed paths."""
    if not old:
        raise DataError(errors.CONTENT_INVALID, None, "search string must not be empty")
    project = store.read_project(agent_id, project_id)
    changed: list[str] = []
    for block in project.blocks():
        new_content, did = _replace_strings(block.content, old, new)
        if did:
            block.content = new_content
            store.write_block(agent_id, project_id, block)
            changed.append(block.rel_path)
    return changed


def delete_project(agent_id: str, project_id: str) -> str:
    """Move a project directory to the OS Trash (or `data/trash`). Returns the target."""
    import datetime
    import shutil

    project = store.read_project(agent_id, project_id)
    pdir = project.root_dir

    trash = os.path.expanduser("~/.Trash")
    if not os.path.isdir(trash):
        trash = os.path.join(layout.data_root(), "trash")
        os.makedirs(trash, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = os.path.join(
        trash, f"{agent_id}_{project_id.replace('/', '_')}_overleaf_deleted_{stamp}"
    )
    shutil.move(pdir, target)
    return target


def _replace_strings(obj, old: str, new: str) -> tuple[object, bool]:
    if isinstance(obj, dict):
        changed = False
        out = {}
        for key, value in obj.items():
            out[key], sub = _replace_strings(value, old, new)
            changed |= sub
        return out, changed
    if isinstance(obj, list):
        changed = False
        out_list = []
        for item in obj:
            new_item, sub = _replace_strings(item, old, new)
            changed |= sub
            out_list.append(new_item)
        return out_list, changed
    if isinstance(obj, str) and old in obj:
        return obj.replace(old, new), True
    return obj, False


def dump(obj) -> str:
    """Render an api result as JSON for the CLI."""
    if isinstance(obj, TreeNode):
        return json.dumps(_tree_dict(obj), indent=2, ensure_ascii=False)
    if isinstance(obj, Block):
        return json.dumps(
            {
                "id": obj.id,
                "rel_path": obj.rel_path,
                "type": obj.type,
                "order": obj.order,
                "display": obj.display,
                "content": obj.content,
            },
            indent=2,
            ensure_ascii=False,
        )
    if isinstance(obj, Project):
        return json.dumps(
            {
                "id": obj.id,
                "template": obj.template_id,
                "template_version": obj.template_version,
                "metadata": obj.metadata,
            },
            indent=2,
            ensure_ascii=False,
        )
    if isinstance(obj, Indexes):
        return json.dumps(
            {"citations": obj.citations, "labels": obj.labels}, indent=2, ensure_ascii=False
        )
    if isinstance(obj, list):
        return json.dumps(
            [{"code": i.code, "path": i.path, "message": i.message} for i in obj],
            indent=2,
            ensure_ascii=False,
        )
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def _tree_dict(node: TreeNode) -> dict:
    return {
        "id": node.id,
        "type": node.type,
        "order": node.order,
        "display": node.display,
        "content": node.content,
        "children": [_tree_dict(c) for c in node.children],
    }
