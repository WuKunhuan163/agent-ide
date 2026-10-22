import os
import sys
from src.template.block_base import BaseBlock

class Block(BaseBlock):
    # Typography hook: an instance that needs a trailing macro (an explicit
    # `\par`, say) sets this instead of copying the whole plugin.
    TEXT_SUFFIX: str = ""

    def render(self, child_contents: str = "") -> str:
        tex = f"{self.content['text']}\n{self.TEXT_SUFFIX}"
        return self.apply_layout(tex)
