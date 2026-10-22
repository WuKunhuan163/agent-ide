"""FRI body paragraph: the shared `text` block plus an explicit `\\par`.

No `\\noindent` here: the paragraph inherits `\\parindent` from the enclosing
`fribody` group, which is what gives the body text its first-line indent while
headings stay flush left.
"""
from src.template.blocks.text.text import Block as SharedText


class Block(SharedText):
    TEXT_SUFFIX = "\\par\n"
