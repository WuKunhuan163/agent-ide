"""In-memory, I/O-free data model for a project and its block tree."""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = 1
DEFAULT_ORDER_STEP = 10


@dataclass
class Block:
    id: str  # directory slug, stable identity
    type: str
    order: int
    display: bool
    content: dict
    children: list["Block"] = field(default_factory=list)
    rel_path: str = ""

    def find(self, rel_path: str) -> "Block | None":
        """Locate a descendant by its block relative path (`a/b`)."""
        target = rel_path.strip("/")
        if not target:
            return None
        head, _, tail = target.partition("/")
        for child in self.children:
            if child.id == head:
                return child if not tail else child.find(tail)
        return None

    def walk(self) -> list["Block"]:
        """Depth-first list including self."""
        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out


@dataclass
class Project:
    id: str
    agent_id: str
    root_dir: str
    template_id: str
    template_version: int
    metadata: dict
    root: Block  # synthetic container; its children are top-level blocks

    def find(self, rel_path: str) -> Block | None:
        return self.root.find(rel_path)

    def blocks(self) -> list[Block]:
        """All real blocks (excludes the synthetic root)."""
        return [b for b in self.root.walk() if b is not self.root]

    def visible_blocks(self) -> list[Block]:
        """Blocks that actually reach the document, in render order.

        `display: false` means "as if this block did not exist", so a hidden node
        and its whole subtree are skipped — exactly the pruning `render.py` does.
        Anything that reasons about the rendered document (content validation, the
        citation/label index) must walk this view rather than `blocks()`.

        Structural checks (order uniqueness, template binding) deliberately still
        use `blocks()`: `display` is a rendering concern and must not be able to
        mask a broken tree.
        """
        out: list[Block] = []
        stack: list[Block] = list(reversed(self.root.children))
        while stack:
            block = stack.pop()
            if not block.display:
                continue  # prunes the subtree, like render_node returning ""
            out.append(block)
            stack.extend(reversed(block.children))
        return out


@dataclass
class TreeNode:
    """Read-only projection returned by `list_tree`; never truncates content."""

    id: str
    type: str
    order: int
    display: bool
    content: dict
    children: list["TreeNode"] = field(default_factory=list)
