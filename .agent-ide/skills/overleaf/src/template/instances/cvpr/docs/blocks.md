**This file lists only this instance's blocks.** How blocks resolve, the plugin contract and the field reference live one level up: `docs/blocks.md`.

## Catalog

**The catalogue is the block contract for this venue**: read the required and optional columns together, because a required field left empty fails the build.

| Type | Kind | Required | Optional |
|---|---|---|---|
| `section` | container | `title` | `label`, `unnumbered`, `align`, `margin_top`, `margin_bottom` |
| `subsection` | container | `title` | `label`, `align` |
| `subsubsection` | container | `title` | `label`, `align` |
| `text` | leaf | `text` | `align`, `margin_top`, `margin_bottom` |
| `figure` | leaf | — (needs `path` or `images`) | `path`, `images`, `caption`, `label`, `width`, `columns`, `span_columns`, `use_subfigures`, `placement`, `is_teaser`, `caption_margin_top` |
| `table` | leaf | `rows` | `header`, `caption`, `label`, `columns`, `placement`, `span_columns`, `size`, `midrules`, `notes`, `align`, `margin_top`, `margin_bottom` |
| `list` | leaf | `items` | `style` (`itemize`/`enumerate`), `compact`, `align`, `margin_top`, `margin_bottom` |
| `teaser` | leaf | — (needs `path` or `paths`) | `path`, `paths`, `caption`, `label` |
| `equation` | leaf | `math` | `label` |
| `math` | leaf | `math` | — |
| `code` | leaf | `code` | `language`, `caption`, `label`, `align` |
| `bibliography` | leaf | `bibtex` | `style` |
| `acknowledgements` | container | `text` | — |
| `arxiv_margin` | leaf | `text` | — |

Allowed children — `section`: `text`, `figure`, `table`, `list`, `equation`,
`math`, `subsection`, `subsubsection`, `teaser`, `code`; `subsection` and
`subsubsection`: the same minus `subsection`/`teaser`;
`acknowledgements`: `text`, `figure`, `equation`, `math`, `list`.

### `table` and `list` in practice

Cells in `rows` / `header` / `items` are **verbatim LaTeX**, so `\textbf{}`,
`$\pm$`, `\multicolumn{2}{c}{...}` and `\cite{key}` are written inline rather
than exposed as fields. `columns` takes a raw `tabular` column spec
(`p{2.1cm}` included); omitted, it is `l` followed by `c`. Rows shorter than the
widest row are padded with empty cells instead of being rejected.

`midrules` is a list of 1-based body row indices to draw an `\hline` after —
the group separator of a results table. Rules are `\hline`, not
`\toprule`/`\midrule`: no shipped instance loads `booktabs`, and a document that
needs booktabs must load it itself in a `text` block before first use.

`span_columns: true` promotes `table` to `table*` for a full-width float;
`size` prepends a size switch (`\small`, `\footnotesize`) inside the float;
`notes` renders a `\footnotesize` note under the rules.
