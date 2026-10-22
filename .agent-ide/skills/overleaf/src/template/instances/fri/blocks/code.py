import os
import re
import sys

from src.template.block_base import BaseBlock

from src.template.instances.fri.layout import (  # noqa: E402
    FRI_BLOCK_SKIP,
    FRI_BODY_FONT,
    FRI_CODE_FONT,
    FRI_TABLE_LABEL_DESC_GAP,
)

def _tex_escape(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<!\\)_", r"\_\\allowbreak{}", text)
    text = re.sub(r"(?<!\\)&", r"\&", text)
    text = re.sub(r"(?<!\\)%", r"\%", text)
    text = re.sub(r"(?<!\\)#", r"\#", text)
    return text


class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        code = str(self.content.get("code", "")).rstrip()
        if not code:
            return ""
        language = str(self.content.get("language", "python")).lower()
        anchor = str(self.content.get("label", "")).strip()
        listing_label = (
            self.content.get("listing_label")
            or self.content.get("listing")
            or "Listing 1"
        )
        description = self.content.get("description") or self.content.get("caption", "")

        listing_tex = _tex_escape(str(listing_label))
        desc_tex = _tex_escape(str(description)) if description else ""

        caption_lines = [
            rf"\vspace*{{{FRI_BLOCK_SKIP}}}",
            "{" + FRI_BODY_FONT,
            r"\begin{center}",
        ]
        if anchor:
            caption_lines.append(rf"\hypertarget{{{anchor}}}{{}}")
        if desc_tex:
            caption_lines.append(rf"{{\bfseries {listing_tex}.}} {desc_tex}\par")
        else:
            caption_lines.append(rf"{{\bfseries {listing_tex}.}}\par")
        caption_lines.extend([
            r"\end{center}",
            "}",
            rf"\vspace*{{{FRI_TABLE_LABEL_DESC_GAP}}}",
        ])

        opts = [
            f"language={language}",
            "breaklines=true",
            "breakatwhitespace=true",
            rf"basicstyle={{{FRI_CODE_FONT}}}",
        ]
        if anchor:
            opts.append(f"label={{{anchor}}}")
        opts_str = ",".join(opts)

        tex = "\n".join([
            *caption_lines,
            f"\\begin{{lstlisting}}[{opts_str}]",
            code,
            "\\end{lstlisting}",
            rf"\vspace*{{{FRI_BLOCK_SKIP}}}",
        ])
        return self.apply_layout(tex)
