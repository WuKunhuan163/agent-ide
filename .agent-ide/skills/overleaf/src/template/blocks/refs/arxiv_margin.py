import os
import sys
from src.template.block_base import BaseBlock

class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        text = self.content.get('text', '')
        tex = r"\AddToShipoutPicture*{%" + "\n"
        tex += r"  \AtPageLowerLeft{%" + "\n"
        tex += r"    \put(30,150){\rotatebox{90}{\LARGE\color{gray} " + text + r"}}%" + "\n"
        tex += r"  }%" + "\n"
        tex += r"}%" + "\n"
        return tex
