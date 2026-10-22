"""FRI body subsection heading — flush left, same convention as `section`."""
from src.template.blocks.text.subsection import Block as SharedSubsection

from src.template.instances.fri.layout import (
    FRI_BODY_FONT_BF,
    FRI_SUBSECTION_SKIP,
    FRI_SUBSECTION_TITLE_SKIP,
)


class Block(SharedSubsection):
    def heading(self, title: str) -> str:
        return (
            rf"\vspace*{{{FRI_SUBSECTION_SKIP}}}"
            + "\n"
            + rf"\noindent{{{FRI_BODY_FONT_BF} {title}}}\par"
            + "\n"
            + rf"\vspace*{{{FRI_SUBSECTION_TITLE_SKIP}}}"
        )
