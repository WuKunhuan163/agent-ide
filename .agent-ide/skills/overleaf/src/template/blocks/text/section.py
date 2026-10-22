import os
import sys
from src.template.block_base import BaseBlock

class Block(BaseBlock):
    is_leaf = False
    
    def heading(self, title: str) -> str:
        """Heading TeX. Override in an instance to change the typography."""
        sec_cmd = "\\section*" if self.content.get("unnumbered", False) else "\\section"
        return f"{sec_cmd}{{{title}}}"

    def render(self, child_contents: str = "") -> str:
        tex = f"{self.heading(self.content['title'])}\n"
        if "label" in self.content:
            tex += f"\\label{{{self.content['label']}}}\n"
        tex += child_contents
        return self.apply_layout(tex)
