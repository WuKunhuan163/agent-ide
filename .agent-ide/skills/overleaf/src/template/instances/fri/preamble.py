import json
import os
import re
import sys
from src.store import errors
from src.store.errors import DataError
from src.template.template_base import BaseTemplate

from src.template.block_base import BaseBlock

from src.template.instances.fri.layout import (
    FRI_BLOCK_SKIP,
    FRI_BODY_BASELINESkip,
    FRI_BODY_FONT,
    FRI_BODY_FONT_BF,
    FRI_BODY_FONT_BF_IT,
    FRI_BODY_FONT_PT,
    FRI_COLUMN_SEP,
    FRI_FIGURE_SCALE_DEFAULT,
    FRI_FOOTER_GAP,
    FRI_FOOT_BOTTOM,
    FRI_HEAD_HEIGHT,
    FRI_HEAD_SEP,
    FRI_PAGE_NUMBER_SIZE,
    FRI_PAGE_TOP,
    FRI_PAR_INDENT,
    FRI_REF_FONT,
    FRI_RUNNING_FONT,
    FRI_SECTION_SKIP,
    FRI_SUBSECTION_SKIP,
    FRI_SUBSECTION_TITLE_SKIP,
    FRI_SUBSUBSECTION_SKIP,
    FRI_SUBSUBSECTION_TITLE_SKIP,
    FRI_TABLE_CAPTION_TABLE_GAP,
    FRI_TABLE_FLOAT_MARGIN,
    FRI_TABLE_FONT_SCALE,
    FRI_TABLE_LABEL_DESC_GAP,
    FRI_TABLE_ROW_STRETCH,
    FRI_TABLE_RULE_GAP,
    FRI_TABLE_TIGHT_COLSEP,
    FRI_TABLE_WIDE_COLS,
    FRI_TABLE_WIDTH_SCALE,
    FRI_TOP_MARGIN_ADJUST,
)


class Template(BaseTemplate):
    def _article_test_preamble(self, meta=None):
        meta = meta or {}
        running_left = self._tex_escape(self._running_header_left(meta.get("authors", [])))
        running_right = self._tex_escape(self._running_header_right(meta))
        return [
            r"\documentclass[10pt]{article}",
            rf"\usepackage[paperwidth=192mm,paperheight=262mm,",
            rf"  top={FRI_PAGE_TOP},bottom=13.8mm,left=13.8mm,right=13.8mm]{{geometry}}",
            rf"\setlength{{\headheight}}{{{FRI_HEAD_HEIGHT}}}",
            rf"\setlength{{\headsep}}{{{FRI_HEAD_SEP}}}",
            rf"\addtolength{{\topmargin}}{{{FRI_TOP_MARGIN_ADJUST}}}",
            r"\usepackage{fontspec}",
            r"\setmainfont{CharisSIL}[",
            r"  Path=assets/fonts/,",
            r"  Extension=.ttf,",
            r"  UprightFont=*-Regular,",
            r"  BoldFont=*-Bold,",
            r"  ItalicFont=*-Italic,",
            r"  BoldItalicFont=*-BoldItalic",
            r"]",
            *self._cjk_font_preamble(),
            *self._unicode_symbol_preamble(),
            r"\usepackage{graphicx}",
            r"\usepackage{listings}",
            r"\lstset{basicstyle=\ttfamily\small,breaklines=true,breakatwhitespace=true,columns=fullflexible}",
            r"\usepackage{array}",
            r"\usepackage{longtable}",
            r"\usepackage{needspace}",
            r"\usepackage{xcolor}",
            r"\usepackage{setspace}",
            r"\usepackage{paracol}",
            r"\usepackage{indentfirst}",
            r"\usepackage{fancyhdr}",
            r"\usepackage{eso-pic}",
            r"\usepackage{capt-of}",
            r"\definecolor{elsevierteal}{HTML}{0976A0}",
            r"\definecolor{elsevierlinkblue}{HTML}{2196D1}",
            r"\definecolor{elseviergray}{HTML}{E8E8E8}",
            r"\usepackage[breaklinks=true,colorlinks=true,urlcolor=elsevierlinkblue,linkcolor=elsevierlinkblue,citecolor=elsevierlinkblue,bookmarks=false]{hyperref}",
            r"\renewcommand{\UrlFont}{\normalfont\fontsize{8}{9}\selectfont}",
            r"\newenvironment{frijournalheader}{}{}",
            r"\newenvironment{frilowerheader}{}{}",
            r"\newenvironment{friinfoabstract}{}{}",
            r"\newenvironment{friauthornotes}{}{}",
            r"\newenvironment{fripublicationmeta}{}{}",
            r"\newenvironment{friintroduction}{}{}",
            r"\newenvironment{fribody}{}{}",
            r"\newenvironment{fritable}{%",
            rf"  \par\vspace{{{FRI_TABLE_FLOAT_MARGIN} plus 0pt minus 2pt}}%",
            r"  \noindent%",
            r"}{%",
            rf"  \par\vspace{{{FRI_TABLE_FLOAT_MARGIN} plus 0pt minus 2pt}}%",
            r"}",
            r"\fancypagestyle{frirunning}{%",
            r"  \fancyhf{}%",
            rf"  \fancyhead[L]{{\normalfont\itshape{FRI_RUNNING_FONT} {running_left}}}%",
            rf"  \fancyhead[R]{{\normalfont\itshape{FRI_RUNNING_FONT} {running_right}}}%",
            r"  \renewcommand{\headrulewidth}{0pt}%",
            r"}",
            rf"\AddToShipoutPictureFG{{\ifnum\value{{page}}>1\relax",
            rf"  \AtPageLowerLeft{{\put(\LenToUnit{{0.5\paperwidth}},\LenToUnit{{{FRI_FOOT_BOTTOM}}}){{",
            rf"    \makebox(0,0){{{FRI_PAGE_NUMBER_SIZE}\selectfont\thepage}}}}}}",
            r"\fi}",
            # The front-matter footer lockup (author notes + publication meta) is
            # pinned to the foot of page 1 as an absolute overlay (like a flexbox
            # child) instead of being flowed, so the body keeps filling the space
            # above it. `paracol` sizes its columns from LaTeX's \@colht/\@colroom
            # (not from \textheight), so the lockup's height is reserved by
            # shrinking those two registers while page 1 is being built and
            # restoring them the moment page 1 is shipped out.
            r"\newsavebox{\friFooterBox}",
            r"\newlength{\friFooterNormColHt}",
            r"\newlength{\friFooterNormColRoom}",
            r"\makeatletter",
            r"\AddToShipoutPictureFG{\ifnum\value{page}=1\relax",
            r"  \AtTextLowerLeft{\put(0,0){\makebox(0,0)[bl]{\usebox{\friFooterBox}}}}%",
            r"  \global\@colht\friFooterNormColHt",
            r"  \global\@colroom\friFooterNormColRoom",
            r"\fi}",
            r"\makeatother",
            r"\pagestyle{frirunning}",
            r"\AtBeginDocument{\thispagestyle{empty}}",
            r"\widowpenalty=10000",
            r"\clubpenalty=10000",
            r"\displaywidowpenalty=10000",
            r"",
            r"\begin{document}",
        ]

    def _para_skip(self) -> str:
        return rf"\vspace{{{FRI_BLOCK_SKIP} plus 1pt minus 2pt}}"

    def _cjk_font_preamble(self) -> list[str]:
        """Render CJK body text when metadata contains Chinese paragraphs."""
        return [
            r"\usepackage{xeCJK}",
            r"\IfFontExistsTF{Songti SC}{",
            r"  \setCJKmainfont{Songti SC}[BoldFont=Heiti SC]",
            r"}{",
            r"  \IfFontExistsTF{PingFang SC}{",
            r"    \setCJKmainfont{PingFang SC}[BoldFont=PingFang SC]",
            r"  }{",
            r"    \setCJKmainfont{STSong}",
            r"  }",
            r"}",
            r"\xeCJKsetup{CJKspace=true}",
        ]

    def _unicode_symbol_preamble(self) -> list[str]:
        """Map common Unicode symbols missing from Charis SIL to safe LaTeX glyphs."""
        return [
            r"\usepackage{amsmath}",
            r"\usepackage{newunicodechar}",
            r"\newunicodechar{≥}{\ensuremath{\geq}}",
            r"\newunicodechar{≤}{\ensuremath{\leq}}",
            r"\newunicodechar{≠}{\ensuremath{\neq}}",
            r"\newunicodechar{±}{\ensuremath{\pm}}",
            r"\newunicodechar{×}{\ensuremath{\times}}",
            r"\newunicodechar{÷}{\ensuremath{\div}}",
            r"\newunicodechar{≈}{\ensuremath{\approx}}",
            r"\newunicodechar{＞}{\textgreater}",
            r"\newunicodechar{＜}{\textless}",
            r"\newunicodechar{–}{--}",
            r"\newunicodechar{—}{---}",
            r"\newunicodechar{…}{\ldots}",
            r"\IfFontExistsTF{STIX Two Text}{",
            r"  \newfontfamily\friSymbolFallback{STIX Two Text}[Scale=MatchLowercase]",
            r"}{",
            r"  \IfFontExistsTF{Arial Unicode MS}{",
            r"    \newfontfamily\friSymbolFallback{Arial Unicode MS}[Scale=MatchLowercase]",
            r"  }{",
            r"    \newfontfamily\friSymbolFallback{Helvetica}[Scale=MatchLowercase]",
            r"  }",
            r"}",
        ]

    def _section_skip(self) -> str:
        return rf"\vspace{{{FRI_SECTION_SKIP} plus 2pt minus 4pt}}"

    def _body_text_block_open(self, indent: bool = False) -> list[str]:
        """Open the font/paragraph group for a text region.

        `indent=True` (article body): paragraphs take a first-line indent of
        `FRI_PAR_INDENT` ("文段顶格") with no inter-paragraph skip, while every
        heading keeps its own explicit `\\noindent` ("标题不顶格"). `indent=False`
        keeps the legacy flush-left + block-skip behaviour used by the back matter.
        """
        par_skip = "0pt" if indent else rf"{FRI_BLOCK_SKIP} plus 1pt minus 2pt"
        lines = [
            "{" + FRI_BODY_FONT,
            rf"\setlength{{\parindent}}{{{FRI_PAR_INDENT if indent else '0pt'}}}",
            rf"\setlength{{\parskip}}{{{par_skip}}}",
            r"\emergencystretch=1em",
        ]
        if not indent:
            lines.append(r"\everypar{\noindent\ignorespaces}")
        return lines

    def _render_back_matter_title(self, title: str) -> list[str]:
        return [
            rf"\vspace*{{{FRI_SECTION_SKIP}}}",
            rf"\noindent{{\bfseries {self._tex_escape(title)}}}\par",
            self._para_skip(),
        ]

    def _render_bibliography_title(self, title: str) -> list[str]:
        """References heading: no gap before first \\bibitem (matches Elsevier ref PDF)."""
        return [
            rf"\vspace*{{{FRI_SECTION_SKIP}}}",
            rf"\noindent{{\bfseries {self._tex_escape(title)}}}\par",
        ]

    def _bibliography_compact_list_preamble(self) -> list[str]:
        # Hanging indent ("首行 [1] 顶格、续行缩进"): the label is flush with the
        # column's left edge and wrapped lines align to the reference text. The
        # `thebibliography` argument sets `\labelwidth` to the widest label, so
        # these lines only re-assert the classic article.cls geometry (they are
        # numerically equal to what `\list` already established, keeping
        # `\@totalleftmargin` consistent) while tightening vertical spacing.
        return [
            r"\setlength{\itemindent}{0pt}",
            r"\setlength{\leftmargin}{\labelwidth}",
            r"\addtolength{\leftmargin}{\labelsep}",
            r"\setlength{\itemsep}{0pt plus 0pt}",
            r"\setlength{\parsep}{0pt plus 0pt}",
            r"\setlength{\topsep}{0pt plus 0pt}",
            r"\setlength{\partopsep}{0pt plus 0pt}",
        ]

    def _suppress_bibliography_section_heading(self) -> list[str]:
        """article.cls thebibliography emits \\section*{\\refname} at ~14pt; suppress it."""
        return [
            r"\makeatletter",
            r"\let\fri@saved@section\section",
            r"\def\section{\@ifstar{\@gobble}{\@gobble}}",
            r"\makeatother",
        ]

    def _restore_section_heading(self) -> list[str]:
        return [
            r"\makeatletter\let\section\fri@saved@section\makeatother",
        ]

    def _format_affiliation_line(self, affil_id, affil_data):
        parts = []
        org = affil_data.get("organization", "")
        if org:
            parts.append(org)
        address = affil_data.get("addressline", "")
        if address:
            parts.append(address)
        city = affil_data.get("city", "")
        postcode = affil_data.get("postcode", "")
        city_part = ", ".join(p for p in [city, postcode] if p)
        if city_part:
            parts.append(city_part)
        country = affil_data.get("country", "")
        if country:
            parts.append(country)
        return ", ".join(parts)

    def _corresponding_suffix(self, mark):
        if mark == 1:
            return "*"
        if mark == 2:
            return "**"
        if mark:
            return "*" * int(mark)
        return ""

    def _format_author_superscript(self, affil_ids, cor_mark) -> str:
        parts = []
        items = [str(x) for x in affil_ids]
        if cor_mark:
            items.append(self._corresponding_suffix(cor_mark))
        for i, item in enumerate(items):
            if i > 0:
                parts.append(r"\textcolor{black}{,}")
            if item in ("*", "**"):
                parts.append(
                    rf"\hyperlink{{cor.{cor_mark}}}{{\textcolor{{elsevierlinkblue}}{{{item}}}}}"
                )
            else:
                parts.append(
                    rf"\hyperlink{{aff.{item}}}{{\textcolor{{elsevierlinkblue}}{{{item}}}}}"
                )
        return "".join(parts)

    def _render_lower_header(self, meta):
        article_type = meta.get("article_type", "Review article")
        title = meta.get("title", "Untitled")
        authors = meta.get("authors", [])
        affiliations = meta.get("affiliations", {})

        author_parts = []
        for i, author in enumerate(authors):
            name = author.get("name", "")
            affil_ids = author.get("affiliation_ids", [])
            sup_tex = self._format_author_superscript(affil_ids, author.get("corresponding_mark"))
            part = (
                rf"{{\fontsize{{10.5}}{{12}}\selectfont {name}}}"
                rf"\textsuperscript{{\fontsize{{7.5}}{{8}}\selectfont {sup_tex}}}"
            )
            author_parts.append(part)
        authors_tex = ", ".join(author_parts)

        affil_lines = []
        for affil_id in sorted(affiliations.keys()):
            line = self._format_affiliation_line(affil_id, affiliations[affil_id])
            affil_lines.append(
                rf"\hypertarget{{aff.{affil_id}}}{{}}\textsuperscript{{\fontsize{{4.6}}{{5}}\selectfont {affil_id}}}"
                rf"{{\fontsize{{6.4}}{{8}}\selectfont\itshape {line}}}"
            )
        affils_tex = " \\\\\n".join(affil_lines)

        return "\n".join([
            r"\begin{frilowerheader}",
            r"\noindent\begin{minipage}{0.8\linewidth}",
            r"\setlength{\parindent}{0pt}",
            r"\vspace*{12pt}",
            rf"\noindent{{\fontsize{{9.5}}{{11}}\selectfont {article_type}}}\par",
            r"\vspace{10.37pt}",
            r"{\linespread{1.26}\selectfont",
            rf"\noindent{{\fontsize{{13.2}}{{16}}\selectfont {title}}}\par",
            r"}",
            r"\vspace{11.52pt}",
            r"{\linespread{1.26}\selectfont",
            r"\noindent" + authors_tex + r"\par",
            r"}",
            r"\vspace{6pt}",
            r"{\linespread{0.603}\selectfont\raggedright",
            affils_tex,
            r"\par}",
            r"\end{minipage}",
            r"\par\vspace{4pt}",
            r"\noindent\rule{\textwidth}{0.25pt}",
            r"\par\vspace*{10pt}",
            r"\end{frilowerheader}",
        ])

    def _tex_escape(self, text):
        text = text.replace("\u00ad", "")
        # Allow line breaks at snake_case underscores in prose (Preview/LaTeX otherwise
        # treats \"word_word\" as an unbreakable box and it can overfull \hbox).
        text = re.sub(r"(?<!\\)_", r"\_\\allowbreak{}", text)
        text = re.sub(r"(?<!\\)&", r"\&", text)
        text = re.sub(r"(?<!\\)%", r"\%", text)
        text = re.sub(r"(?<!\\)#", r"\#", text)
        return text

    _BIB_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

    def _href_url_target(self, url: str) -> str:
        """Escape URL for \\href target (do not escape underscores)."""
        for char, escaped in (("%", r"\%"), ("#", r"\#")):
            url = url.replace(char, escaped)
        return url

    def _clean_bib_url(self, raw: str) -> tuple[str, str]:
        """Return (url_without_spaces, trailing_punctuation)."""
        url_body = raw
        trailing = ""
        while url_body and url_body[-1] in ".,;)]>":
            trailing = url_body[-1] + trailing
            url_body = url_body[:-1]
        return re.sub(r"\s+", "", url_body), trailing

    def _format_bibliography_entry(self, text: str) -> str:
        """Black body text; only URL substrings become blue \\href links."""
        matches = list(self._BIB_URL_RE.finditer(text))
        if not matches:
            return self._tex_escape(text)
        parts: list[str] = []
        pos = 0
        for match in matches:
            parts.append(self._tex_escape(text[pos : match.start()]))
            clean_url, trailing = self._clean_bib_url(match.group(0))
            if clean_url:
                target = self._href_url_target(clean_url)
                display = self._tex_escape(clean_url)
                parts.append(
                    rf"\href{{{target}}}{{\textcolor{{elsevierlinkblue}}{{{display}}}}}"
                )
            else:
                parts.append(self._tex_escape(match.group(0)))
            parts.append(self._tex_escape(trailing))
            pos = match.end()
        parts.append(self._tex_escape(text[pos:]))
        return "".join(parts)

    def _cite_key(self, num: int) -> str:
        return f"ref{num:03d}"

    def _format_cite_label_parts(self, nums: list[int]) -> str:
        """Render [2,3] with black punctuation and blue linked digits."""
        if len(nums) == 1:
            n = nums[0]
            key = self._cite_key(n)
            return (
                r"\textcolor{black}{[}"
                + rf"\hyperlink{{cite.{key}}}{{\textcolor{{elsevierlinkblue}}{{{n}}}}}"
                + r"\textcolor{black}{]}"
            )
        if len(nums) > 2 and nums == list(range(nums[0], nums[-1] + 1)):
            start, end = nums[0], nums[-1]
            k0, k1 = self._cite_key(start), self._cite_key(end)
            return (
                r"\textcolor{black}{[}"
                + rf"\hyperlink{{cite.{k0}}}{{\textcolor{{elsevierlinkblue}}{{{start}}}}}"
                + r"\textcolor{black}{--}"
                + rf"\hyperlink{{cite.{k1}}}{{\textcolor{{elsevierlinkblue}}{{{end}}}}}"
                + r"\textcolor{black}{]}"
            )
        inner = r"\textcolor{black}{,}".join(
            rf"\hyperlink{{cite.{self._cite_key(n)}}}{{\textcolor{{elsevierlinkblue}}{{{n}}}}}"
            for n in nums
        )
        return r"\textcolor{black}{[}" + inner + r"\textcolor{black}{]}"

    def parse_bibliography_entries(self, project_dir: str) -> dict[str, str]:
        return self._parse_references_bib(project_dir)

    def iter_citable_texts(self, meta) -> list[str]:
        chunks: list[str] = []
        intro = meta.get("introduction", "")
        if isinstance(intro, list):
            chunks.extend(str(p) for p in intro if p)
        elif intro:
            chunks.append(str(intro))
        for section in meta.get("body_sections", []):
            for item in section.get("content") or []:
                if item.get("type") == "paragraph" and item.get("text"):
                    chunks.append(str(item["text"]))
            for sub in section.get("subsections") or []:
                for item in sub.get("content") or []:
                    if item.get("type") == "paragraph" and item.get("text"):
                        chunks.append(str(item["text"]))
        for item in meta.get("back_matter") or []:
            for para in item.get("paragraphs") or []:
                if para:
                    chunks.append(str(para))
            for block in item.get("content") or []:
                if block.get("type") == "paragraph" and block.get("text"):
                    chunks.append(str(block["text"]))
        return chunks

    def _normalize_citation_spacing(self, text: str) -> str:
        """Ensure a space before inline numeric citations: 'word[12]' -> 'word [12]'."""
        text = re.sub(r"(\S)\[(\d+)", r"\1 [\2", text)
        return text

    def _tex_escape_preserving_link_targets(self, text: str) -> str:
        """Escape prose while leaving \\hyperlink / \\hypertarget anchor IDs intact."""
        if not text:
            return text
        parts: list[str] = []
        i = 0
        while i < len(text):
            matched = False
            for cmd in (r"\hyperlink{", r"\hypertarget{"):
                if text.startswith(cmd, i):
                    end = i + len(cmd)
                    depth = 1
                    anchor_start = end
                    while end < len(text) and depth:
                        ch = text[end]
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        end += 1
                    anchor = text[anchor_start : end - 1]
                    parts.append(f"{cmd}{anchor}" + "}")
                    i = end
                    matched = True
                    break
            if matched:
                continue
            next_i = len(text)
            for cmd in (r"\hyperlink{", r"\hypertarget{"):
                pos = text.find(cmd, i)
                if pos != -1:
                    next_i = min(next_i, pos)
            parts.append(self._tex_escape(text[i:next_i]))
            i = next_i
        return "".join(parts)

    def _linkify_citations(self, text: str) -> str:
        text = self._normalize_citation_spacing(text)
        escaped = self._tex_escape_preserving_link_targets(text)
        skip_criterion_list = "following criteria" in text.lower()

        def cite_nums(nums: list[int]) -> str:
            return self._format_cite_label_parts(nums)

        def replace_range(m):
            start, end = int(m.group(1)), int(m.group(2))
            return cite_nums(list(range(start, end + 1)))

        def replace_multi(m):
            nums = [int(x.strip()) for x in re.split(r"[,;]\s*", m.group(1)) if x.strip()]
            return cite_nums(nums)

        def replace_single(m):
            num = int(m.group(1))
            if skip_criterion_list and num <= 4:
                end = m.end()
                if end < len(escaped) and escaped[end] == ":":
                    return m.group(0)
                if end < len(escaped) and escaped[end] == ",":
                    rest = escaped[end + 1 : end + 24].lstrip()
                    if rest and rest[0].islower():
                        return m.group(0)
            return cite_nums([num])

        out = re.sub(r"\[(\d+)\s*[–\-]\s*(\d+)\]", replace_range, escaped)
        out = re.sub(r"\[(\d+(?:\s*,\s*\d+)+)\]", replace_multi, out)
        out = re.sub(r"\[(\d+)\]", replace_single, out)
        return out

    def _float_label_for_key(self, key: str, meta=None) -> str:
        if meta:
            entry = (meta.get("tables") or {}).get(key) or (meta.get("figures") or {}).get(key) or {}
            if entry.get("label"):
                return str(entry["label"])
        if key.startswith("table"):
            suffix = key[5:]
            if suffix.isdigit():
                return f"Table {suffix}"
        if key.startswith("fig"):
            suffix = key[3:]
            if suffix.isdigit():
                return f"Fig. {suffix}"
        return key

    def _subsection_anchor_id(self, title: str) -> str:
        m = re.match(r"^(\d+\.\d+)\.", str(title).strip())
        return f"sec.{m.group(1)}" if m else ""

    def _section_anchor_id(self, title: str) -> str:
        m = re.match(r"^(\d+)\.\s+", str(title).strip())
        return f"sec.{m.group(1)}" if m else ""

    def _expand_ref_placeholders(self, text: str, meta, project_dir: str = "") -> str:
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key.startswith("sec."):
                label = f"section {key[4:]}"
                return (
                    rf"\hyperlink{{{key}}}{{\textcolor{{elsevierlinkblue}}{{{self._tex_escape(label)}}}}}"
                )
            kind = "table" if key.startswith("table") else "figure"
            if not self._float_has_content(kind, key, meta, project_dir):
                return m.group(0)
            label = self._float_label_for_key(key, meta)
            return (
                rf"\hyperlink{{{key}}}{{\textcolor{{elsevierlinkblue}}{{{self._tex_escape(label)}}}}}"
            )

        return re.sub(r"\{\{ref:([^}]+)\}\}", repl, text)

    def _linkify_inline_float_refs(
        self, text: str, meta, project_dir: str = ""
    ) -> str:
        """Expand {{ref:...}} placeholders and linkify numeric citations."""
        text = str(text).strip()
        if not text:
            return ""
        if "{{ref:" in text:
            text = self._expand_ref_placeholders(text, meta, project_dir)
        return self._linkify_citations(text)

    def _render_code_item(self, item: dict, listing_num: int = 1) -> list[str]:
        code = item.get("code", "")
        if not str(code).strip():
            return []
        language = str(item.get("language", "python")).lower()
        anchor = str(item.get("label", "")).strip()
        listing_label = (
            item.get("listing_label")
            or item.get("listing")
            or f"Listing {listing_num}"
        )
        description = item.get("description") or item.get("caption", "")
        listing_tex = self._tex_escape(str(listing_label))
        desc_tex = self._tex_escape(str(description)) if description else ""
        code_font = r"\fontsize{7.97}{10}\selectfont\ttfamily"

        caption_lines = [
            rf"\vspace*{{{FRI_BLOCK_SKIP}}}",
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
            rf"\vspace*{{{FRI_TABLE_LABEL_DESC_GAP}}}",
        ])

        opts = [
            f"language={language}",
            "breaklines=true",
            "breakatwhitespace=true",
            rf"basicstyle={{{code_font}}}",
        ]
        if anchor:
            opts.append(f"label={{{anchor}}}")
        opts_str = ",".join(opts)
        return [
            *caption_lines,
            f"\\begin{{lstlisting}}[{opts_str}]",
            str(code).rstrip(),
            "\\end{lstlisting}",
            self._para_skip(),
        ]

    def _render_content_sequence(
        self,
        content: list,
        meta,
        project_dir: str,
        inserted: set,
    ) -> list:
        lines: list[str] = []
        listing_num = 0
        for item in content:
            if not isinstance(item, dict):
                continue
            if not BaseBlock.should_display(item):
                continue
            kind = item.get("type")
            if kind == "paragraph":
                text = item.get("text", "")
                if not str(text).strip():
                    continue
                fig_caption = re.match(r"^(Fig\.\s*\d+\.\s+.+)$", str(text).strip())
                if fig_caption:
                    m = re.match(r"^Fig\.\s*(\d+)\.", str(text).strip())
                    key = self._figure_key(int(m.group(1))) if m else ""
                    lines.append(self._para_skip())
                    if key and self._figure_entry(meta, key).get("asset"):
                        inserted.add(key)
                        lines.extend(self._render_float_block(meta, "figure", key, project_dir))
                    else:
                        lines.append(
                            rf"\noindent{{\bfseries {self._linkify_inline_float_refs(text, meta, project_dir)}}}\par"
                        )
                    continue
                linked = self._linkify_inline_float_refs(text, meta, project_dir)
                lines.append(rf"{linked}\par")
            elif kind == "list":
                items = [str(i).strip() for i in item.get("items", []) if str(i).strip()]
                if not items:
                    continue
                for li in items:
                    linked = self._linkify_inline_float_refs(li, meta, project_dir)
                    lines.append(
                        r"\noindent\hangindent=1.35em\hangafter=1"
                        rf"\textbullet\hspace{{0.45em}}{linked}\par"
                    )
            elif kind == "table":
                key = str(item.get("ref") or item.get("key", "")).strip()
                if key and key not in inserted:
                    inserted.add(key)
                    lines.extend(self._render_table_block(meta, key, project_dir))
            elif kind == "figure":
                key = str(item.get("ref") or item.get("key", "")).strip()
                if key and key not in inserted:
                    inserted.add(key)
                    lines.extend(self._render_float_block(meta, "figure", key, project_dir))
            elif kind == "code":
                listing_num += 1
                lines.extend(self._render_code_item(item, listing_num))
        return lines

    def _require_content_not_paragraphs(self, title: str, paragraphs, content) -> None:
        if paragraphs and not content:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                f"FRI section '{title}' uses deprecated paragraphs[] for body/float layout. "
                "Migrate to declarative content[] with {ref:...} placeholders.",
            )

    def _parse_references_bib(self, project_dir: str) -> dict[str, str]:
        if not project_dir:
            return {}
        bib_path = os.path.join(project_dir, "references.bib")
        if not os.path.exists(bib_path):
            return {}
        text = open(bib_path, encoding="utf-8").read()
        entries = {}
        for match in re.finditer(
            r"@misc\{(ref\d+)\s*,\s*note\s*=\s*\{(.*?)\}\s*\}",
            text,
            flags=re.DOTALL,
        ):
            entries[match.group(1)] = match.group(2).strip()
        return entries

    def _render_bibliography(self, state):
        meta = state.get("metadata", {})
        if not self._meta_visibility(meta, "bibliography"):
            return ""
        if not meta.get("include_bibliography", True):
            return ""
        entries = self._parse_references_bib(state.get("project_dir", ""))
        if not entries:
            return ""
        items = []
        for key in sorted(entries, key=lambda k: int(k[3:])):
            body = self._format_bibliography_entry(entries[key])
            items.append(rf"\hypertarget{{cite.{key}}}{{}}\bibitem{{{key}}}\label{{cite.{key}}} {body}")
        return "\n".join([
            *self._body_text_block_open(),
            *self._render_bibliography_title("References"),
            r"\phantomsection",
            FRI_REF_FONT,
            *self._suppress_bibliography_section_heading(),
            rf"\begin{{thebibliography}}{{{max(int(k[3:]) for k in entries)}}}",
            *self._bibliography_compact_list_preamble(),
            *items,
            r"\end{thebibliography}",
            *self._restore_section_heading(),
            r"}",
        ])

    def _author_short_name(self, name):
        parts = name.split()
        if not parts:
            return name
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2 and parts[0] == parts[1]:
            return f"{parts[0][0]}. {parts[-1]}"
        last = parts[-1]
        initials_parts = []
        for part in parts[:-1]:
            if "." in part:
                initials_parts.extend(segment[0] for segment in part.split(".") if segment)
            else:
                initials_parts.append(part[0])
        initials = ".".join(initials_parts) + "."
        return f"{initials} {last}"

    def _running_header_left(self, authors):
        if not authors:
            return ""
        short = self._author_short_name(authors[0].get("name", ""))
        if len(authors) > 1:
            return f"{short} et al."
        return short

    def _article_id_from_doi(self, doi_url):
        if not doi_url:
            return ""
        match = re.search(r"\.(e\d+)$", doi_url.rstrip("/"))
        return match.group(1) if match else ""

    def _license_name_from_url(self, license_url):
        if not license_url:
            return "CC BY-NC-ND"
        match = re.search(r"/licenses/([^/]+)/", license_url)
        if not match:
            return "CC BY-NC-ND"
        slug = match.group(1).upper().replace("-", "-")
        return f"CC {slug}"

    def _running_header_right(self, meta):
        journal = meta.get("journal_name", "Heliyon")
        volume = meta.get("journal_volume", "")
        year = meta.get("copyright_year", "")
        article_id = self._article_id_from_doi(meta.get("doi_url", ""))
        if volume and year and article_id:
            return f"{journal} {volume} ({year}) {article_id}"
        if year and article_id:
            return f"{journal} ({year}) {article_id}"
        return journal

    def _breakable_email_display(self, email, chunk_size=10):
        zws = "\u200b"
        parts = []
        for i, ch in enumerate(email):
            parts.append(ch)
            if (i + 1) % chunk_size == 0 and i + 1 < len(email):
                parts.append(zws)
        return self._tex_escape("".join(parts))

    def _meta_visibility(self, meta, part: str) -> bool:
        vis = meta.get("visibility") or {}
        if part in vis:
            return BaseBlock.should_display({"display": vis[part]})
        return True

    def _render_author_notes(self, meta):
        if not self._meta_visibility(meta, "author_notes"):
            return ""
        authors = meta.get("authors", [])
        affiliations = meta.get("affiliations", {})

        corr_body = "\n".join(
            [rf"\hypertarget{{cor.{mark}}}{{}}\noindent {stars} Corresponding author. {aff_text}\par"
             for author in authors
             for mark in [author.get("corresponding_mark")]
             for stars in [self._corresponding_suffix(mark)]
             for aff_ids in [author.get("affiliation_ids", [])]
             for aff_text in [
                 self._format_affiliation_line(aff_ids[0], affiliations[aff_ids[0]])
                 if aff_ids and aff_ids[0] in affiliations else ""
             ]
             if mark]
        )

        email_parts = []
        for author in authors:
            email = author.get("email", "")
            if not email:
                continue
            short = self._author_short_name(author.get("name", ""))
            display = self._breakable_email_display(email)
            email_parts.append(
                rf"\textcolor{{elsevierlinkblue}}{{\href{{mailto:{email}}}{{{display}}}}} ({short})"
            )
        emails_line = ", ".join(email_parts)

        return "\n".join([
            r"\begin{friauthornotes}",
            r"\vspace*{8pt}",
            r"{\fontsize{7.2}{9}\selectfont",
            r"\setlength{\parindent}{0pt}",
            r"\setlength{\leftskip}{0pt}",
            r"\setlength{\emergencystretch}{2em}",
            r"\settowidth{\dimen0}{Corresponding}%",
            r"\noindent\rule{\dimen0}{0.25pt}\par",
            r"\vspace*{1pt}",
            corr_body,
            r"\noindent\begin{minipage}[t]{\linewidth}",
            r"\raggedright",
            r"\ \ \ \ {\itshape E-mail addresses:}\normalfont\ ",
            rf"{emails_line}.",
            r"\end{minipage}\par",
            r"}",
            r"\end{friauthornotes}",
        ])

    def _render_publication_meta(self, meta):
        if not self._meta_visibility(meta, "publication_meta"):
            return ""
        doi_url = meta.get("doi_url", "")
        received = meta.get("received_date", "")
        revised = meta.get("revised_date", "")
        accepted = meta.get("accepted_date", "")
        available = meta.get("available_online_date", "")
        issn = meta.get("issn", "")
        copyright_year = meta.get("copyright_year", "")
        copyright_holder = meta.get("copyright_holder", "The Authors")
        publisher = meta.get("publisher", "Elsevier Ltd.")
        license_name = self._license_name_from_url(meta.get("license_url", ""))
        license_url = meta.get("license_url", "")

        history_parts = []
        if received:
            history_parts.append(f"Received {received}")
        if revised:
            history_parts.append(f"Received in revised form {revised}")
        if accepted:
            history_parts.append(f"Accepted {accepted}")
        history_line = "; ".join(history_parts)

        body = r"\fontsize{7.2}{9}\selectfont"
        lines = [r"\begin{fripublicationmeta}", r"\vspace*{10pt}", r"{" + body]

        if doi_url:
            lines.append(
                rf"\noindent\textcolor{{elsevierlinkblue}}{{\href{{{doi_url}}}{{{doi_url}}}}}\par"
            )
        if history_line:
            lines.append(rf"\noindent {history_line}\par")
        if available:
            lines.append(rf"\noindent Available online {available}\par")

        if issn:
            copyright_line = (
                rf"{issn}/© {copyright_year} {copyright_holder}. "
                rf"Published by {publisher}."
            )
        else:
            copyright_line = (
                rf"© {copyright_year} {copyright_holder}. "
                rf"Published by {publisher}."
            )
        if license_name:
            copyright_line += (
                rf" This is an open access article under the {license_name} license"
            )
        lines.append(rf"\noindent {copyright_line}\par")

        if license_url:
            lines.append(
                rf"\noindent (\textcolor{{elsevierlinkblue}}{{\href{{{license_url}}}{{{license_url}}}}}).\par"
            )

        lines.extend([r"}", r"\end{fripublicationmeta}"])
        return "\n".join(lines)

    def _render_introduction(self, meta):
        if not self._meta_visibility(meta, "introduction"):
            return ""
        intro = meta.get("introduction", "")
        if not intro:
            return ""

        if isinstance(intro, list):
            paragraphs = [p.strip() for p in intro if p and p.strip()]
        else:
            paragraphs = [p.strip() for p in str(intro).split("\n\n") if p.strip()]
            if len(paragraphs) == 1:
                paragraphs = [str(intro).strip()]

        body_lines = []
        for para in paragraphs:
            body_lines.append(rf"{self._linkify_citations(para)}\par")
            body_lines.append(self._para_skip())

        return "\n".join([
            r"\begin{friintroduction}",
            rf"\vspace*{{{FRI_SECTION_SKIP}}}",
            r"\noindent\rule{\textwidth}{0.25pt}",
            rf"\par\vspace*{{{FRI_BLOCK_SKIP}}}",
            rf"\noindent{{{FRI_BODY_FONT_BF} 1. Introduction}}\par",
            self._para_skip(),
            *self._body_text_block_open(),
            *body_lines,
            r"}",
            r"\end{friintroduction}",
        ])

    def _figure_scale(self, meta) -> float:
        return float(meta.get("figure_scale", FRI_FIGURE_SCALE_DEFAULT))

    def _figure_entry(self, meta, key: str) -> dict:
        return dict(meta.get("figures", {}).get(key, {}))

    def _render_figure_caption(self, meta, key: str) -> str:
        fig = self._figure_entry(meta, key)
        label = self._tex_escape(fig.get("label", "Fig. 1"))
        description = self._tex_escape(
            fig.get("description", "PRISMA flow diagram of selection of eligible studies.")
        )
        margin_top = fig.get("caption_margin_top", FRI_BLOCK_SKIP)
        margin_bottom = fig.get("caption_margin_bottom", FRI_BLOCK_SKIP)
        return "\n".join([
            rf"\vspace*{{{margin_top}}}",
            r"\begin{center}",
            rf"\hypertarget{{{key}}}{{}}",
            rf"{{\bfseries {label}.}} {description}\par",
            r"\end{center}",
            rf"\vspace*{{{margin_bottom}}}",
        ])

    def _table_entry(self, meta, key: str) -> dict:
        return dict(meta.get("tables", {}).get(key, {}))

    def _resolve_table_data(self, entry: dict, project_dir: str = "") -> dict:
        data = dict(entry)
        source = data.get("source")
        if source and project_dir:
            path = os.path.join(project_dir, source)
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    external = json.load(f)
                for key, value in external.items():
                    if key not in data or data[key] in (None, [], {}):
                        data[key] = value
                for key in ("columns", "rows", "footnote"):
                    if key in external:
                        data[key] = external[key]
        return data

    def _table_has_content(self, entry: dict, project_dir: str = "") -> bool:
        data = self._resolve_table_data(entry, project_dir)
        if data.get("pages") or data.get("asset"):
            return True
        return bool(data.get("columns") and data.get("rows"))

    def _render_table_caption(self, meta, key: str) -> str:
        tbl = self._table_entry(meta, key)
        label = self._tex_escape(tbl.get("label", "Table 1"))
        description = self._tex_escape(
            tbl.get("description", "General information about the articles and descriptions of the study sites.")
        )
        margin_top = tbl.get("caption_margin_top", FRI_TABLE_FLOAT_MARGIN)
        margin_bottom = tbl.get("caption_margin_bottom", FRI_TABLE_LABEL_DESC_GAP)
        return "\n".join([
            rf"\vspace*{{{margin_top}}}",
            r"\begin{center}",
            rf"\hypertarget{{{key}}}{{}}",
            rf"{{\bfseries {label}}}\par",
            rf"\vspace*{{{FRI_TABLE_LABEL_DESC_GAP}}}",
            rf"{description}\par",
            r"\end{center}",
            rf"\vspace*{{{margin_bottom}}}",
        ])

    def _auto_table_font_scale(self, n_cols: int) -> float:
        if n_cols >= 8:
            return 0.72
        if n_cols >= 6:
            return 0.75
        return FRI_TABLE_FONT_SCALE

    def _auto_table_column_ratios(self, columns: list) -> list[float]:
        n = len(columns)
        if n == 3:
            return [2.0, 2.0, 1.0]
        if n == 7:
            return [4.0, 12.0, 18.0, 8.0, 14.0, 14.0, 12.0]
        if n == 8:
            return [6.0, 10.0, 18.0, 14.0, 14.0, 12.0, 10.0, 16.0]
        if n == 6:
            return [20.0, 18.0, 14.0, 18.0, 18.0, 12.0]
        return [1.0] * n

    def _table_column_ratios(self, columns: list, data: dict) -> list[float]:
        explicit = data.get("column_ratios")
        if explicit and len(explicit) == len(columns):
            return [float(r) for r in explicit]
        per_col = [col.get("width_ratio") for col in columns]
        if per_col and all(r is not None for r in per_col):
            return [float(r) for r in per_col]
        return self._auto_table_column_ratios(columns)

    def _table_font_spec(self, entry: dict, data: dict, n_cols: int) -> tuple[float, float]:
        scale = self._auto_table_font_scale(n_cols)
        return FRI_BODY_FONT_PT * scale, float(FRI_BODY_BASELINESkip.replace("pt", "")) * scale

    def _table_width_mode(self, n_cols: int) -> str:
        return "full" if n_cols >= FRI_TABLE_WIDE_COLS else "column"

    def _table_width_token(self, width_mode: str) -> str:
        return "textwidth" if width_mode == "full" else "linewidth"

    def _table_column_widths(self, columns: list, width_mode: str, data: dict | None = None) -> list[str]:
        token = self._table_width_token(width_mode)
        ratios = self._table_column_ratios(columns, data or {})
        total = sum(ratios)
        return [
            f"{FRI_TABLE_WIDTH_SCALE * ratio / total:.4f}\\{token}" for ratio in ratios
        ]

    def _table_continued_tex(self, raw_label: str) -> str:
        label = self._tex_escape(raw_label)
        return rf"{{\bfseries {label}}} (continued)"

    def _table_header_rule_lines(self, header: str, n_cols: int = 0, continued: str = "") -> list:
        gap = FRI_TABLE_RULE_GAP
        lines: list[str] = []
        if continued:
            lines.extend([
                rf"\multicolumn{{{n_cols}}}{{@{{}}l@{{}}}}{{{continued}}} \\",
            ])
        lines.extend([
            rf"\noalign{{\vspace*{{{gap}}}}}",
            r"\hline",
            rf"\noalign{{\vspace*{{{gap}}}}}",
            header + r" \\",
            rf"\noalign{{\vspace*{{{gap}}}}}",
            r"\hline",
            rf"\noalign{{\vspace*{{{gap}}}}}",
        ])
        return lines

    def _render_structured_table(self, meta, key: str, project_dir: str = "") -> list:
        entry = self._table_entry(meta, key)
        data = self._resolve_table_data(entry, project_dir)
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        if not columns or not rows:
            return []

        n_cols = len(columns)
        width_mode = self._table_width_mode(n_cols)
        font_size, font_leading = self._table_font_spec(entry, data, n_cols)
        widths = self._table_column_widths(columns, width_mode, data)
        col_spec = "@{}" + "".join(
            f">{{\\raggedright\\arraybackslash}}p{{{width}}}" for width in widths
        ) + "@{}"
        header = " & ".join(self._tex_escape(col["header"]) for col in columns)
        label = self._tex_escape(entry.get("label", "Table 1"))
        description = self._tex_escape(
            entry.get("description", "General information about the articles and descriptions of the study sites.")
        )
        continued_tex = self._table_continued_tex(entry.get("label", "Table 1"))

        lines: list[str] = [r"\begin{fritable}"]
        lines.extend([
            rf"\fontsize{{{font_size:.2f}}}{{{font_leading:.2f}}}\selectfont",
            rf"\hypertarget{{{key}}}{{}}",
            r"\begingroup",
            r"\setlength{\parskip}{0pt}",
            rf"\noindent{{\bfseries {label}}}\\",
            rf"\noindent {description}",
            r"\endgroup",
            rf"\par\vspace*{{{FRI_TABLE_CAPTION_TABLE_GAP}}}",
            rf"\renewcommand{{\arraystretch}}{{{FRI_TABLE_ROW_STRETCH}}}",
        ])
        if n_cols >= FRI_TABLE_WIDE_COLS:
            lines.append(rf"\setlength{{\tabcolsep}}{{{FRI_TABLE_TIGHT_COLSEP}}}")
        lines.extend([
            r"\setlength{\LTpre}{0pt}",
            r"\setlength{\LTpost}{0pt}",
            rf"\begin{{longtable}}{{{col_spec}}}",
            *self._table_header_rule_lines(header),
            r"\endfirsthead",
            *self._table_header_rule_lines(header, n_cols, continued_tex),
            r"\endhead",
            r"\hline",
            r"\endfoot",
            r"\hline",
            r"\endlastfoot",
        ])
        for row in rows:
            if isinstance(row, dict) and not BaseBlock.should_display(row):
                continue
            cells = []
            for col in columns:
                raw = str(row.get(col["key"], "")).strip()
                cells.append(self._linkify_citations(raw) if raw else "")
            lines.append(" & ".join(cells) + r" \\")
        lines.extend([r"\end{longtable}"])
        footnote = data.get("footnote")
        if footnote:
            footnote_tex = self._linkify_citations(footnote)
            lines.append(
                rf"\noindent{{\fontsize{{{font_size:.2f}}}{{{font_leading:.2f}}}\selectfont\itshape "
                rf"{footnote_tex}}}\par"
            )
        lines.append(r"\end{fritable}")
        return lines

    def _render_table_block(self, meta, key: str, project_dir: str = "") -> list:
        entry = self._table_entry(meta, key)
        if not BaseBlock.should_display(entry):
            return []
        data = self._resolve_table_data(entry, project_dir)
        if data.get("columns") and data.get("rows"):
            return self._render_structured_table(meta, key, project_dir)
        return self._render_float_block(meta, "table", key, project_dir)

    def _render_float_block(self, meta, kind: str, key: str, project_dir: str = "") -> list:
        entry = self._figure_entry(meta, key) if kind == "figure" else self._table_entry(meta, key)
        if not BaseBlock.should_display(entry):
            return []
        if kind == "table" and not (entry.get("pages") or entry.get("asset")):
            return []
        assets = entry.get("pages") or ([entry["asset"]] if entry.get("asset") else [])
        if not assets:
            return []
        scale = float(entry.get("scale", self._figure_scale(meta)))
        margin = round((1.0 - scale) / 2.0, 4)
        scale = round(scale, 4)
        margin_top = entry.get("float_margin_top", FRI_BLOCK_SKIP)
        lines = [rf"\vspace*{{{margin_top}}}", r"\nointerlineskip"]
        for asset in assets:
            lines.append(
                rf"\noindent\hspace{{{margin}\linewidth}}"
                rf"\includegraphics[width={scale}\linewidth,keepaspectratio]{{{asset}}}\par"
            )
        if kind == "figure":
            lines.append(self._render_figure_caption(meta, key))
        else:
            lines.append(self._render_table_caption(meta, key))
        return lines

    def _figure_key(self, n: int) -> str:
        return f"fig{n}"

    def _float_has_content(self, kind: str, key: str, meta, project_dir: str) -> bool:
        if kind == "figure":
            return bool(self._figure_entry(meta, key).get("asset"))
        return self._table_has_content(self._table_entry(meta, key), project_dir)

    def _render_subsections(
        self,
        subsections,
        meta,
        project_dir: str,
        inserted: set,
        depth: int = 1,
    ) -> list:
        blocks = []
        for sub in subsections:
            if not BaseBlock.should_display(sub):
                continue
            title = sub.get("title", "")
            paragraphs = sub.get("paragraphs", [])
            content = sub.get("content")
            nested = sub.get("subsections", [])
            self._require_content_not_paragraphs(title, paragraphs, content)
            if title:
                anchor = self._subsection_anchor_id(title)
                if depth == 1:
                    blocks.extend([
                        rf"\vspace*{{{FRI_SUBSECTION_SKIP}}}",
                    ])
                    if anchor:
                        blocks.append(rf"\hypertarget{{{anchor}}}{{}}")
                    blocks.extend([
                        rf"\noindent{{{FRI_BODY_FONT_BF} {self._tex_escape(title)}}}\par",
                        rf"\vspace*{{{FRI_SUBSECTION_TITLE_SKIP}}}",
                    ])
                else:
                    blocks.extend([
                        rf"\vspace*{{{FRI_SUBSUBSECTION_SKIP}}}",
                    ])
                    if anchor:
                        blocks.append(rf"\hypertarget{{{anchor}}}{{}}")
                    blocks.extend([
                        rf"\noindent{{{FRI_BODY_FONT_BF_IT} {self._tex_escape(title)}}}\par",
                        rf"\vspace*{{{FRI_SUBSUBSECTION_TITLE_SKIP}}}",
                    ])
            if content:
                blocks.extend(
                    self._render_content_sequence(content, meta, project_dir, inserted)
                )
            if nested:
                blocks.extend(
                    self._render_subsections(
                        nested, meta, project_dir, inserted, depth + 1
                    )
                )
        return blocks

    # Block types that make up the article body; everything else (bibliography,
    # acknowledgements, arxiv margin, ...) stays outside `fribody`.
    _BODY_BLOCK_TYPES = (
        "section",
        "subsection",
        "subsubsection",
        "text",
        "figure",
        "table",
        "equation",
        "math",
        "code",
    )

    def _split_body_blocks(self, rendered_content: str, block_types) -> tuple[str, str]:
        """Split the rendered block tree into (body_tex, extra_tex) by block type."""
        pattern = re.compile(
            r"% \[BEGIN_BLOCK: ([^\]]+)\]\s*(.*?)\s*% \[END_BLOCK: \1\]",
            re.DOTALL,
        )
        body: list[str] = []
        extra: list[str] = []
        for match in pattern.finditer(rendered_content):
            chunk = match.group(0).strip()
            block_type = (block_types or {}).get(match.group(1), "")
            (body if block_type in self._BODY_BLOCK_TYPES else extra).append(chunk)
        return "\n".join(body), "\n".join(extra)

    def _render_body_sections(self, meta, project_dir: str = "", extra_tex: str = ""):
        sections = meta.get("body_sections", [])
        if not sections and not extra_tex:
            return ""

        blocks: list[str] = [
            r"\begin{fribody}",
            *self._body_text_block_open(indent=True),
        ]
        inserted: set[str] = set()
        for section in sections:
            if not BaseBlock.should_display(section):
                continue
            title = section.get("title", "")
            paragraphs = section.get("paragraphs", [])
            subsections = section.get("subsections", [])
            content = section.get("content")
            self._require_content_not_paragraphs(title, paragraphs, content)
            if not title or (not content and not subsections):
                continue
            section_anchor = self._section_anchor_id(title)
            if section_anchor:
                blocks.append(rf"\hypertarget{{{section_anchor}}}{{}}")
            blocks.extend([
                self._section_skip(),
                rf"\noindent{{{FRI_BODY_FONT_BF} {self._tex_escape(title)}}}\par",
            ])
            if content:
                blocks.extend(
                    self._render_content_sequence(content, meta, project_dir, inserted)
                )
            if subsections:
                blocks.extend(
                    self._render_subsections(
                        subsections,
                        meta,
                        project_dir,
                        inserted,
                    )
                )
        if extra_tex:
            blocks.append(extra_tex)
        blocks.append(r"}")
        blocks.append(r"\end{fribody}")
        return "\n".join(blocks)

    def _render_back_matter(self, meta, project_dir: str = "") -> str:
        items = meta.get("back_matter") or []
        if not items:
            return ""
        blocks: list[str] = [*self._body_text_block_open()]
        inserted: set[str] = set()
        for item in items:
            if not BaseBlock.should_display(item):
                continue
            title = str(item.get("title", "")).strip()
            paragraphs = item.get("paragraphs") or []
            content = item.get("content")
            if title:
                blocks.extend(self._render_back_matter_title(title))
            if content:
                blocks.extend(
                    self._render_content_sequence(content, meta, project_dir, inserted)
                )
            for para in paragraphs:
                text = self._linkify_citations(str(para).strip())
                if text:
                    blocks.append(rf"{text}\par")
                    blocks.append(self._para_skip())
        blocks.append(r"}")
        return "\n".join(blocks)

    def _render_abs_col(self, meta, abstract):
        abstract_tex = self._linkify_citations(str(abstract))
        return "\n".join([
            r"\begin{spacing}{0.79}",
            r"{\fontsize{7.2}{9}\selectfont\hspace{1.5em}",
            rf"{abstract_tex}",
            r"}",
            r"\end{spacing}",
        ])

    def _render_info_abstract(self, meta):
        if not self._meta_visibility(meta, "abstract"):
            return ""
        keywords = meta.get("keywords", [])
        abstract = meta.get("abstract", "")
        kw_body = "\n".join(
            [r"\noindent{\itshape Keywords:}\par"]
            + [rf"\noindent\normalfont {kw}\par" for kw in keywords]
        )
        left_width = r"0.29\linewidth"
        right_width = r"\dimexpr\linewidth-0.29\linewidth-18pt\relax"

        kw_col = "\n".join([
            r"{\fontsize{6.4}{8}\selectfont",
            r"\setlength{\parskip}{0pt}",
            r"\setlength{\baselineskip}{8pt}",
            r"\setlength{\parindent}{0pt}",
            rf"{kw_body}",
            r"}",
        ])
        abs_col = self._render_abs_col(meta, abstract)

        return "\n".join([
            r"\begin{friinfoabstract}",
            r"\linespread{1}\selectfont",
            r"\newlength{\frirulebodysep}",
            r"\setlength{\frirulebodysep}{0.667pt}",
            r"\noindent",
            rf"\begin{{tabular}}[t]{{@{{}}p{{{left_width}}}@{{\hspace{{18pt}}}}p{{{right_width}}}@{{}}}}",
            r"{\fontsize{7}{7}\selectfont A\ R\ T\ I\ C\ L\ E\ \ I\ N\ F\ O} &",
            r"{\fontsize{7}{7}\selectfont A\ B\ S\ T\ R\ A\ C\ T}",
            r"\end{tabular}",
            r"\par\noindent",
            rf"\begin{{minipage}}[t]{{{left_width}}}\noindent\rule{{\linewidth}}{{0.25pt}}\end{{minipage}}%",
            r"\hspace{18pt}%",
            rf"\begin{{minipage}}[t]{{{right_width}}}\noindent\rule{{\linewidth}}{{0.25pt}}\end{{minipage}}",
            r"\par\vspace*{\frirulebodysep}",
            rf"\setcolumnwidth{{{left_width}, {right_width}}}",
            r"\setlength{\columnsep}{18pt}",
            r"\begin{paracol}{2}",
            r"\noindent",
            r"\setlength{\parindent}{0pt}",
            kw_col,
            r"\switchcolumn",
            abs_col,
            r"\end{paracol}",
            r"\end{friinfoabstract}",
        ])

    def render_preamble(self, state):
        meta = state.get("metadata", {})
        page_mode = meta.get("page_mode", "full")

        preamble = [
            r"\documentclass[a4paper,fleqn]{cas-dc}",
            r"\usepackage{graphicx}",
            r"\usepackage{capt-of}",
            r"\usepackage{array}",
            r"\usepackage{longtable}",
            r"\usepackage{needspace}",
            r"\usepackage{xcolor}",
            r"\definecolor{elsevierteal}{HTML}{0976A0}",
            r"\definecolor{elsevierlinkblue}{HTML}{2196D1}",
            r"\definecolor{elseviergray}{HTML}{E8E8E8}",
            r"\hypersetup{breaklinks=true, urlcolor=elsevierlinkblue, linkcolor=elsevierlinkblue, bookmarks=false}",
            r"\newenvironment{frijournalheader}{}{}",
            r"",
        ]

        if page_mode in (
            "upper_header_only",
            "header_through_affiliations",
            "header_through_info_abstract",
            "header_through_author_notes",
            "header_through_publication_meta",
            "header_through_introduction",
            "full_report",
        ):
            return "\n".join(self._article_test_preamble(meta))

        title = meta.get("title", "Untitled")
        preamble.extend([
            r"\usepackage[authoryear,longnamesfirst]{natbib}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage[T1]{fontenc}",
            r"\let\WriteBookmarks\relax",
            r"\def\floatpagepagefraction{1}",
            r"\def\textpagefraction{.001}",
            r"",
            f"\\title [mode = title]{{{title}}}",
            r"",
            r"\shorttitle{Food Research International Article}",
            r"\shortauthors{Authors}",
            r"",
        ])

        authors = meta.get("authors", [])
        affiliations = meta.get("affiliations", {})
        cor_texts = {}

        if authors:
            for author in authors:
                name = author.get("name", "")
                email = author.get("email", "")
                cormark = author.get("corresponding_mark", None)
                cortext = author.get("corresponding_text", "")
                affil_ids = author.get("affiliation_ids", [])

                if affil_ids:
                    affil_str = ",".join(str(aid) for aid in affil_ids)
                    preamble.append(f"\\author[{affil_str}]{{{name}}}")
                else:
                    preamble.append(f"\\author{{{name}}}")

                if email:
                    preamble.append(f"\\ead{{{email}}}")
                if cormark is not None:
                    preamble.append(f"\\cormark[{cormark}]")
                    if cortext and cormark not in cor_texts:
                        cor_texts[cormark] = cortext

            for affil_id, affil_data in affiliations.items():
                org = affil_data.get("organization", "")
                address = affil_data.get("addressline", "")
                city = affil_data.get("city", "")
                postcode = affil_data.get("postcode", "")
                state_prov = affil_data.get("state", "")
                country = affil_data.get("country", "")

                affil_str = f"\\affiliation[{affil_id}]{{organization={{{org}}}"
                if address:
                    affil_str += f", addressline={{{address}}}"
                if city:
                    affil_str += f", city={{{city}}}"
                if postcode:
                    affil_str += f", postcode={{{postcode}}}"
                if state_prov:
                    affil_str += f", state={{{state_prov}}}"
                if country:
                    affil_str += f", country={{{country}}}"
                affil_str += "}"
                preamble.append(affil_str)

            for cm_id, c_text in cor_texts.items():
                preamble.append(f"\\cortext[{cm_id}]{{{c_text}}}")
        else:
            preamble.append(r"\author[1]{Anonymous Author}")
            preamble.append(r"\affiliation[1]{organization={Unknown Institution}}")

        received = meta.get("received_date")
        if received:
            preamble.append(f"\\received{{{received}}}")
        revised = meta.get("revised_date")
        if revised:
            preamble.append(f"\\revised{{{revised}}}")
        accepted = meta.get("accepted_date")
        if accepted:
            preamble.append(f"\\accepted{{{accepted}}}")

        # `\begin{document}` closes the preamble; every package / title / author
        # line above must precede it (LaTeX forbids \usepackage after it).
        preamble.append(r"\begin{document}")
        return "\n".join(preamble)

    def build_document(self, state):
        self.validate_state(state)
        self.validate_bibliography_citations(state)
        meta = state.get("metadata", {})
        page_mode = meta.get("page_mode", "full")

        lines = []
        lines.append(self.render_preamble(state))

        rendered_content = state.get("rendered_content", "")

        header_match = re.search(
            r"% \[BEGIN_BLOCK: ([^\]]+)\]\s*\\begin\{frijournalheader\}(.*?)\\end\{frijournalheader\}\s*% \[END_BLOCK: \1\]",
            rendered_content,
            re.DOTALL,
        )
        header_tex = ""
        if header_match:
            block_id = header_match.group(1)
            header_inner = header_match.group(2).strip()
            header_tex = (
                f"% [BEGIN_BLOCK: {block_id}]\n{header_inner}\n% [END_BLOCK: {block_id}]"
            )
            rendered_content = rendered_content.replace(header_match.group(0), "")

        if page_mode == "upper_header_only":
            if header_tex:
                lines.append(header_tex)
            lines.append(r"\end{document}")
            return "\n".join(lines)

        if page_mode == "header_through_affiliations":
            if header_tex:
                lines.append(header_tex)
            lines.append(self._render_lower_header(meta))
            lines.append(r"\end{document}")
            return "\n".join(lines)

        if page_mode == "header_through_info_abstract":
            if header_tex:
                lines.append(header_tex)
            lines.append(self._render_lower_header(meta))
            lines.append(self._render_info_abstract(meta))
            lines.append(r"\end{document}")
            return "\n".join(lines)

        if page_mode in ("header_through_author_notes",):
            if header_tex:
                lines.append(header_tex)
            lines.append(self._render_lower_header(meta))
            lines.append(self._render_info_abstract(meta))
            # The abstract is full-width and its page extent is unknown until it
            # is typeset, so let the fill glue absorb the leftover vertical space
            # and drop the author notes to the bottom of that page.
            lines.append(r"\par\vfill")
            lines.append(self._render_author_notes(meta))
            lines.append(r"\end{document}")
            return "\n".join(lines)

        if page_mode in ("header_through_publication_meta", "header_through_introduction", "full_report"):
            if header_tex:
                lines.append(header_tex)
            lines.append(self._render_lower_header(meta))
            lines.append(self._render_info_abstract(meta))
            # The author notes + publication meta are the journal's page-bottom
            # lockup: they are rendered into \friFooterBox (the absolute overlay
            # pinned to the foot of page 1) while the body keeps filling the
            # space above them. Their height is reserved out of page 1 by
            # shrinking \@colht/\@colroom -- the registers paracol reads to size
            # its columns -- and no page break is forced, so the body continues
            # on this page.
            lines.append(r"\par")
            lines.append(r"\sbox{\friFooterBox}{\begin{minipage}{\textwidth}")
            lines.append(self._render_author_notes(meta))
            lines.append(self._render_publication_meta(meta))
            lines.append(r"\end{minipage}}")
            lines.append(r"\makeatletter")
            lines.append(r"\setlength{\friFooterNormColHt}{\@colht}")
            lines.append(r"\setlength{\friFooterNormColRoom}{\@colroom}")
            for _reg in (r"\@colht", r"\@colroom"):
                lines.append(
                    rf"\addtolength{{{_reg}}}{{-\dimexpr\ht\friFooterBox"
                    rf"+\dp\friFooterBox+{FRI_FOOTER_GAP}\relax}}"
                )
            lines.append(r"\makeatother")
            if page_mode in ("header_through_introduction", "full_report"):
                intro_tex = self._render_introduction(meta)
                if intro_tex:
                    lines.append(intro_tex)
            if page_mode == "full_report":
                project_dir = state.get("project_dir", "")
                block_body, extra_blocks = self._split_body_blocks(
                    rendered_content, state.get("block_types", {})
                )
                body_tex = self._render_body_sections(
                    meta, project_dir, extra_tex=block_body
                )
                body_region: list[str] = []
                if body_tex:
                    body_region.append(body_tex)
                if extra_blocks:
                    body_region.append(extra_blocks)
                back_tex = self._render_back_matter(meta, project_dir)
                if back_tex:
                    body_region.append(back_tex)
                bib_tex = self._render_bibliography(state)
                if bib_tex:
                    body_region.append(bib_tex)
                if body_region:
                    # The article body flows in two equal columns; paracol splits
                    # \textwidth into half-width columns separated by the gutter.
                    # \columnratio{0.5,0.5} is required because paracol's
                    # \setcolumnwidth is global state: the front-matter abstract
                    # sets 0.29/0.71 and would otherwise leak into the body.
                    lines.append(rf"\setlength{{\columnsep}}{{{FRI_COLUMN_SEP}}}")
                    lines.append(r"\columnratio{0.5,0.5}")
                    lines.append(r"\begin{paracol}{2}")
                    lines.extend(body_region)
                    lines.append(r"\end{paracol}")
            lines.append(r"\end{document}")
            return "\n".join(lines)

        abstract = meta.get("abstract")
        if abstract:
            lines.append(r"\begin{abstract}")
            lines.append(abstract)
            lines.append(r"\end{abstract}")

        keywords = meta.get("keywords", [])
        if keywords:
            lines.append(r"\begin{keywords}")
            lines.append(" \\sep ".join(keywords))
            lines.append(r"\end{keywords}")

        if header_tex:
            lines.append(header_tex)

        lines.append(r"\maketitle")

        rendered_content = re.sub(
            r"% \[BEGIN_BLOCK:[^\]]+\]\s*% \[END_BLOCK:[^\]]+\]\s*",
            "",
            rendered_content,
            flags=re.DOTALL,
        ).strip()
        if rendered_content:
            lines.append(rendered_content)
        lines.append(r"\end{document}")

        return "\n".join(lines)
