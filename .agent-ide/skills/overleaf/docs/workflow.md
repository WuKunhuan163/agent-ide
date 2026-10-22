# Workflow

How to use this skill so that the document is never a `.tex` file you edit by
hand. The loop below is the intended maximum: every step reads or writes the
block tree, and the generated `.tex` is treated as disposable output.

## The loop

```
init → read the schema → edit one node → validate → build --no-compile → build → clean
```

1. **Bind a template first.** `init --conf <instance>` creates `project.json`
   and an empty `blocks/`. The instance decides which block types exist, which
   metadata keys are required, and how many sections the body may have. Changing
   venue later is a template change, not a rewrite.
2. **Read before writing.** `tree` for shape, `show-block --path <rel>` for the
   real fields of a sibling of the type you are about to add, and the catalog in
   `docs/blocks.md` for required versus optional fields. `CONTENT_INVALID` is
   almost always a guessed field name.
3. **One node per edit.** All writing goes through `edit`: `add`, `set`, `move`,
   `duplicate`, `delete`, `replace`, `meta`. Never rewrite a block file to change
   a sentence — address the field and set it.
4. **Validate while editing, not after.** `validate` reports template binding,
   missing required metadata, section overflow against `allowed_sections`,
   sibling `order` conflicts, and undefined `\cite` / `\ref` keys in one pass.
   `build` is gated on it, so an unvalidated build is wasted work.
5. **Render before compiling.** `build --no-compile` produces the `.tex` and the
   lint warnings; read them before paying for a compile. `build` then runs
   `tectonic` once and leaves the PDF plus its assets.
6. **Clean when handing off.** `clean` removes the products directory; a
   deliverable is the PDF, not a directory of intermediates.

## Draft without deleting

`--display false` hides a block and its whole subtree: it renders as nothing and
validation skips it, so half-written prose can sit in the tree and not block a
build. The one trap: a visible `\ref` pointing at a label defined only inside a
hidden block is `LABEL_UNDEFINED` — hidden means absent everywhere, including the
reference index.

## Figures and prose

Drawing rules and attachment are in `docs/figures.md`; sentence-level
conventions are in `docs/prose.md`. Both are about producing content that
survives a venue change; neither prescribes a layout for a specific journal.

## Project-wide values

Author block, affiliation, e-mail, grant numbers and similar text that appears
in several places goes into placeholders: `data/placeholders.json` for defaults,
`metadata.placeholders` for the project, overriding key by key. `build`
substitutes in every block content string and in the final `.tex`, so switching
submission version is one `edit meta`, not a search across blocks.

## A new venue

A template instance is a directory: `template.json` (required metadata, allowed
sections, block catalog), optional TeX assets, and optional `blocks/` overrides.
Resolution checks the instance first, then the shared groups in the fixed order
`text → media → math → refs`, so an instance only carries what differs from the
common case. An instance may name a `python` entry when document assembly itself
differs; both shipped instances do.

## Migrating an old project

A project written before the rewrite is a flat `metadata.json` plus
`root/<NN>_<type>/block.json` folders. It imports in one command:

```bash
python3 $O --id me migrate --from /path/to/old_project [--as <proj>]
```

- every metadata key except `template` is carried into `metadata` verbatim;
- the `NN_` prefix becomes `order` (NN × 10) and the rest of the folder name
  becomes the block id; duplicate ids under one parent get `_2`, `_3`;
- each block is written through the same path as `edit add`, so a field the
  manifest rejects is reported and skipped rather than written;
- a folder without `block.json` is skipped, and the warning counts the nested
  blocks it took with it;
- an existing project is refused (`PROJECT_EXISTS`), never overwritten.

Run `validate` afterwards: the old skill accepted some content the manifest does
not, and that is where it surfaces. Figure paths were stored as written, so any
image the old project kept outside the build directory or `input/` has to be put
there before it renders.

## What is generic, and what belongs to an instance

Generic — true regardless of paper or venue:

- the store invariants: fixed key list, block id is its directory name, unique
  sibling `order`, projections derived on every read and never stored;
- the plugin contract: `validate()` for checks the manifest cannot express,
  `render()` as the only required method, leaves and containers as declared;
- validation as a gate, with data errors, validation issues and compile errors
  kept as three distinct failure shapes;
- assets copied into the build and referenced by relative path — absolute and
  non-ASCII paths break the engine in a way that looks unrelated;
- one compile, deliverable-only output, an explicit `clean`;
- figures drawn in modules and measured, not eyeballed;
- prose that references labels instead of positions.

Instance-owned — expected to change:

- field sets and layout per venue (teaser band, page-one masthead, margin notes);
- `required_metadata` and `allowed_sections` values;
- fonts, sizes, and any typographic patch;
- the caption style a venue enforces.

## Recipes

A 2×3 full-width figure with subfigures:

```bash
python3 $O --id me edit add --proj paper --type figure --content '{
  "images": [{"path":"out/a.png"},{"path":"out/b.png"},{"path":"out/c.png"},
             {"path":"out/d.png"},{"path":"out/e.png"},{"path":"out/f.png"}],
  "columns": 3, "use_subfigures": true, "span_columns": true,
  "caption": "Overview of the pipeline.", "label": "fig:pipeline"}'
```

Rewrite one paragraph. The block path is the chain of block ids (`section` →
`text_3`), not `children`; a field below a block needs brackets because a slug
may contain a dot, and `--value` takes JSON, so a plain string is quoted twice:

```bash
python3 $O --id me edit set --proj paper \
  --at "section/intro/text_3['content']['text']" \
  --value '"Revised sentence."'
```

Park a draft section so it cannot block the build:

```bash
python3 $O --id me edit add --proj paper --type text --to section/intro \
  --display false --content '{"text":"TODO: ablation discussion"}'
```

Move a section to the end, and copy another one. An empty `--to` means the top
level — `--to $` is not a block address and is rejected:

```bash
python3 $O --id me edit move --at section/related --to "" --order 90
python3 $O --id me edit duplicate --at section/method --to "" --order 30
```

Switch the submission e-mail for the whole document:

```bash
python3 $O --id me edit meta --proj paper \
  --content '{"placeholders":{"email":"a@b.edu"}}'
```
