# Template instances

How to read an existing instance and how to add a new one. An instance is a
journal or conference layout: which block types exist, how content flows into
TeX, and which assets ride along.

## What an instance is

```
src/template/instances/<id>/
├── template.json      # the manifest: block types + assembly configuration
├── preamble.py        # optional; `python` entry naming a `Template` class
├── <journal>.sty      # / .cls / .bst  — copied into the build dir
├── assets/            # fonts and images, copied into build/assets
├── thumbnails/        # second asset dir, copied into build/thumbnails
└── blocks/            # per-instance block overrides (see blocks.md)
```

Instances are shared code: they travel with the skill via `skill.json` →
`directories: ["src"]`. They must never read or write a project directly —
everything an instance needs arrives through the renderer's `state`, and anything
it produces goes into the build directory.

`list_instances` reports every directory under `instances/` that has a
`template.json`.

## `template.json`

| Key | Type | Read by | Meaning |
|---|---|---|---|
| `name` | string | `manifest_for` | instance id. Defaults to the directory name |
| `version` | int | store + render | bound into `project.json`; a mismatch is `TEMPLATE_VERSION_MISMATCH` |
| `description` | string | — | human text only, ignored by code |
| `python` | string | `load_instance` | optional module that must define `Template`; when present it replaces the declarative assembly |
| `required_metadata` | list | `validate` | metadata keys a project must set, else `METADATA_INCOMPLETE` |
| `abstract_environment` | bool | `BaseTemplate` | declarative path only: wrap `metadata.abstract` in an `abstract` environment (default `true`). `cvpr` sets it but overrides `build_document` without calling `super()`, so on `cvpr` the key is **inert** — its own code emits the abstract |
| `preamble_header` | list of str | `BaseTemplate` | declarative preamble lines, before `\begin{document}` |
| `assets` | list of str | `copy_instance_assets` | which subdirectories of the instance are copied into the build dir (default `["assets", "thumbnails"]`) |
| `default_metadata` | object | `BaseTemplate` | seed returned by `default_metadata()`, written by `init` |
| `blocks` | object | store manifest | per-type `required` / `optional` / `leaf` / `container` / `allowed_children` — see [`blocks.md`](blocks.md). `required_metadata` is a **top-level** key (above), never a per-type one |

One naming subtlety worth knowing: `template.json` spells the id `name`, while the
store manifest spells it `template`. `registry.manifest_for` performs that
translation; nothing else should re-derive it.

## The declarative path

With no `python` key, `BaseTemplate` assembles the document:

1. `render_preamble` joins `preamble_header` verbatim.
2. `build_document` emits that preamble, `\begin{document}`, `\begin{abstract}`
   + `metadata.abstract` + `\end{abstract}` when `abstract_environment` allows,
   then the rendered body, then `\end{document}`.

Hooks an instance may override:

| Hook | Purpose |
|---|---|
| `validate_state(state)` | raise `DataError` when required metadata is missing |
| `default_metadata()` | seed written by `init` |
| `validate_bibliography_citations(state)` | cross-check `[N]` citations against BibTeX entries. Runs only if the instance also implements **both** `parse_bibliography_entries(project_dir)` and `iter_citable_texts(meta)` |

The declarative path has no notion of title, authors or a masthead, which is why
the two shipped instances both take the python path.

## The python path

`"python": "preamble.py"` makes `registry._load_python_template` import that file
by absolute path, require a `Template` class, and instantiate it as
`Template(instance_dir, spec)` — it must subclass `BaseTemplate`, whose `__init__`
stores `template_dir`, `spec`, `name`, `version` and `required_metadata`.

`Template` is loaded by absolute path, so its imports must be absolute package
imports (`from src.template...`, `from src.store...`). Instance directories are
not added to `sys.path`.

It must provide:

| Method | Contract |
|---|---|
| `render_preamble(state) -> str` | everything before `\begin{document}` |
| `build_document(state) -> str` | the complete `.tex` |

`state` is:

| Key | Value |
|---|---|
| `metadata` | `project.json` metadata, verbatim |
| `rendered_content` | the body: every block's TeX, each wrapped in `% [BEGIN_BLOCK: <id>]` / `% [END_BLOCK: <id>]` markers |
| `block_types` | `{block_id: type}` for every rendered block |
| `project_dir` | project root |
| `output_dir` | build dir |

### The two hard requirements on `build_document`

After assembly the renderer checks the result and raises `MALFORMED_FILE`
otherwise:

1. it must contain `\end{document}`;
2. every tracked block's `% [BEGIN_BLOCK: <id>]` marker must still be present.

That is the safety net that catches a `Template` which silently drops part of the
body. If your assembly rewrites or reflows the body (both shipped instances do —
`fri` re-parses it, `cvpr` lifts the teaser band out of it), it must preserve
those markers.

## Metadata contract

`required_metadata` is the machine-checked part; instances may read more.

| Instance | `required_metadata` | Also reads |
|---|---|---|
| `cvpr` | `title`, `authors`, `abstract` | `authors[].name`, `.institution`, `.email`, `.website` |
| `fri` | *(none)* | journal name, volume, ISSN, publisher, article type, DOI/license URLs, received/revised/accepted/available dates, copyright holder/year, affiliations, authors, keywords, introduction, body sections, figures, tables, back matter, visibility, page mode, figure scale, `include_bibliography` |

Two optional metadata keys are read by the store rather than by an instance:

- `placeholders` — string substitutions applied at build time.
- `allowed_sections` / `body_sections` — an optional chapter gate: when
  `allowed_sections` is a list, `body_sections` may not have more entries than it,
  else `SECTION_LIMIT`.

`fri` is a hybrid: it renders part of the document from these metadata keys,
not only from the block tree. Treat `instances/fri/preamble.py` as the authority
for their exact shape.

## Assets and the build directory

`render.prepare_build_dir` is the single place that decides what a build
directory contains. In order:

1. the project's `assets/` is copied to `build/assets/`;
2. the instance's `.sty` / `.cls` / `.bst` files, plus the directories named by
   its `assets` key, are copied in — skipping `blocks/` and `__pycache__`;
3. the project's `references.bib` is copied in.

Rendering then adds whatever the block plugins write: figure images into
`build/assets/`, and a `bibliography` block's `references.bib`.

Consequences worth remembering:

- Instance `assets/` are merged into `build/assets/` **after** the project's, so
  an instance file with the same name wins.
- `references.bib` has two possible sources: the project root file, and a
  `bibliography` block's `bibtex`. Step 4 runs after rendering, so the project
  file wins when both exist.
- Everything under `build/` is disposable. `clean` deletes it; the next `build`
  recreates it.

## What `build` does, in order

1. reads the project tree once, and parses each `template.json` once — the
   parsed spec is cached per instance, keyed by the file's mtime;
2. builds the citation/label index **once** and validates the project with it;
3. renders the tree into TeX, reusing that same index;
4. writes `<project_id>.tex`;
5. lints it — **read-only**. A linter that rewrites the document makes the
   generated `.tex` stop being what your template produced;
6. runs `tectonic` once with `cwd=<build dir>` (never `os.chdir`, which would
   mutate process-global state) under a 300-second timeout, then keeps the PDF
   and drops the LaTeX/BibTeX intermediates.

## Versioning

`project.json.template_version` is written by `init` from the instance's
`version`, and re-checked on every render and every `validate`. Bump `version`
when a change makes existing projects render differently — that turns silent
layout drift into explicit `TEMPLATE_VERSION_MISMATCH` issues you can go fix.

## Adding an instance

1. `mkdir src/template/instances/<id>`, and keep the convention of a one-line
   `__init__.py` marker beside `template.json`. Python does not require it —
   sibling imports such as `from src.template.instances.<id>.layout import …`
   resolve as namespace packages without it — but every existing instance and
   block group carries one.
2. Drop the publisher's `.sty` / `.cls` / `.bst` and any fonts/images into the
   instance directory, with asset subdirectories named in `assets`.
3. Write `template.json`: `name`, `version: 1`, `required_metadata`, the full
   `blocks` map, and `default_metadata`.
4. Add `preamble.py` with `class Template(BaseTemplate)` implementing
   `render_preamble` and `build_document`. Use `cvpr` as the minimal example and
   `fri` as the full one.
5. Register the block types your `blocks` map names: `blocks.md` → *Adding a block
   plugin*. A type in the map with no plugin file is `BLOCK_TYPE_UNKNOWN` at
   render time.
6. Verify end to end:
   ```bash
   O=.agent-ide/skills/overleaf/overleaf.py
   python3 $O --id probe list-templates          # <id> must appear
   python3 $O --id probe init --proj t --conf <id>
   python3 $O --id probe validate --proj t
   python3 $O --id probe build --proj t
   ```
7. Read the generated `.tex` in `build/` at least once. Compilation success only
   proves TeX ran, not that your assembly placed the blocks where you intended.
