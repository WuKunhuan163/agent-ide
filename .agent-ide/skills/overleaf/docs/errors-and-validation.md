# Errors and validation

What the CLI prints when something is wrong, what each code means, and the order
to work through a broken build.

## Three failure shapes

| Shape | Example output | Exit |
|---|---|---|
| `DataError` | `Error: CONTENT_INVALID: path=section/text: field=content: missing required content field(s): text` | 1 |
| Validation issues | `[ { "code": "LABEL_UNDEFINED", "path": "section/text", "message": "undefined label 'fig1'" } ]` | 1 when non-empty |
| `CompileError` | `Error: tectonic failed: …` | 1 |

A `DataError` renders as `CODE`, then `path=` and `field=` when present, then the
detail — all joined by `: `. Nothing else is printed on stderr, and a traceback
means a bug in the skill rather than a problem in your project.

Work in this order: **`validate` → `build --no-compile` → `build`**. That
separates data problems from rendering problems from TeX problems.

## Error codes

Codes are a stable public contract (`src/store/errors.py`).

| Code | Raised when | What to do |
|---|---|---|
| `PROJECT_EXISTS` | `init` on an existing project directory | choose another `--proj`, or `delete-project` the old one |
| `PROJECT_NOT_FOUND` | no project directory, or no `project.json` in it | check `--id` and `--proj` |
| `TEMPLATE_NOT_FOUND` | instance directory or `template.json` missing; also a project bound to a template the manifest disagrees with | `list-templates` to see what exists |
| `TEMPLATE_VERSION_MISMATCH` | `project.json.template_version` differs from the instance's `version` | re-init the project, or update the recorded version deliberately |
| `BLOCK_NOT_FOUND` | a block address (`edit move` / `edit duplicate` / `edit delete` / `show-block`) names nothing; also a `block.json` file missing under a block directory | `tree` to see real `rel_path` values |
| `BLOCK_TYPE_UNKNOWN` | the type is absent from the bound manifest, or no plugin file provides it | see [`blocks.md`](blocks.md) |
| `CONTENT_INVALID` | missing required content field, unrecognised field, `content` not an object; `edit replace` with an empty `--old`; a `fri` `body_sections` entry that still uses `paragraphs[]` with no `content[]` (only reachable under `page_mode: full_report`) | compare with a working sibling via `show-block` |
| `CONTENT_ID_INVALID` | a `--at` selector is not a writable address: empty, has no steps, contains `[*]`/`..`, or names `$`, `$.metadata`, a whole block, a whole `content` or `type`; also an `--at` / `--to` outside the block tree (`edit move` / `edit duplicate` / `edit delete` need a block address) | address exactly one field; a field below a block needs brackets (`section/text['content']['text']`) |
| `CONTENT_PATH_NOT_FOUND` | a `--at` read selector matches nothing; a write addresses a missing **intermediate** node; a write index is out of range | `show-content` the parent selector to see the real ids and field names |
| `ORDER_CONFLICT` | two siblings share an `order` | pick a free integer; new blocks default to `max + 10` |
| `CHILD_NOT_ALLOWED` | the parent's `allowed_children` rejects the child type | move it, or use a container that accepts it |
| `LEAF_CANNOT_HAVE_CHILDREN` | a leaf block was given children — on write and again at render | delete the children or change the parent type |
| `PATH_UNSAFE` | absolute path, `..`, a segment named `block.json`/`project.json`, moving a block into itself, or an unsafe block id | use a plain forward-slash `rel_path` |
| `CITATION_UNDEFINED` | a `[N]` citation with no matching BibTeX entry (template hook); also a `validate` issue for `\cite` keys | fix the key or the `.bib` |
| `LABEL_UNDEFINED` | a `\ref` / `\eqref` / `\autoref` target no block defines | add the `label`, or fix the reference |
| `METADATA_INCOMPLETE` | a `required_metadata` key is missing from `project.json` | `edit meta --content '{"title":"…"}'` |
| `SECTION_LIMIT` | `body_sections` has more entries than `allowed_sections` permits | trim the sections or widen the gate |
| `MALFORMED_FILE` | invalid JSON, non-object top level, unknown key in `project.json`/`block.json`, wrong field type, a block directory without `block.json`, a `python` entry without `Template`, a plugin without `Block`, `\end{document}` missing from the rendered TeX, a tracked block missing from it, or `tectonic` absent during a compiling build | read the `path=` in the message — it names the offending file |
| `SCHEMA_UNSUPPORTED` | `schema` is not `1` | the project predates the current format; re-init it |
| `WRITE_FAILED` | the filesystem refused a block-directory rename (`edit move`) — permissions, read-only volume, disk full | fix the filesystem; nothing was written, so the tree is still consistent |

## What `validate` checks

`validate` never raises for data-level problems; it returns every issue it finds
and exits 1 when the list is non-empty.

| Check | Code |
|---|---|
| the project is bound to the manifest's template | `TEMPLATE_NOT_FOUND` |
| `template_version` matches the instance | `TEMPLATE_VERSION_MISMATCH` |
| every `required_metadata` key is present | `METADATA_INCOMPLETE` |
| `body_sections` fits inside `allowed_sections` (only when the gate is set) | `SECTION_LIMIT` |
| each **visible** block's `content` against its manifest entry | `CONTENT_INVALID` |
| sibling `order` values are unique — over the whole tree, hidden included | `ORDER_CONFLICT` |
| every `\cite` key resolves to a BibTeX entry — visible blocks only | `CITATION_UNDEFINED` |
| every `\ref`-family label is defined in a visible block | `LABEL_UNDEFINED` |

Citation and label scanning reads string fields, preferring `content.text`.

### `display: false` is invisible to the whole pipeline

Hiding a block is not only a rendering decision. The content check, the `\cite`
scan, the `\ref` scan and the citation/label index all walk the rendered view
(`Project.visible_blocks`), so a hidden subtree:

- **may hold draft or half-written content.** A hidden block missing its required
  fields is not an issue, and `build` proceeds — that is what makes hiding useful
  for focusing a build on one part of the document.
- **contributes no labels and no citation keys.** A visible `\ref` to a label that
  only a hidden block defines is therefore a genuine `LABEL_UNDEFINED`. That is
  intended: such a reference would dangle in the PDF, so it fails loudly instead
  of rendering as `??`.
- **is pruned as a whole subtree**, exactly like the renderer — hiding a section
  hides everything inside it.

Two checks deliberately still walk the **whole** tree, hidden included, and two
commands still see hidden blocks:

| Still sees hidden blocks | Why |
|---|---|
| sibling `order` uniqueness | `order` is a stored structural invariant; hiding must not mask a duplicate that resurfaces when the block is shown again |
| template binding + `required_metadata` | project-level, not per-block |
| `search` / `edit replace` | they edit stored content, not a rendering — you want to find and fix text wherever it lives |

`build` runs the same validation first and refuses to write anything if it finds
issues — it raises the **first** issue's code, with a detail naming how many were
found. So a red `validate` always means a red `build`; fix them there.

## Render-time checks

After assembly, the renderer asserts the document is whole:

- `\end{document}` must be present;
- every rendered block must still appear as `% [BEGIN_BLOCK: <id>]`.

Either failure is `MALFORMED_FILE` with no path. It means a `Template` assembled
the body in a way that lost blocks — see
[`templates.md`](templates.md) → *The two hard requirements*.

## Compile failures

`compile_tex` raises `CompileError` (printed as `Error: …`) for:

- `tectonic` exiting non-zero — the message carries tectonic's own output;
- `tectonic` not finishing within 300 seconds;
- BibTeX errors reported in that output;
- no PDF produced;
- a PDF smaller than 1024 bytes, which in practice means a blank or truncated
  document.

`tectonic` not being installed at all is different: `build` raises `MALFORMED_FILE`
telling you to use `--no-compile`. Use `--no-compile` to render TeX without TeX
installed, then compile elsewhere; `brew install tectonic` fixes it locally.

## Diagnostic loop

```bash
O=.agent-ide/skills/overleaf/overleaf.py
P=data/projects/<agent>/<proj>

python3 $O --id <agent> validate     --proj <proj>  # data-level truth
python3 $O --id <agent> show-project --proj <proj>  # template binding + metadata
python3 $O --id <agent> indexes      --proj <proj>  # citation keys / labels
python3 $O --id <agent> build        --proj <proj> --no-compile
```

Then read `$P/build/<proj>.tex`. It is the exact input tectonic saw, and the
`% [BEGIN_BLOCK: <id>]` markers show where each block landed. If the `.tex` is
correct but the PDF is not, the problem is in the instance's TeX, not in the
document data; the TeX error text arrives in the `CompileError` message, and the
`.tex` is left in place for re-running `tectonic` by hand.

`clean` deletes the entire `build/` directory, which is the fastest way to rule
out stale products.
