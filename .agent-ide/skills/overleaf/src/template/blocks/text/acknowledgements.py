import os
import sys
from src.template.block_base import BaseBlock

class Block(BaseBlock):
    is_leaf = False
    
    def render(self, child_contents: str = "") -> str:
        tex = "\\section*{Acknowledgements}\n"
        tex += f"{self.content.get('text', '')}\n"
        tex += child_contents
        return tex