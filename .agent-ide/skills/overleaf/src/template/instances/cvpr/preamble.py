"""CVPR instance document assembly.

The declarative path in `render.py` only concatenates preamble + abstract +
body, which drops CVPR's title/authors and never unwraps the `cvprteaser`
environment. This module takes over assembly, mirroring the legacy
`CvprTemplate`: emit `\\title` / `\\author`, then wrap `\\maketitle` and the
teaser in a `\\twocolumn[...]` band.
"""
import re

from src.template.template_base import BaseTemplate


class Template(BaseTemplate):
    def render_preamble(self, state):
        meta = state.get("metadata", {})
        title = meta.get("title", "Untitled")

        base = list(self.spec.get("preamble_header", []))
        # Code listing colours + \lstset must precede hyperref (kept last).
        code_setup = [
            r"\definecolor{codegreen}{rgb}{0,0.6,0}",
            r"\definecolor{codegray}{rgb}{0.5,0.5,0.5}",
            r"\definecolor{codepurple}{rgb}{0.58,0,0.82}",
            r"\definecolor{backcolour}{rgb}{0.95,0.95,0.92}",
            r"\lstset{",
            r"  backgroundcolor=\color{backcolour},",
            r"  commentstyle=\color{codegreen},",
            r"  keywordstyle=\color{magenta},",
            r"  numberstyle=\tiny\color{codegray},",
            r"  stringstyle=\color{codepurple},",
            r"  basicstyle=\ttfamily\small,",
            r"  breaklines=true,",
            r"  breakatwhitespace=true,",
            r"  keepspaces=true,",
            r"  showstringspaces=false,",
            r"  frame=single,",
            r"  tabsize=4,",
            r"  columns=fullflexible,",
            r"  upquote=true",
            r"}",
        ]
        insert_at = next(
            (i for i, line in enumerate(base) if "hyperref" in line), len(base)
        )
        base[insert_at:insert_at] = code_setup

        authors = meta.get("authors", [])
        if authors:
            blocks = []
            for author in authors:
                name = author.get("name", "")
                inst = author.get("institution", "")
                email = author.get("email", "")
                website = author.get("website", "")
                entry = name + r"\\" + inst
                if email:
                    entry += r"\\{\small " + email + "}"
                if website:
                    entry += r"\\{\small \url{" + website + "}}"
                blocks.append(entry)
            author_tex = "\\author{" + " \\and ".join(blocks) + "}"
        else:
            author_tex = r"\author{Anonymous Authors}"

        return "\n".join([*base, "", f"\\title{{{title}}}", "", author_tex])

    def build_document(self, state):
        self.validate_state(state)

        body = state.get("rendered_content", "")
        teaser_match = re.search(
            r"\\begin\{cvprteaser\}(.*?)\\end\{cvprteaser\}", body, re.DOTALL
        )

        lines = [self.render_preamble(state), r"\begin{document}"]
        if teaser_match:
            teaser_tex = teaser_match.group(1)
            body = body.replace(teaser_match.group(0), "")
            lines.append(r"\twocolumn[{")
            lines.append(r"\renewcommand\twocolumn[1][]{#1}")
            lines.append(r"\maketitle")
            lines.append(teaser_tex)
            lines.append(r"}]")
        else:
            lines.append(r"\maketitle")

        abstract = state.get("metadata", {}).get("abstract")
        if abstract:
            lines.append(r"\begin{abstract}")
            lines.append(abstract)
            lines.append(r"\end{abstract}")

        lines.append(body)
        lines.append(r"\end{document}")
        return "\n".join(lines)
