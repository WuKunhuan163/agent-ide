# Blocks

Everything an agent or a template author needs to know about block types: how a
type is resolved, what the plugin contract is, which types each shipped instance
offers, and how to add a new one.

**The manifest is the machine authority for `content`.** Field lists below are
the human-readable view of
`src/template/instances/<id>/template.json` → `blocks.<type>.{required,optional}`
— when the two ever disagree, `template.json` wins.

## Resolution

For instance `<id>` and type `<type>`, first hit wins:

1. `src/template/instances/<id>/blocks/<type>.py` — instance override
2. `src/template/blocks/<group>/<type>.py`, scanning groups in the fixed order
   **`text` → `media` → `tables` → `math` → `refs`**
3. nothing found → `BLOCK_TYPE_UNKNOWN`

The discovered module must define `class Block`. Resolution results are cached
per `(instance, type)` for the life of the process.

Instance and block modules are loaded by absolute path, so **their imports must
be absolute package imports** (`from src.template...`, `from src.store...`).
Instance directories are deliberately not added to `sys.path`.

## The plugin contract

```python
from src.template.block_base import BaseBlock


class Block(BaseBlock):
    def render(self, child_contents: str = "") -> str:
        return f"{self.content['text']}\n"
```

| Member | Role |
|---|---|
| `is_leaf` | class attr, default `True`. A leaf that is given children raises `LEAF_CANNOT_HAVE_CHILDREN` in `validate` |
| `validate()` | runs from `__init__`. Only for checks the manifest cannot express (e.g. "`path` **or** `images`"); raise `DataError`, never a bare exception |
| `render(child_contents)` | the only required method. Must return a LaTeX string; containers receive their children's rendered TeX |
| `apply_layout(tex)` | helper: wraps/appends `margin_top`, `margin_bottom`, `align` (`center`/`right`) |
| `content` | the block's `content` dict, plus the injected keys below |
| `parent_id` | the parent block's **`rel_path`** (`""` at top level). Rarely needed |

### Typography hooks

A shared block emits shared *structure*; an instance supplies the *typography*
by overriding a hook, never by copying the plugin:

| Plugin | Hook | Default |
|---|---|---|
| `text` | `TEXT_SUFFIX` (class attr) | `""` — appended after the paragraph and a newline |
| `section` | `heading(title)` | `\section{title}`, or `\section*` when `unnumbered` |
| `subsection` | `heading(title)` | `\subsection{title}` |

`fri`'s `text`, `section` and `subsection` overrides are each a few lines of
exactly this: a subclass plus one hook. Everything else — `label` handling,
children, `apply_layout`, the leaf backstop — stays in one place.

Injected into `content` by the renderer, on a copy — they are **not** stored in
`block.json` and never appear in a manifest's field lists:

- `_project_dir` — the project root (`.../data/projects/<agent>/<proj>`)
- `_output_dir` — the build directory (`.../<proj>/build`)

Plugins that write files (figures, thumbnails, `references.bib`) write them under
`_output_dir`, never into the project.

### Structure is not the plugin's job

Nesting is enforced by the **store**, from the manifest: `leaf`, `container`, and
`allowed_children` (with `"*"` as a wildcard) are checked by `src/store/tree.py`
on every write. The manifest is the single authority, and it is per-instance —
the `cvpr` and `fri` `section` types accept different children.

`BaseBlock` therefore declares no child list. The only structural fact a plugin
restates is `is_leaf`, which `BaseBlock.validate` uses as a cheap backstop
against a tree that did not come through the store. Adding a container means
setting `is_leaf = False` **and** putting the child list in `template.json`.

### `display`

A block's visibility is the **top-level `display`** in `block.json`: `false`
makes the renderer emit nothing for that block and its subtree while the block
stays in the tree. Set it with `edit add --display` / `edit set --at <block>.display`,
never through `content`. It is read once per node by `BaseBlock.should_display`
at the render boundary (`render.py`).

A `display` key **inside `content` does not work**. The block-level call passes
`{"display": block.display, "content": block.content}`, and the top-level flag is
a required boolean, so the content-level fallback inside `should_display` is
unreachable. `fri` still lists `display` in the manifest for `section` /
`subsection` / `text` / `journal_header`; that entry is **inert vocabulary** —
setting it passes validation and then changes nothing.

The one place a `display` key does take effect is **inside metadata**: `fri`'s
preamble hands metadata rows, sections, tables and figures straight to
`should_display`, so `display: false` on such an entry hides it.
`should_display` also accepts `0`/`1` and the strings `false`, `no`, `none`,
`hidden`, `off`.

Hidden means hidden **everywhere**. Content validation and the citation/label
index both walk the visible view (`Project.visible_blocks`), so a hidden subtree
may hold draft content without blocking `build`, contributes no `\label` and no
citation key, and a visible `\ref` to a label only a hidden block defines is a
real `LABEL_UNDEFINED` rather than a dangling reference in the PDF. `order`
uniqueness and the template binding still check the whole tree — see
[`errors-and-validation.md`](errors-and-validation.md).

## Content is validated before render

`build` refuses to run on an invalid project, and the render boundary re-checks
each block against the manifest (`check_content`). A missing required field or an
unlisted field is `CONTENT_INVALID` — both when you write the block and when you
build. Plugins can therefore index `self.content["field"]` directly for required
fields instead of re-validating them.

## Catalog: `cvpr`

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

## Catalog: `fri`

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

## Field reference

**Text and headings**

- `text` — body text. Emitted verbatim, so inline LaTeX is allowed. Write
  paragraphs as one string, not a list.
- `title` — heading text. `section`/`subsection` only.
- `label` — LaTeX `\label` target for `\ref`/`\eqref` resolution. On `text` and
  `figure` it is also what `indexes` collects.
- `unnumbered` — `cvpr` `section` only: emits `\section*`.
- `paragraphs`, `content` — declared by `fri` sections for compatibility; the
  `fri` heading plugins do not read them.

**Layout**

- `align` — `center` or `right`; anything else is ignored.
- `margin_top` / `margin_bottom` — vertical space, a LaTeX dimension such as
  `12pt`.
- These apply only to plugins that call `apply_layout` (`text`, `section`,
  `subsection`, `code`, and the instance overrides of them). `acknowledgements`,
  `math` and `equation` skip it, so declaring `align` there has no effect.

**Media**

- `path` — one image, relative to the build dir, falling back to the project's
  `input/` directory. `images` — a list of either bare paths or objects with
  `path`, `width`, `caption`, `label`, `sub_width`.
- `caption`, `label` — figure caption and its label.
- `width` — either a bare fraction of `\linewidth` (`"0.8"`) or a full LaTeX
  dimension (`"8cm"`, `"\\linewidth"`).
- `columns` — grid columns; defaults to the number of images.
- `use_subfigures` — wrap images in `subfigure`; defaults to `true` when there is
  more than one image.
- `span_columns` — use the starred float environment (full width in two-column
  layouts).
- `placement` — float placement specifier, default `t`.
- `caption_margin_top` — space between the image grid and the caption.
- `is_teaser` (`cvpr` `figure`) — emit the CVPR teaser band instead of a float.
- `teaser` (`cvpr`) — dedicated teaser plugin; `paths` is the multi-image form.
  Aspect ratios are read from the image headers with the standard library, so no
  image package is needed.
- Images are copied into `build/assets/` as `<block_id>_<index>_<name>`, keeping
  the original file name at the end so extensions survive.

**Math and code**

- `math` — the LaTeX body, without the delimiters. `equation` wraps it in
  `equation` (plus `label`); `math` wraps it in `\[ ... \]`.
- `code` — verbatim source, `language` — a `listings` language, default
  `python`. `caption` and `label` are passed to `lstlisting`. The shared plugin
  escapes `_` in the caption.

**References**

- `bibtex` — the BibTeX source. The `bibliography` plugin writes it to
  `build/references.bib` and emits `\bibliographystyle` + `\bibliography`.
  `style` selects the style, default `ieeetr`.
- If the project also has `references.bib` at its root, `build` copies that file
  over the rendered one — **the project file wins**. Pick one source of truth.
- `arxiv_margin` — a rotated grey `text` note in the page margin, via
  `\AddToShipoutPicture*` (current page only).

**Masthead (`fri` `journal_header`)**

- `journal_name`, `citation`, `homepage` — the three masthead text slots.
- `publisher_logo_path` / `cover_path` — file names under the project's
  `assets/`, used as the left and right images **only when**
  `use_custom_thumbnails` is true. Otherwise the instance's bundled placeholder
  images are copied in. No image library is required either way.

## Adding a block plugin

1. Decide the group and create `src/template/blocks/<group>/<type>.py` (or
   `src/template/instances/<id>/blocks/<type>.py` to override for one instance).
   Each group directory carries a one-line `__init__.py` marker; imports resolve
   without it, but keep it to match the existing groups.
2. Write `class Block(BaseBlock)` with a `render(child_contents="")` returning
   LaTeX. Call `apply_layout(tex)` last if you want `align`/`margin_*` to work.
   To restyle an existing type for one instance, subclass the shared plugin and
   override its typography hook — do not copy the plugin.
3. Add a `<type>` entry to every instance's `template.json` → `blocks`, listing
   `required` and `optional` field names. This is what makes the type usable:
   unknown types fail `spec()` with `BLOCK_TYPE_UNKNOWN`, and unlisted content
   fields fail `check_content` with `CONTENT_INVALID`.
4. For containers add `"container": true` and `allowed_children`; for leaves
   either omit both or state `"leaf": true`. Set `is_leaf = False` on the class
   for containers — that flag is the only structural mirror the plugins keep.
5. Add a `validate()` only if you must enforce something the manifest cannot
   express — and raise `DataError` with a stable code.
6. Smoke-test it: `python3 overleaf.py --id <agent> init --proj probe --conf <id>`
   then `edit add --type <type> --content '{...}'` and `build`.
