"""FRI body section heading: the shared `section` with journal typography.

The heading is always flush left ("标题不顶格"): it carries an explicit
`\\noindent` so the paragraph indent set by the enclosing `fribody` group only
affects the `text` blocks underneath it.
"""
from src.template.blocks.text.section import Block as SharedSection

from src.template.instances.fri.layout import FRI_BODY_FONT_BF, FRI_SECTION_SKIP


class Block(SharedSection):
    def heading(self, title: str) -> str:
        return (
            rf"\vspace{{{FRI_SECTION_SKIP} plus 2pt minus 4pt}}"
            + "\n"
            + rf"\noindent{{{FRI_BODY_FONT_BF} {title}}}\par"
        )
