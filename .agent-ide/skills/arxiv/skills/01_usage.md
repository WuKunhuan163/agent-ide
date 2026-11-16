# arxiv — CLI usage

## Hard rule

Once the search command returns, parse the result and continue into downstream tools (Write, Shell, …) **in the same turn**. Do not end the turn on the search alone.

## Install

**One install line, no configuration**: the tool is keyless and needs no account for anything below.

```bash
python3 .agent-ide/skills/agent-ide/agent-ide.py install --project . arxiv
```

## Commands

**Every command is one line and prints JSON unless told otherwise**, which is what lets the next step consume it directly.

```bash
.agent-tools/arxiv <options> "query string"
.agent-tools/arxiv download --from <result.json> [--out DIR] [--limit N] [--delay S] [--dry-run]
```

### Options

* `query`: space-separated keywords, implicitly AND. Do not write literal `AND`/`OR`/`NOT`.
* `--max_results`, `-m`: upper bound on papers shown.
* `--sort_by`, `-s`: `relevance` | `submittedDate` | `lastUpdatedDate` (unset: `submittedDate` for arxiv, `relevance` for openalex; openalex has no last-updated order and falls back to relevance).
* `--min_citations`: minimum Crossref citation count.
* `--min_upvotes`: minimum Hugging Face Daily Papers upvotes.
* `--abstract_contains`: keyword the abstract must contain.
* `--max_eval`: cap on papers evaluated (default 100).
* `--delay`: seconds between paged requests.
* `--exclude-cache`: skip papers already in cache.json.
* `--source arxiv|openalex`: which index (default `arxiv`). openalex is cross-disciplinary and carries citation counts and OA links.
* `--year_from` / `--year_to`: year filter, openalex only.
* `--in fulltext|title_abstract`: search scope, openalex only; `title_abstract` is far less noisy.
* `--download`: download the PDFs of what matched.
* `--out`: destination for `--download`, default `data/fetch/pdfs/`.

### Query syntax (arxiv source)

**The query syntax looks like a search box and is not one**: the table shows what the tool actually does with each form you type.

| You write | What actually happens |
|---|---|
| `health claim` | `all:health +AND+ all:claim` — matches title, abstract, full text and authors |
| `health AND claim` | same as above; the `AND` is dropped |
| `ti:gaussian` | **HTTP 400** — `ti:gaussian` is treated as one ordinary word |
| `"3D Gaussian Splatting"` | quotes do nothing; it becomes three words ANDed |

No field prefixes (`ti:`/`au:`/`abs:`), no phrases, no OR. A 400 is not degraded — it returns empty.

### Filter chain and what it costs

Each paper passes, in order: local `--abstract_contains` → HuggingFace upvotes → Crossref citations. The last two **always issue a request**, even at a threshold of 0, because the value is displayed:

- 2 external requests per paper, serial; measured 6.2 s for 3 papers (`--delay 0.5`), roughly 170 s for 100.
- The citation count comes from the first row of `rows=1` and **the title is not verified** — measured 2 of 3 wrong; preprints are usually 0. `--min_citations` kills on a wrong number; do not use it as a hard gate.
- For a trustworthy count, use `--source openalex` (OpenAlex's own count).

### Examples

**The examples run as written, and each one names the file it lands in** — copy one and change the topic, not the shape.

```bash
.agent-tools/arxiv --max_results 3 "controllable neural scene generation"
.agent-tools/arxiv --max_results 5 --sort_by relevance --exclude-cache "neural rendering score distillation"
.agent-tools/arxiv --max_results 3 --min_upvotes 50 --abstract_contains "keyword" "Example Topic"
.agent-tools/arxiv --max_results 5 --delay 1.0 "NeRF reconstruction"

# openalex source: cross-disciplinary, ordered by citations/relevance, written to disk on the way out
.agent-tools/arxiv --source openalex --in title_abstract --year_from 2023 --max_results 50 --download --out papers/ "3D Gaussian Splatting"
```

## Download

**Download consumes a result JSON, not a topic**: it takes the `pdf` url out of a search result and writes a verified file, so the search has to come first.

```bash
# consume this skill's own search snapshot (openalex and arxiv share the format)
.agent-tools/arxiv download --from .agent-ide/skills/arxiv/data/fetch/results/<ts>_<hash>.json --out papers/

# see what would be fetched before fetching
.agent-tools/arxiv download --from results.json --dry-run

# first 10 only, 1.2 s apart (the default)
.agent-tools/arxiv download --from results.json --limit 10 --delay 1.2
```

| Option | Effect |
|---|---|
| `--from` | result JSON: this skill's `pdf_link`, or `pdf_url`/`link` from an older snapshot |
| `--out` | destination directory, default `data/fetch/pdfs/` |
| `--limit` | fetch only the first N |
| `--delay` | seconds between requests, default 1.2; keep arXiv at 1 s or more |
| `--retries` | retries on connection error / 5xx, default 3 |
| `--dry-run` | print the URLs, fetch nothing |

Behaviour:

- Filename = `title slug + first 8 hex of the URL hash`, stable per URL; an existing file is skipped, so re-running is safe.
- Writes `<name>.pdf.part` first; only after the leading 4 bytes check out as `%PDF` is it renamed atomically. Anything else is deleted and counted as a failure.
- Some hosts drop the default `python-requests` UA, so a browser UA is always sent; the same applies at AAAI/PLOS and institutional repositories.
- Hosts that honour `Range` (arXiv: `206`) resume a partial file; others re-download the whole thing.
- 4xx → skipped; connection errors and 5xx → failed after retries. Exit code 1 when anything failed.
