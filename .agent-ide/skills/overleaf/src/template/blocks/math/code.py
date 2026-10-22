import os
import sys
from src.template.block_base import BaseBlock

class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        code = self.content.get('code', '')
        language = self.content.get('language', 'python')
        caption = self.content.get('caption', '').replace('_', '\\_')
        label = self.content.get('label', '')
        
        opts = [f"language={language}", "breaklines=true", "breakatwhitespace=true", "basicstyle=\\ttfamily\\small"]
        if caption:
            opts.append(f"caption={{{caption}}}")
        if label:
            opts.append(f"label={{{label}}}")
            
        opts_str = ",".join(opts)
        
        # Protect code block with lstlisting which supports line breaks
        tex = f"\\begin{{lstlisting}}[{opts_str}]\n"
        tex += code
        if not tex.endswith('\n'):
            tex += "\n"
        tex += "\\end{lstlisting}\n"
        
        return self.apply_layout(tex)
