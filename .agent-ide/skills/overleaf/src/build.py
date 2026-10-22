"""Build pipeline: store state -> template render -> TeX -> PDF.

The only place that touches both layers. It reads project state through
`src.store.api`, renders through `src.template.render`, then compiles.
"""
from __future__ import annotations

import os
import shutil

from src.store import api as store_api
from src.store import layout
from src.store.errors import DataError
from src.store.index import build_indexes
from src.store.schema import Manifest

from src.template import compile as tex_compile
from src.template import render as template_render
from src.template.registry import manifest_for


def build(agent_id: str, project_id: str, *, do_compile: bool = True) -> dict:
    project = store_api.read_project(agent_id, project_id)
    out_dir = layout.build_dir(agent_id, project_id)

    manifest = Manifest(manifest_for(project.template_id))
    # Build the citation/label index once and hand it to both passes, so
    # validation and the render-time warnings read the same data.
    indexes = build_indexes(project)
    issues = store_api.validate_project(project, manifest, indexes)
    if issues:
        raise DataError(
            issues[0].code,
            issues[0].path,
            f"{len(issues)} validation issue(s); first: {issues[0].message}",
        )

    placeholders = _load_placeholders(project.metadata)
    tex, tracked, block_types, warnings = template_render.render_project(
        project, out_dir, placeholders, indexes
    )

    tex_path = os.path.join(out_dir, f"{project_id}.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)

    warnings.extend(tex_compile.lint_tex(tex_path))

    result = {
        "tex": tex_path,
        "blocks": tracked,
        "block_types": block_types,
        "warnings": warnings,
        "pdf": None,
    }

    if do_compile:
        if not tex_compile.has_tectonic():
            raise DataError(
                "MALFORMED_FILE", None, "tectonic not found in PATH; re-run with --no-compile"
            )
        result["pdf"] = tex_compile.compile_tex(tex_path)

    return result


def clean_build(agent_id: str, project_id: str) -> str | None:
    """Remove the project's `build/` products directory; return it when removed."""
    out_dir = os.path.join(layout.project_dir(agent_id, project_id), layout.BUILD_DIRNAME)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
        return out_dir
    return None


def _load_placeholders(metadata: dict | None = None) -> dict:
    """Global `data/placeholders.json`, overlaid by project metadata.placeholders."""
    merged: dict = {}
    path = os.path.join(layout.data_root(), "placeholders.json")
    if os.path.exists(path):
        import json

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged.update(data)
        except (OSError, ValueError):
            pass
    if isinstance(metadata, dict):
        project_level = metadata.get("placeholders")
        if isinstance(project_level, dict):
            merged.update(project_level)
    return merged
