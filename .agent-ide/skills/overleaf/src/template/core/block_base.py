"""Base class for every layout block.

A block is a pure transformer: content dict -> LaTeX string. It never touches
the disk layout of a project; anything it needs about paths arrives through
`content` keys injected by the renderer (`_project_dir`, `_output_dir`).
"""
from __future__ import annotations

from src.store import errors
from src.store.errors import DataError


class BaseBlock:
    """Base class for all layout blocks."""

    # Structure (nesting, which children a container accepts) is owned by the
    # template manifest, which is per-instance and enforced by `src.store.tree`
    # on every write. `is_leaf` is the one structural fact restated here, as a
    # cheap backstop for trees that did not come through the store.
    is_leaf: bool = True

    def __init__(self, block_id: str, parent_id: str, children_ids: list, content: dict) -> None:
        self.block_id = block_id
        self.parent_id = parent_id
        self.children_ids = children_ids or []
        self.content = content
        self.validate()

    def validate(self) -> None:
        """Override to check required content fields."""
        if self.is_leaf and len(self.children_ids) > 0:
            raise DataError(
                errors.LEAF_CANNOT_HAVE_CHILDREN,
                None,
                f"block type '{self.__class__.__name__}' is a leaf and cannot have children",
            )

    @staticmethod
    def should_display(data) -> bool:
        """Return False when a block/row/section is explicitly hidden."""
        if not isinstance(data, dict):
            return True
        display = data.get("display")
        if display is None:
            content = data.get("content")
            if isinstance(content, dict):
                display = content.get("display")
        if display is None:
            return True
        if isinstance(display, bool):
            return display
        if isinstance(display, (int, float)):
            return bool(display)
        if isinstance(display, str):
            return display.strip().lower() not in {"false", "no", "none", "hidden", "0", "off"}
        return True

    def apply_layout(self, tex: str) -> str:
        """Apply generic layout options (margins, alignment)."""
        mt = self.content.get("margin_top")
        mb = self.content.get("margin_bottom")
        align = self.content.get("align")

        res = tex
        if mt:
            res = f"\\vspace*{{{mt}}}\n" + res
        if mb:
            if not res.endswith("\n"):
                res += "\n"
            res += f"\\vspace*{{{mb}}}\n"

        if align == "center":
            res = "\\begin{center}\n" + res + "\\end{center}\n"
        elif align == "right":
            res = "\\begin{flushright}\n" + res + "\\end{flushright}\n"

        return res

    def render(self, child_contents: str = "") -> str:
        """Convert content to LaTeX. Containers receive rendered children."""
        raise NotImplementedError("Block must implement render()")
