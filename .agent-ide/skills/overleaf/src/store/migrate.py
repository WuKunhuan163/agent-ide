"""Import a project written by the pre-rewrite skill.

The old layout was a directory tree of numbered block folders plus one flat
`metadata.json`:

    <old>/metadata.json                     {template, title, authors, abstract, ...}
    <old>/root/01_section/block.json        {type, content}
    <old>/root/01_section/01_text/block.json

The current layout is `project.json` (schema, template, template_version,
metadata) plus `blocks/<id>/block.json` with a stored `order`. The tree shape is
the same; the names, the metadata envelope and the ordering are not.

This module writes through the store API rather than by hand, so the result is a
project the rest of the skill can read — every block goes through the same
validation as `edit add`.
"""
from __future__ import annotations

import json
import os
import re

from src.store import api as store_api
from src.store import errors
from src.store.layout import resolve_arg
from src.store.errors import DataError
from src.store.schema import Manifest
from src.template.registry import manifest_for

_INDEX_RE = re.compile(r"^(\d+)_(.+)$")


def migrate_legacy(
    agent_id: str, source: str, project_id: str | None = None
) -> dict:
    """Copy one old-layout project into the current store; return a summary."""
    source = resolve_arg(source)
    meta_path = os.path.join(source, "metadata.json")
    if not os.path.isfile(meta_path):
        raise DataError(
            errors.MALFORMED_FILE, source, "no metadata.json: not an old-layout project"
        )
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(errors.MALFORMED_FILE, meta_path, f"unreadable metadata.json: {exc}")
    if not isinstance(meta, dict):
        raise DataError(errors.MALFORMED_FILE, meta_path, "metadata.json must be an object")

    template = meta.get("template")
    if not isinstance(template, str) or not template.strip():
        raise DataError(
            errors.MALFORMED_FILE, meta_path, "metadata.json has no template", field="template"
        )
    template = template.strip()

    target = project_id or os.path.basename(source.rstrip(os.sep))
    metadata = {key: value for key, value in meta.items() if key != "template"}

    manifest = Manifest(manifest_for(template))
    store_api.init_project(agent_id, target, template, metadata=metadata)

    report: dict = {
        "project": target,
        "template": template,
        "blocks": 0,
        "warnings": [],
    }
    root = os.path.join(source, "root")
    if os.path.isdir(root):
        _walk(agent_id, target, root, "", manifest, report)
    return report


def _walk(
    agent_id: str,
    project_id: str,
    path: str,
    parent: str,
    manifest: Manifest,
    report: dict,
) -> None:
    """Depth-first, in the old folder's own order, so `order` stays monotonic."""
    for name in sorted(os.listdir(path)):
        folder = os.path.join(path, name)
        if not os.path.isdir(folder):
            continue
        block_file = os.path.join(folder, "block.json")
        if not os.path.isfile(block_file):
            nested = _count_nested(folder)
            report["warnings"].append(
                f"skipped {os.path.relpath(folder, path)}: no block.json"
                + (f" ({nested} nested block(s) dropped)" if nested else "")
            )
            continue
        try:
            with open(block_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            report["warnings"].append(f"skipped {name}: {exc}")
            continue
        if not isinstance(data, dict) or not isinstance(data.get("type"), str):
            report["warnings"].append(f"skipped {name}: block.json has no type")
            continue

        match = _INDEX_RE.match(name)
        index = int(match.group(1)) if match else 0
        content = data.get("content")
        if not isinstance(content, dict):
            report["warnings"].append(f"{name}: content is not an object; used {{}}")
            content = {}

        try:
            block = store_api.add_block(
                agent_id,
                project_id,
                data["type"],
                content,
                manifest,
                parent=parent,
                order=index * 10,
                display=bool(data.get("display", True)),
            )
        except DataError as exc:
            report["warnings"].append(f"{name}: {exc.code} {exc.detail}")
            continue

        report["blocks"] += 1
        _walk(agent_id, project_id, folder, block.rel_path, manifest, report)


def _count_nested(folder: str) -> int:
    """How many block.json files sit below `folder`, for the skip warning."""
    total = 0
    for root, _dirs, files in os.walk(folder):
        if "block.json" in files and root != folder:
            total += 1
    return total
