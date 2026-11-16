import os
import sys
from src.template.core.block_base import BaseBlock

class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        return f"\\[ {self.content.get('math', '')} \\]"
