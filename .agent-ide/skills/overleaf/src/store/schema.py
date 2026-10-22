"""Content validation driven by a template manifest (a plain dict).

The data plane never imports template code. A manifest is:

    {
      "template": "cvpr",
      "version": 1,
      "blocks": {
        "section": {
          "required": ["title"],
          "optional": ["label", "display"],
          "leaf": false,
          "allowed_children": ["subsection", "text", "*"]
        },
        ...
      }
    }
"""
from __future__ import annotations

import json
import os

from src.store import errors
from src.store.errors import DataError


class BlockSpec:
    def __init__(self, name: str, raw: dict) -> None:
        self.name = name
        self.required: tuple[str, ...] = tuple(raw.get("required", []))
        self.optional: tuple[str, ...] = tuple(raw.get("optional", []))
        self.leaf: bool = bool(raw.get("leaf", not raw.get("container", False)))
        self.allowed_children = raw.get("allowed_children")

    def accepts(self, child_type: str) -> bool:
        if self.allowed_children is None:
            return not self.leaf
        if "*" in self.allowed_children:
            return True
        return child_type in self.allowed_children


class Manifest:
    def __init__(self, raw: dict) -> None:
        self.template = raw.get("template", "")
        self.version = raw.get("version", 0)
        self.required_metadata: tuple[str, ...] = tuple(raw.get("required_metadata", []))
        self.blocks: dict[str, BlockSpec] = {
            name: BlockSpec(name, spec or {}) for name, spec in (raw.get("blocks") or {}).items()
        }

    def spec(self, block_type: str, path: str | None = None) -> BlockSpec:
        if block_type not in self.blocks:
            raise DataError(
                errors.BLOCK_TYPE_UNKNOWN,
                path,
                f"type {block_type!r} not in manifest",
                field="type",
            )
        return self.blocks[block_type]


def load_manifest(path: str) -> Manifest:
    """Load a template manifest from `templates/<id>/template.json`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise DataError(errors.TEMPLATE_NOT_FOUND, path, "manifest does not exist")
    except json.JSONDecodeError as exc:
        raise DataError(errors.MALFORMED_FILE, path, f"invalid JSON: {exc}")
    if not isinstance(raw, dict):
        raise DataError(errors.MALFORMED_FILE, path, "manifest must be an object")
    return Manifest(raw)


def check_content(
    block_type: str,
    content: dict,
    manifest: Manifest,
    path: str | None = None,
) -> None:
    """Validate a block's content dict against the manifest entry for its type."""
    spec = manifest.spec(block_type, path)
    if not isinstance(content, dict):
        raise DataError(
            errors.CONTENT_INVALID, path, "content must be an object", field="content"
        )

    missing = [k for k in spec.required if k not in content]
    if missing:
        raise DataError(
            errors.CONTENT_INVALID,
            path,
            f"missing required content field(s): {', '.join(missing)}",
            field="content",
        )

    known = set(spec.required) | set(spec.optional)
    if known:
        unknown = [k for k in content if k not in known]
        if unknown:
            raise DataError(
                errors.CONTENT_INVALID,
                path,
                f"unknown content field(s): {', '.join(sorted(unknown))}",
                field="content",
            )
