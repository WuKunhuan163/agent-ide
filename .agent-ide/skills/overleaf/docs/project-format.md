# Project format

The exact shape of a project on disk. This is the store layer's contract
(`src/store/codec.py`, `layout.py`, `disk.py`); the template layer never writes
any of it.

## Where projects live

```
<skill>/data/projects/<agent_id>/<project_id>/
├── project.json          # identity: template binding + metadata
├── blocks/               # the block tree
├── assets/               # project-owned images etc., copied into build/assets
├── references.bib        # optional; copied into build/ when present
└── build/                # products only, created on demand
```

The whole `data/` tree is gitignored. Projects are local runtime state: they are
never published with the skill and never travel between machines.

## The block tree

Block ids are directory slugs. Children live in a `blocks/` subdirectory **beside
their parent's `block.json`**, so the logical path `section/text` maps to
`blocks/section/blocks/text`:

```
blocks/
├── section/
│   ├── block.json
│   └── blocks/
│       ├── subsection/
│       │   ├── block.json
│       │   └── blocks/
│       │       └── text/block.json
│       └── text/block.json
└── text_2/block.json
```

A `rel_path` is the `/`-joined slug chain from the top level (`section/blocks` is
not a path — the `blocks` directory name never appears in a `rel_path`). The
empty string addresses the synthetic root. The root itself has no `block.json`.

- Every directory under `blocks/` **must** contain a `block.json`. One that does
  not is `MALFORMED_FILE` — the tree fails loudly rather than silently skipping
  the node.
- Removing a block that was the last child of its parent prunes the now-empty
  `blocks/` container directory.

## Slugs

`edit add` derives the directory name from the block type: characters outside
`[A-Za-z0-9._-]` become `_`, and collisions take a numeric suffix. Two `text`
blocks are therefore `text` and `text_2`. Slug allocation is the only source of
ids — nothing renames an existing block, so ids stay stable for the life of the
block.

There is deliberately **no `id` key in `block.json`**: a block's identity *is*
its directory name, and `rel_path` is derived from the path on every read. Adding
an explicit `id` does not work — the codec rejects the file outright with
`MALFORMED_FILE: unknown keys: id`, and even if the key were tolerated it would be
dropped on the next write, because both the loader and the dumper work from a
fixed key list. Identity can therefore never disagree with the tree, and there is
nothing to keep in sync.

`edit duplicate` re-allocates every slug in the copied subtree the same way, so
a clone never collides with its source. Labels inside the copied content are
copied verbatim and reported back, because two blocks sharing a `\label` is
something only you can resolve.

`edit move` re-allocates on collision too, and that is the one case where an
existing block is renamed: moving a top-level `text` into a `section` that already
has a `text` lands it as `section/text_2`, and the CLI reports the new `rel_path`.

## `order`

Siblings carry an integer `order` and are sorted by `(order, id)`.

- A new block without an explicit `--order` gets `max(sibling order) + 10`.
- **`order` must be unique among siblings.** A duplicate is `ORDER_CONFLICT`,
  both on write and during `validate`.
- `edit move` without `--order` appends to the destination's end.

Gaps are fine and expected; `10, 20, 30` leaves room to insert without touching
its neighbours.

## Content selectors

`show-content` reads, and `edit set --at` writes, a project addressed as **one JSON
document**, which is also how every `edit` verb is told which block it acts on
(`--at` for the block itself, `--to` for the parent it moves under):

```
$                                          # the whole project
$.metadata.title
$.blocks.section                           # a block: envelope + content + children
$.blocks.section.content.title
$.blocks.section.children.text_2
$.blocks.fig.content.images[0].width
```

The projection is derived on every call, never stored: a block appears as
`{id, type, order, display, content, children}` and `children` is a map keyed by
child slug — the same nesting `rel_path` describes, not the `blocks/` directories
on disk. `order` stays in each block, so the keyed map loses nothing.

The syntax is a stdlib-only JSONPath subset: `$`, `.name`, `['name']`, `[i]`
(negative counts from the end), `[*]`, `..name`, `..*`.

**Sugar for block paths.** A bare path is read as a block path, not as JSONPath:
`section/text` means `$.blocks.section.text`. A field below a block needs
brackets — `section/text['content']['text']` — because a dot is legal inside a
slug, so the block path cannot be split at `.`; the split is at `[`.

| Rule | Behaviour |
|---|---|
| a **read** may use `[*]` and `..` | returns every match, each with its canonical `content_id` |
| a **write** must name exactly one node | a wildcard or descent is `CONTENT_ID_INVALID` |
| `$`, `$.metadata`, a whole block, a whole `content` | not values: `CONTENT_ID_INVALID` — address a field inside |
| `type` | read-only |
| `order`, `display` | writable; `order` is guarded like `edit move` (`ORDER_CONFLICT` on a clash) |
| a content field | re-checked with `check_content`, so an unlisted field is `CONTENT_INVALID` here, not at render time |
| a **read** selector matching nothing | `CONTENT_PATH_NOT_FOUND`, never an empty result — a silent empty read would hide a typo |
| a **write** whose path is absent | a missing *intermediate* node is `CONTENT_PATH_NOT_FOUND`; the **last** segment is created — a new `metadata` key is fine (metadata is free-form), a new `content` field must be declared by the manifest or it is `CONTENT_INVALID` |

A write reports which channel it landed in (`metadata`, `content`, `envelope`)
and the block `rel_path` it touched, so exactly one file is rewritten.

## `project.json`

Exactly four keys. Any extra key is rejected.

| Key | Type | Notes |
|---|---|---|
| `schema` | int | must be `1`; anything else is `SCHEMA_UNSUPPORTED` |
| `template` | non-empty string | the instance id this project is bound to |
| `template_version` | positive int | must match the instance's `version`, else `TEMPLATE_VERSION_MISMATCH` |
| `metadata` | object | free-form, read by the instance's `Template` |

```json
{
  "schema": 1,
  "template": "cvpr",
  "template_version": 1,
  "metadata": {
    "title": "My Paper",
    "authors": [{ "name": "Author", "institution": "Inst", "email": "e@mail.com" }],
    "abstract": "Abstract."
  }
}
```

`metadata` is where title, authors, abstract and the optional `placeholders` /
`allowed_sections` / `body_sections` keys live. `init` seeds it from the
instance's `default_metadata`; `edit meta` merges into it and `show-project`
reads it back.

## `block.json`

Exactly five keys. Any extra key is rejected.

| Key | Type | Notes |
|---|---|---|
| `schema` | int | must be `1` |
| `type` | non-empty string | must exist in the bound template's manifest |
| `order` | int | unique among siblings; `true`/`false` is not an int |
| `display` | bool | the block's visibility switch; `false` renders nothing (subtree included) but keeps the block. Set with `edit add --display` / `edit set --at <block>.display`. A `display` inside `content` has no effect at block level. Hidden subtrees are skipped by content validation and by the citation/label index too, so `false` really means "as if it did not exist" |
| `content` | object | validated against the manifest entry for `type` |

```json
{
  "schema": 1,
  "type": "text",
  "order": 10,
  "display": true,
  "content": { "text": "Body." }
}
```

`content` is checked against the manifest by `check_content`: missing required
fields and unrecognised fields are both `CONTENT_INVALID`. See
[`blocks.md`](blocks.md) for the per-type fields.

## Strictness and atomicity

- The codec is the **only** place JSON is read or written.
- No defaults are inferred for required fields, and no unknown key is tolerated:
  an extra key (a hand-added `id`, say) is a hard `MALFORMED_FILE` on read, not a
  warning. The same fixed key list drives writing, so a field the codec does not
  know is dropped by the next write. Editing these files by hand is therefore
  either rejected or ignored — go through the CLI.
- `content` must be an object even when a type declares no fields.
- `schema` is the only version gate: it must equal `1`, anything else is
  `SCHEMA_UNSUPPORTED`. A future format change ships a new schema number plus a
  migration; nothing existing is ever silently reinterpreted.
- Writes go to a temporary file and are then `os.replace`d into position, so a
  crash cannot leave a half-written `block.json`.
- JSON is written with 2-space indent, `ensure_ascii=false`, and a trailing
  newline — diffs stay readable and non-ASCII content stays literal.

Failures are raised as `DataError` with a stable code; see
[`errors-and-validation.md`](errors-and-validation.md).

## Path safety

`normalize_rel_path` is applied to every `--path` and to the block path a selector
sugar resolves to (`--at` / `--to`) before use. It
rejects absolute paths, `..` traversal, and any segment named `block.json` or
`project.json` — all as `PATH_UNSAFE`. Paths are POSIX-style and
forward-slash separated; backslashes are normalized to `/`.

## Products vs state

`build/` holds generated output only: the `.tex`, the PDF, the copied instance
assets, `assets/`, and `references.bib`. It is recreated on demand by `build` and
removed wholesale by `clean`. Nothing in `build/` is ever read back as project
state — deleting it loses no work.
