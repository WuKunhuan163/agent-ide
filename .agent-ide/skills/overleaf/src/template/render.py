"""Assemble a rendered TeX document from a project's block tree.

The template layer never writes the project on disk. It reads the in-memory
`Project` / `TreeNode` handed over by the store layer and returns TeX strings.
"""
from __future__ import annotations

import os
import shutil

from src.store import errors, layout
from src.store.errors import DataError
from src.store.index import build_indexes
from src.store.model import Block, Project
from src.store.schema import Manifest, check_content
from src.store.validate import extract_cite_keys, extract_ref_labels, text_of

from src.template.block_base import BaseBlock
from src.template.registry import load_instance, resolve_block_class


def render_project(
    project: Project,
    out_dir: str,
    placeholders: dict | None = None,
    indexes=None,
) -> tuple[str, str, dict[str, str], list[str]]:
    """Render a project's tree as (tex, block_ids, block_types, warnings)."""
    instance_id = project.template_id
    spec, template = load_instance(instance_id)

    if spec.get("version", 1) != project.template_version:
        raise DataError(
            errors.TEMPLATE_VERSION_MISMATCH,
            layout.project_file(project.agent_id, project.id),
            f"project expects version {project.template_version}, instance provides {spec.get('version', 1)}",
        )

    prepare_build_dir(project, out_dir)

    # The manifest is the single authority for required/optional content fields:
    # block plugins no longer re-list them, so the render boundary enforces it.
    manifest = Manifest(spec)

    idx = indexes if indexes is not None else build_indexes(project)
    warnings: list[str] = []
    tracked: list[str] = []
    tracked_types: dict[str, str] = {}

    def render_node(block: Block, parent_rel: str = "") -> str:
        if not BaseBlock.should_display(
            {"display": block.display, "content": block.content}
        ):
            return ""

        check_content(block.type, block.content, manifest, block.rel_path)
        children_tex = "".join(render_node(child, block.rel_path) for child in block.children)

        data = {
            "type": block.type,
            "id": block.id,
            "children_ids": [c.id for c in block.children],
            "content": dict(block.content),
        }
        data["content"]["_project_dir"] = project.root_dir
        data["content"]["_output_dir"] = out_dir
        if placeholders:
            data["content"] = _apply_placeholders(data["content"], placeholders)

        block_cls = resolve_block_class(instance_id, block.type)
        oop_block = block_cls(block.id, parent_rel, data["children_ids"], data["content"])

        _check_refs(block, warnings, idx)

        tex = oop_block.render(children_tex)
        tracked.append(block.id)
        tracked_types[block.id] = block.type
        return f"\n% [BEGIN_BLOCK: {block.id}]\n{tex}\n% [END_BLOCK: {block.id}]\n"

    body = "".join(render_node(block) for block in project.root.children)

    state = {
        "metadata": project.metadata,
        "rendered_content": body,
        "block_types": tracked_types,
        "project_dir": project.root_dir,
        "output_dir": out_dir,
    }
    template.validate_bibliography_citations(state)
    tex = template.build_document(state)
    if placeholders:
        tex = _apply_placeholders_str(tex, placeholders)

    if r"\end{document}" not in tex:
        raise DataError(errors.MALFORMED_FILE, None, "rendered TeX is missing \\end{document}")
    for name in tracked:
        if f"% [BEGIN_BLOCK: {name}]" not in tex:
            raise DataError(
                errors.MALFORMED_FILE, None, f"block '{name}' missing from rendered TeX"
            )

    return tex, tracked, tracked_types, warnings


def copy_instance_assets(instance_id: str, out_dir: str) -> None:
    """Copy .sty/.cls/.bst plus asset dirs from an instance into the build dir."""
    spec, _ = load_instance(instance_id)
    idir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances", instance_id)
    assets = spec.get("assets", ["assets", "thumbnails"])
    for item in os.listdir(idir):
        full = os.path.join(idir, item)
        if item in ("__pycache__", "blocks"):
            continue
        if os.path.isdir(full):
            if item in assets:
                shutil.copytree(full, os.path.join(out_dir, item), dirs_exist_ok=True)
        elif item.endswith((".sty", ".cls", ".bst")):
            shutil.copy2(full, os.path.join(out_dir, item))


# --------------------------------------------------------------------------- internals


def prepare_build_dir(project: Project, out_dir: str) -> None:
    """Materialize the build directory in one place.

    Project assets first, then instance assets (an instance file wins on a name
    clash), then the project's `references.bib`. Rendering adds whatever the
    block plugins write: figure images, and a `bibliography` block's
    `references.bib`.
    """
    os.makedirs(out_dir, exist_ok=True)
    src = layout.assets_dir(project.agent_id, project.id)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(out_dir, "assets"), dirs_exist_ok=True)
    copy_instance_assets(project.template_id, out_dir)
    bib = os.path.join(project.root_dir, "references.bib")
    if os.path.isfile(bib):
        shutil.copy2(bib, os.path.join(out_dir, "references.bib"))


def _check_refs(block: Block, warnings: list[str], idx) -> None:
    # The same extractor `validate` uses, so the two can never disagree about
    # which text carries citations and cross-references.
    text = text_of(block.content)
    for key in extract_cite_keys(text):
        if not idx.has_citation(key):
            warnings.append(f"{block.rel_path}: undefined citation '{key}'")
    for label in extract_ref_labels(text):
        if not idx.has_label(label):
            warnings.append(f"{block.rel_path}: undefined label '{label}'")


def _apply_placeholders(content: dict, placeholders: dict) -> dict:
    out = {}
    for key, value in content.items():
        if isinstance(value, str):
            out[key] = _apply_placeholders_str(value, placeholders)
        else:
            out[key] = value
    return out


def _apply_placeholders_str(text: str, placeholders: dict) -> str:
    for key, value in placeholders.items():
        # An empty key would match everywhere and shred the document.
        if key:
            text = text.replace(key, str(value))
    return text
