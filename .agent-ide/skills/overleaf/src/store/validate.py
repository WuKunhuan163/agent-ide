"""Project-level composite validation and TeX citation/ref scanning."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.store import errors, layout
from src.store.errors import DataError
from src.store.index import Indexes, build_indexes
from src.store.model import Project
from src.store.schema import Manifest, check_content

_CITE_RE = re.compile(r"\\cite(?:[A-Za-z*]+)?\{([^}]+)\}")
_REF_RE = re.compile(r"\\(?:eq|auto)?ref\{([^}]+)\}")


@dataclass
class Issue:
    code: str
    path: str
    message: str


def validate_project(
    project: Project, manifest: Manifest, indexes: Indexes | None = None
) -> list[Issue]:
    """Return every issue found. Never raises for data-level problems.

    `indexes` lets a caller that already built them (the build pipeline) avoid
    rebuilding the citation/label index a second time.
    """
    issues: list[Issue] = []

    # template binding
    if manifest.template and project.template_id != manifest.template:
        issues.append(
            Issue(
                errors.TEMPLATE_NOT_FOUND,
                layout.project_file(project.agent_id, project.id),
                f"project template '{project.template_id}' is not '{manifest.template}'",
            )
        )
    if manifest.version and project.template_version != manifest.version:
        issues.append(
            Issue(
                errors.TEMPLATE_VERSION_MISMATCH,
                layout.project_file(project.agent_id, project.id),
                f"expected template_version {manifest.version}, got {project.template_version}",
            )
        )

    # required metadata for the bound template
    missing_meta = [k for k in manifest.required_metadata if k not in project.metadata]
    if missing_meta:
        issues.append(
            Issue(
                errors.METADATA_INCOMPLETE,
                layout.project_file(project.agent_id, project.id),
                f"missing required metadata field(s): {', '.join(missing_meta)}",
            )
        )

    # optional chapter gate: body_sections may not exceed allowed_sections
    allowed = project.metadata.get("allowed_sections")
    if isinstance(allowed, list):
        body = project.metadata.get("body_sections", [])
        n_body = len(body) if isinstance(body, list) else 0
        if n_body > len(allowed):
            issues.append(
                Issue(
                    errors.SECTION_LIMIT,
                    layout.project_file(project.agent_id, project.id),
                    f"body_sections has {n_body} entries but allowed_sections permits {len(allowed)}",
                )
            )

    # per-block content. Hidden subtrees are skipped: `display: false` means "as
    # if it did not exist", which is what makes hiding useful for focusing a
    # build — draft or half-written content may sit there without blocking it.
    for block in project.visible_blocks():
        try:
            check_content(block.type, block.content, manifest, block.rel_path)
        except DataError as exc:
            issues.append(Issue(exc.code, block.rel_path, exc.detail))

    # sibling order uniqueness. Deliberately over the *whole* tree: `order` is a
    # stored structural invariant, and hiding a block must not mask a duplicate
    # that would resurface the moment it is shown again.
    for parent, siblings in _walk_pairs(project):
        seen: dict[int, str] = {}
        for sib in siblings:
            if sib.order in seen:
                issues.append(
                    Issue(
                        errors.ORDER_CONFLICT,
                        parent,
                        f"'{sib.id}' and '{seen[sib.order]}' share order {sib.order}",
                    )
                )
            seen[sib.order] = sib.id

    # citations and cross-references, over the rendered view only: a `\cite` in a
    # hidden block is not in the document, and a `\label` in one is not
    # addressable — the same pruning the renderer applies.
    idx = indexes if indexes is not None else build_indexes(project)
    for block in project.visible_blocks():
        text = text_of(block.content)
        for key in extract_cite_keys(text):
            if not idx.has_citation(key):
                issues.append(
                    Issue(errors.CITATION_UNDEFINED, block.rel_path, f"undefined citation '{key}'")
                )
        for label in extract_ref_labels(text):
            if not idx.has_label(label):
                issues.append(
                    Issue(errors.LABEL_UNDEFINED, block.rel_path, f"undefined label '{label}'")
                )
    return issues


def extract_cite_keys(text: str) -> list[str]:
    """Citation keys referenced by `\\cite...` commands in `text`."""
    keys: list[str] = []
    for group in _CITE_RE.findall(text):
        keys.extend(k.strip() for k in group.split(",") if k.strip())
    return keys


def extract_ref_labels(text: str) -> list[str]:
    """Label names referenced by `\\ref` / `\\eqref` / `\\autoref` in `text`."""
    return [lbl.strip() for lbl in _REF_RE.findall(text) if lbl.strip()]


def text_of(content: dict) -> str:
    """Every string in `content`, preferring `text`.

    The single extractor for citation/label scanning: validate and render must
    look at exactly the same text or one of them silently misses a reference.
    """
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    if isinstance(text, str):
        return text
    parts = [v for v in content.values() if isinstance(v, str)]
    return "\n".join(parts)


def _walk_pairs(project: Project):
    stack = [(project.root.rel_path or "/", project.root.children)]
    while stack:
        parent, siblings = stack.pop()
        yield parent, siblings
        for sib in siblings:
            stack.append((sib.rel_path, sib.children))
