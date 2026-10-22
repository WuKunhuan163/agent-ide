"""Base class for a template instance.

An instance is a directory under `instances/<id>/` holding `template.json`
plus assets. If `template.json` declares `"python": "<file>"`, that file is
imported and its `Template` class takes over document assembly; otherwise the
declarative path in `render.py` is used.
"""
from __future__ import annotations

import json
import os
import re

from src.store import errors
from src.store.errors import DataError


class BaseTemplate:
    """Declarative template: preamble fragments + body assembly rules."""

    def __init__(self, template_dir: str, spec: dict | None = None) -> None:
        self.template_dir = template_dir
        self.spec = spec if spec is not None else self._load_spec()
        self.name = self.spec.get("name", os.path.basename(template_dir))
        self.version = self.spec.get("version", 1)
        self.required_metadata: list[str] = list(self.spec.get("required_metadata", []))

    def _load_spec(self) -> dict:
        path = os.path.join(self.template_dir, "template.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_state(self, state: dict) -> bool:
        metadata = state.get("metadata", {})
        for key in self.required_metadata:
            if key not in metadata:
                raise DataError(
                    errors.METADATA_INCOMPLETE,
                    None,
                    f"missing required metadata field '{key}' for {self.name}",
                    field=key,
                )
        return True

    def validate_bibliography_citations(self, state: dict) -> None:
        """Cross-check inline `[N]` citations against `references.bib` entries.

        Only runs when the instance implements `parse_bibliography_entries`
        and `iter_citable_texts`.
        """
        parse_entries = getattr(self, "parse_bibliography_entries", None)
        iter_texts = getattr(self, "iter_citable_texts", None)
        if not parse_entries or not iter_texts:
            return
        meta = state.get("metadata", {})
        entries = parse_entries(state.get("project_dir", ""))
        if not entries:
            return
        for text in iter_texts(meta):
            for match in re.finditer(r"\[(\d+)\]", str(text)):
                key = f"ref{int(match.group(1)):03d}"
                if key not in entries:
                    raise DataError(
                        errors.CITATION_UNDEFINED,
                        None,
                        f"citation [{match.group(1)}] has no entry '{key}' in references.bib",
                    )

    def default_metadata(self) -> dict:
        """Seed metadata written by `init` for this instance."""
        seed = self.spec.get("default_metadata")
        if isinstance(seed, dict):
            return json.loads(json.dumps(seed))
        return {
            "title": f"My {self.name.upper()} Paper",
            "authors": [{"name": "Author", "institution": "Inst", "email": "e@mail.com"}],
            "abstract": "Abstract.",
        }

    def render_preamble(self, state: dict) -> str:
        """Preamble lines, before `\\begin{document}`."""
        header = self.spec.get("preamble_header", [])
        return "\n".join(header)

    def build_document(self, state: dict) -> str:
        """Full .tex document for a rendered body."""
        self.validate_state(state)
        meta = state.get("metadata", {})

        lines: list[str] = [self.render_preamble(state), r"\begin{document}"]

        abstract = meta.get("abstract")
        if abstract and self.spec.get("abstract_environment", True):
            lines.append(r"\begin{abstract}")
            lines.append(abstract)
            lines.append(r"\end{abstract}")

        lines.append(state.get("rendered_content", ""))
        lines.append(r"\end{document}")
        return "\n".join(lines)
