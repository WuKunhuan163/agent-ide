"""Citation and cross-reference index construction.

Replaces the old build-time `os.walk` that only inspected `content["text"]`.
Sources:
  - citation keys: any `bibliography` block's `content["bibtex"]`
  - label keys:    any block's `content["label"]`
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.store.model import Project

_BIB_ENTRY_RE = re.compile(r"@[A-Za-z]+\s*\{\s*([^,\s]+)\s*,")


@dataclass
class Indexes:
    citations: dict[str, str] = field(default_factory=dict)  # key -> block rel_path
    labels: dict[str, str] = field(default_factory=dict)  # label -> block rel_path

    def has_citation(self, key: str) -> bool:
        return key in self.citations

    def has_label(self, label: str) -> bool:
        return label in self.labels


def build_indexes(project: Project) -> Indexes:
    """Indexes cover the rendered document only: hidden subtrees contribute no
    labels and no citation keys, so a visible `\\ref` to a hidden label is a real
    `LABEL_UNDEFINED` rather than a silently dangling reference in the PDF."""
    idx = Indexes()
    for block in project.visible_blocks():
        content = block.content if isinstance(block.content, dict) else {}

        if block.type == "bibliography":
            bibtex = content.get("bibtex")
            if isinstance(bibtex, str):
                for key in _BIB_ENTRY_RE.findall(bibtex):
                    idx.citations.setdefault(key.strip(), block.rel_path)

        label = content.get("label")
        if isinstance(label, str) and label.strip():
            idx.labels.setdefault(label.strip(), block.rel_path)
    return idx
