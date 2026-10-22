"""FRI journal layout constants — single source for template + blocks."""

FRI_PAGE_TOP = "52pt"
FRI_HEAD_HEIGHT = "12pt"
FRI_HEAD_SEP = "6pt"
FRI_TOP_MARGIN_ADJUST = "14pt"
FRI_FOOT_BOTTOM = "33pt"
# Gap kept between the last body line and the pinned page-bottom footer lockup.
FRI_FOOTER_GAP = "12pt"
FRI_BLOCK_SKIP = "6pt"
FRI_SECTION_SKIP = "10pt"
FRI_SUBSECTION_SKIP = "8pt"
FRI_SUBSUBSECTION_SKIP = "6pt"
FRI_SUBSECTION_TITLE_SKIP = "4pt"
FRI_SUBSUBSECTION_TITLE_SKIP = "3pt"
FRI_BODY_FONT_PT = 7.97
FRI_BODY_BASELINESkip = "10pt"
FRI_BODY_FONT = r"\fontsize{7.97}{10}\selectfont"
FRI_BODY_FONT_BF = r"\fontsize{7.97}{10}\selectfont\bfseries"
FRI_BODY_FONT_BF_IT = r"\fontsize{7.97}{10}\selectfont\bfseries\itshape"
FRI_REF_FONT_PT = 6.38
FRI_REF_BASELINESkip = "8pt"
FRI_REF_FONT = r"\fontsize{6.38}{8}\selectfont"
FRI_RUNNING_FONT = r"\fontsize{6.38}{8}\selectfont"
FRI_CODE_FONT = r"\fontsize{7.97}{10}\selectfont\ttfamily"
FRI_TABLE_FONT_SCALE = 0.8
FRI_TABLE_ROW_STRETCH = 1.1
FRI_TABLE_RULE_GAP = "2pt"
FRI_TABLE_WIDE_COLS = 6
FRI_TABLE_WIDTH_SCALE = 0.96
FRI_TABLE_TIGHT_COLSEP = "1.5pt"
FRI_TABLE_CAPTION_TABLE_GAP = "1pt"
FRI_TABLE_LABEL_DESC_GAP = "0pt"
FRI_TABLE_FLOAT_MARGIN = "2pt"
FRI_PAGE_NUMBER_SIZE = FRI_RUNNING_FONT
FRI_FIGURE_SCALE_DEFAULT = 0.8

# Body paragraph first-line indent ("文段顶格"): a third of the original four
# body characters wide, tuned for the two-column body. Section/subsection titles
# never indent (`\noindent`), so the two stay distinct.
FRI_PAR_INDENT = "1.3333em"

# The article body runs in two equal columns (double-column journal layout), so
# each column is half the text width. The gutter matches the front-matter
# abstract and `cas-dc.cls` (18pt).
FRI_COLUMN_SEP = "18pt"
