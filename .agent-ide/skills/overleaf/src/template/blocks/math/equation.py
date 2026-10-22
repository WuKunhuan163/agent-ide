import os
import sys
from src.template.block_base import BaseBlock

class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        math_expr = self.content.get('math', '')
        label = self.content.get('label', '')
        tex = f"\\begin{{equation}}\n"
        tex += f"   {math_expr}\n"
        if label:
            tex += f"   \\label{{{label}}}\n"
        tex += f"\\end{{equation}}"
        return tex
