---
name: arxiv
description: >-
  arXiv search plus the repo's PDF download engine. `download` consumes any result
  JSON carrying a pdf url — openalex `pdf_url`, arxiv `pdf_link`, any OA host — and
  writes verified PDFs to disk. Use it whenever a search result must become a local
  file for pdf_reader.
---

# arxiv

Two jobs: searching arXiv preprints, and turning a PDF from any search result into a local file. The second is what the pipeline mostly uses it for.

## Core commands

**The commands are one line each and print JSON, so the next step can consume them**: the block below is the whole surface.

```bash
# search (arXiv source by default)
.agent-tools/arxiv <options> "query string"

# search OpenAlex (cross-disciplinary, with citation counts and OA links), download immediately
.agent-tools/arxiv --source openalex --in title_abstract --year_from 2023 \
    --max_results 100 --download --out papers/ "3D Gaussian Splatting"

# download later from any result JSON carrying a pdf url
.agent-tools/arxiv download --from <result.json> [--out DIR] [--limit N] [--dry-run] \
    [--delay 1.2] [--retries 3]
```

Both sources share one CLI and one field set (`title/year/authors/pdf_link/citations/abstract/doi/venue`), and `--download` / `download --from` treat them identically. They differ only on the search side:

| | `--source arxiv` (default) | `--source openalex` |
|---|---|---|
| Coverage | arXiv preprints | cross-disciplinary: journals, conferences, preprints |
| Default sort | `submittedDate` | `relevance` (`--sort_by` overrides) |
| Per-call limit | paginated, bounded by `--max_eval` | 200 records, no pagination |
| Exclusive filters | `--min_citations` / `--min_upvotes` / `--abstract_contains` | `--year_from` / `--year_to` / `--in` |
| Extra fields | `hf_upvotes` | `openalex_id`, citations come from OpenAlex |

`--from` accepts this skill's own result snapshots and any JSON holding `pdf_url` or `pdf_link`; the host need not be arxiv.org — AAAI OJS, PLOS and institutional repositories are handled the same way.

## Search semantics and limits (`--source arxiv`)

- The query is split on whitespace, each term encoded as `all:<term>` and joined with `+AND+`; `and` / `or` / `not` are dropped, so `A AND B` is the same as `A B`.
- No field qualifiers: `ti:gaussian` is sent as `all:ti:gaussian`, the API answers HTTP 400, the whole search returns empty, and there is no fallback.
- No quoted phrases; an over-long query or special characters likewise tend to produce 400.
- `--min_citations` reads the count from the first Crossref `query.bibliographic` hit without checking title similarity, so it can take another paper's count; preprints usually score 0. Use `--source openalex` when the count matters.
- Enrichment costs a fixed amount: even with `--min_upvotes` and `--min_citations` both 0, each record still costs two serial requests (HuggingFace + Crossref).
- Pagination is 10 per page, the evaluation ceiling is `--max_eval` (default 100), and pages are spaced by `--delay` (default 3.0 s); `--exclude-cache` prints `[cached]` and skips on a cache hit in `data/fetch/cache.json`.

## Download rules (baked into the code)

- A browser User-Agent (hosts such as AAAI OJS drop the default python UA).
- The first bytes must be `%PDF`, otherwise the file is deleted rather than written (failures often return 200 with HTML).
- Write `.part` first, rename atomically after the check passes; resume when the host supports `Range`.
- Skip if the target file already exists, so the command is repeatable.
- 4xx counts as skipped; connection errors and 5xx are retried `--retries` times (default 3) then counted as failed, and any failure makes the exit code 1.

Options and examples: [skills/01_usage.md](skills/01_usage.md).

## Neighbouring skills

**Three neighbouring skills do overlapping work deliberately; the table says which one owns what** so a lookup does not happen twice.

| Skill | Division of labour |
|---|---|
| `crossref` | authoritative metadata and journal-scoped search for a known DOI/ISSN; metadata only, never downloads |
| `pdf-reader` | PDF or URL → text; its input is a file this skill downloaded |
| `overleaf` | block tree → LaTeX → PDF |
