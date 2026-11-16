**This file lists only this instance's blocks.** How blocks resolve, the plugin contract and the field reference live one level up: `docs/blocks.md`.

## Catalog

**The catalogue is the block contract for this venue**: read the required and optional columns together, because a required field left empty fails the build.

| Type | Kind | Required | Optional |
|---|---|---|---|
| `section` | container | `title` | `label`, `paragraphs`, `content`, `display`¹ |
| `subsection` | container | `title` | `label`, `paragraphs`, `content`, `display`¹ |
| `text` | leaf | `text` | `display`¹, `align`, `margin_top`, `margin_bottom` |
| `figure` | leaf | — (needs `path` or `images`) | `path`, `images`, `caption`, `label`, `width`, `columns`, `span_columns`, `use_subfigures`, `placement`, `caption_margin_top` |
| `equation` | leaf | `math` | `label` |
| `math` | leaf | `math` | — |
| `code` | leaf | `code` | `language`, `caption`, `label` |
| `bibliography` | leaf | `bibtex` | `style` |
| `acknowledgements` | container | `text` | — |
| `arxiv_margin` | leaf | `text` | — |
| `journal_header` | leaf | — | `journal_name`, `citation`, `homepage`, `publisher_logo_path`, `cover_path`, `use_custom_thumbnails`, `display`¹ |

¹ Declared in the manifest but **inert** at block level — a `display` inside `content` is never read; use the top-level flag. See [`display`](#display).

Allowed children — `section`: `text`, `figure`, `equation`, `math`,
`subsection`, `code`; `subsection`: `text`, `figure`, `equation`, `math`,
`code`; `acknowledgements`: `text`, `figure`, `equation`, `math`.

`fri` overrides `text`, `section`, `subsection` and `code` with its own
typography, and adds `journal_header` for the page-1 masthead.
