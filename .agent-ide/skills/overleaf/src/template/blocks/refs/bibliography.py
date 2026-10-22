import os
import sys

from src.template.block_base import BaseBlock

class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        bibtex = self.content.get('bibtex', '')
        style = self.content.get('style', 'ieeetr')
        
        # Write references.bib to the output directory
        out_dir = self.content.get('_output_dir', os.getcwd())
            
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "references.bib"), "w", encoding="utf-8") as f:
            f.write(bibtex)
            
        tex = "\n"
        tex += "{\\small\n"
        tex += f"\\bibliographystyle{{{style}}}\n"
        tex += "\\bibliography{references}\n"
        tex += "}\n"
        return tex
