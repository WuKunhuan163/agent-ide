"""Bulleted or numbered list.

One plugin for both environments: `style` picks `itemize` or `enumerate`, so an
instance does not need a second type just to number its items. Items are verbatim
LaTeX, which covers bold lead-ins, inline math and citations; a list that needs a
figure or a second paragraph belongs in a `text` block instead.
"""
from __future__ import annotations

from src.store import errors
from src.store.errors import DataError

from src.template.block_base import BaseBlock


class Block(BaseBlock):
    _STYLES = ("itemize", "enumerate")

    def validate(self) -> None:
        super().validate()

        items = self.content.get("items")
        if not isinstance(items, list) or not items:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                "list block needs a non-empty 'items' list",
                field="items",
            )
        if not all(isinstance(item, str) for item in items):
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                "'items' must be a list of strings",
                field="items",
            )

        style = str(self.content.get("style", "itemize"))
        if style not in self._STYLES:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                f"'style' must be one of {', '.join(self._STYLES)}",
                field="style",
            )

    def render(self, child_contents: str = "") -> str:
        style = str(self.content.get("style", "itemize"))
        lines = [f"\\begin{{{style}}}"]
        # `compact` has to be set inside the environment; no enumitem is loaded.
        if self.content.get("compact", False):
            lines.append("\\setlength{\\itemsep}{0pt}")
            lines.append("\\setlength{\\parskip}{0pt}")
        lines.extend(f"\\item {item}" for item in self.content["items"])
        lines.append(f"\\end{{{style}}}")
        return self.apply_layout("\n".join(lines) + "\n")
