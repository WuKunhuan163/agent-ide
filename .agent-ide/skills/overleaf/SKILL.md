---
name: overleaf
description: Compile LaTeX documents from a block tree with template instances, automatic linting and single-pass tectonic builds.
---

# Overleaf

Use this skill when the user wants a LaTeX report, paper, or `.tex` produced or edited — instead of running `pdflatex` by hand.

The document is a **block tree on disk**, not a `.tex` file you hand-write. You edit blocks through the CLI; `build` renders them to TeX and compiles that with `tectonic`.

## Quickstart

```bash
cd <project root>
O=.agent-ide/skills/overleaf/overleaf.py

python3 $O --id <agent> list-templates                          # pick an instance: cvpr | fri
python3 $O --id <agent> init --proj <proj> --conf cvpr
python3 $O --id <agent> edit add --proj <proj> --type section --content '{"title":"Introduction"}'
python3 $O --id <agent> edit add --proj <proj> --type text --to section --content '{"text":"Body."}'
python3 $O --id <agent> validate --proj <proj>                  # exit 1 when issues exist
python3 $O --id <agent> build --proj <proj>                     # -> data/projects/<agent>/<proj>/build/<proj>.pdf
```

`--id` is required on every command. `--proj` is required on every command except `list-templates`.

## CLI

**Every change to a document goes through one command, `edit`.** One verb is one kind of change, and there is no other way to write:

| `edit` verb | Effect |
|---|---|
| `add --type <t> [--to <parent>] [--order <n>] [--display true\|false] (--content\|--content-file)` | create a block |
| `set --at <selector> (--value\|--value-file)` | set the one node a selector names |
| `move --at <selector> [--to <parent>] [--order <n>]` | reparent and/or reorder |
| `duplicate --at <selector> [--to <parent>] [--order <n>]` | deep-copy a subtree under a new parent |
| `delete --at <selector>` | remove a block and its whole subtree |
| `replace --old <text> [--new <text>]` | replace literal text across every block |
| `meta (--content\|--content-file)` | merge keys into `project.json` metadata |

Reads are one verb each and never write:

| Read | Purpose |
|---|---|
| `list-templates` | available instance ids |
| `tree` | block tree, content included |
| `show-project` | template binding and full `metadata` |
| `show-block --path <rel>` | one block, by block path |
| `show-content --at <selector>` | any single node, by content selector |
| `indexes` | citation keys and labels collected from the rendered tree |
| `validate` | project-level issues; exits 1 when any are found |
| `search --query` | blocks whose content contains the query |

`init`, `migrate`, `delete-project`, `build` and `clean` act on a project's lifecycle or its products, not on its document, so they sit outside `edit`. `migrate --from <dir> [--as <proj>]` imports a project written by the pre-rewrite layout.

## Addressing

Every `edit` verb is told **which block** it acts on by a content selector: `--at` for the block itself, `--to` for the parent it lands under (`--to` omitted or empty means the top level). A project is addressable as **one JSON document**:

```
$                                          # the whole project
$.metadata.title
$.blocks.section                           # a block: envelope + content + children
$.blocks.section.content.title
$.blocks.section.children.text_2
$.blocks.fig.content.images[0].width
```

The projection is derived on every call, never stored: a block appears as `{id, type, order, display, content, children}` and `children` is a map keyed by child slug — the same nesting the block path describes, not the `blocks/` directories on disk.

**Sugar for block paths.** A bare path is read as a block path, not as JSONPath: `section/text` means `$.blocks.section.text`. So `edit duplicate --at section/text --to fig` and `edit duplicate --at src/section/text` say the same thing at any depth. A field below a block needs brackets — `section/text['content']['text']` — because a dot is legal inside a slug, so the block path cannot be split at `.`; the split is at `[`.

The syntax is a stdlib-only JSONPath subset: `$`, `.name`, `['name']`, `[i]` (negative counts from the end), `[*]`, `..name`, `..*`. A **read** may use `[*]` and `..`; a **write** must name exactly one node. A read that matches nothing is `CONTENT_PATH_NOT_FOUND` — never an empty result, which would hide a typo. A write creates its final segment: a new `metadata` key is fine, a new `content` field has to be declared by the manifest (`CONTENT_INVALID` otherwise), and a missing intermediate node is `CONTENT_PATH_NOT_FOUND`.

`--content` takes a JSON object, `--content -` reads it from stdin, and `--content-file <path>` (or `-`) reads it from a file. `--value` / `--value-file` follow the same three forms but accept JSON of **any type**, so a `set` can write a string, a number, a list or a whole object. Use these instead of fighting shell backslash escaping on LaTeX-heavy text.

## Rules that will bite

1. **`content` is validated against the template manifest.** A missing required field or an unrecognised field is `CONTENT_INVALID`, both when you write a block (`edit add`, `edit set` on a `content` field) and when `build` renders it. Run `show-block` on a sibling of the type you want if you are unsure of the field names — never invent one.
2. **Nesting is gated.** A `leaf` type cannot receive children, and a container only accepts the types listed in its `allowed_children`. Violations are `LEAF_CANNOT_HAVE_CHILDREN` / `CHILD_NOT_ALLOWED`.
3. **Sibling `order` values must be unique.** New blocks get `max(order) + 10`; a collision is `ORDER_CONFLICT`. `edit move` into a parent that already holds the block's name re-allocates the slug (`text` lands as `text_2`), which is the only case where an existing block is renamed — the CLI reports the `rel_path` it ended up at, so trust that output.
4. **`--display false` hides a block without deleting it.** It renders as nothing (subtree included) but stays in the tree. This top-level flag is the only hide switch a block has: a `display` inside `content` changes nothing even where the manifest lists it (see `docs/blocks.md`). Hidden is hidden everywhere — validation and the citation/label index skip hidden subtrees, so draft content may sit there without blocking `build`; the flip side is that a visible `\ref` to a label only a hidden block defines becomes `LABEL_UNDEFINED`.
5. **Block ids are directory slugs**, not titles: two `text` blocks are `text` and `text_2`. A block's path is its chain of ids from the top level (`section/text`) — that is what the selector sugar takes, and what `tree`, `search`, `validate` and `edit replace` print back.
6. **`type` is read-only and identity is the directory name.** `block.json` has no `id` key: adding one by hand is `MALFORMED_FILE`, and the loader and the dumper share one fixed key list, so a field the codec does not know cannot survive a write. Edit through the CLI (see `docs/project-format.md`).

## Templates

| Instance | Shape |
|---|---|
| `cvpr` | IEEE/CVF proceedings, two-column, title/authors/abstract from metadata, `teaser` block |
| `fri` | Cell Press single-column article, `journal_header` block for the page-1 masthead |

An instance is `src/template/instances/<id>/`: a `template.json` manifest, optional assets (`.sty`, `.cls`, `.bst`, fonts, images) and optional `blocks/` overrides. `template.json` may name a `python` entry whose `Template` class takes over document assembly; both shipped instances do.

## Block resolution

`instances/<id>/blocks/<type>.py` wins; otherwise the shared groups under `src/template/blocks/` are scanned in the fixed order `text` → `media` → `math` → `refs`. A miss is `BLOCK_TYPE_UNKNOWN`.

Every block plugin defines `class Block(BaseBlock)` and imports `from src.template.block_base import BaseBlock`. Instance and block modules are loaded by absolute path, so **all their imports must be absolute package imports** (`from src.template...` / `from src.store...`); instance directories are deliberately not added to `sys.path`.

## Placeholders

`build` substitutes placeholders in every block content string and in the final `.tex`. A global `data/placeholders.json` (create it if you want one) supplies defaults; the project's `metadata.placeholders` overrides them key by key. Both are optional — with neither, block content is emitted verbatim.

## Compile

`build` is gated on validation: if the project has any issue, it raises that issue's code instead of writing anything. Run `validate` while editing, and `build` once it is clean.

It then runs `tectonic` once on the generated `.tex` inside `data/projects/<agent>/<proj>/build/`, keeps only the PDF, and prints the `.tex`, the rendered block ids, warnings and the PDF path as JSON. If `tectonic` is absent, `build --no-compile` still renders TeX and says so; install it with `brew install tectonic`.

## Architecture

Two layers under `src/`, with a one-way dependency:

| Layer | Path | Owns |
|---|---|---|
| Store | `src/store/` | On-disk project format, block tree, content validation, citation/label indexes |
| Template | `src/template/` | Instances, block plugins, TeX assembly, lint, tectonic compile |

`src/build.py` is the only module that calls both. Store never renders TeX; template never writes project state.

## Where to look next

| Question | Doc |
|---|---|
| What exactly lives in `project.json` / `block.json`? | `docs/project-format.md` |
| Which block types exist, and what fields do they take? | `docs/blocks.md` |
| How do I add a new template instance? | `docs/templates.md` |
| An error code appeared, or the build failed — now what? | `docs/errors-and-validation.md` |
| What does the intended full workflow look like? | `docs/workflow.md` |
| I need to draw a composite figure and attach it | `docs/figures.md` |
| How should the prose itself be written | `docs/prose.md` |
