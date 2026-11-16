---
name: crossref
description: >-
  Crossref metadata for known identifiers — a DOI or an ISSN. Returns authoritative
  records, license/CC status, and journal-scoped search. Not a topic search engine: for
  "find papers about X", use arxiv --source openalex. Keyless and bot-friendly.
---

# crossref

Crossref is the metadata registry for DOI-issuing bodies and works only on **known identifiers**: give it a DOI or an ISSN and it returns the authoritative record. It does not find papers by topic.

## Invocation

Top-level options come **before** the subcommand; argparse rejects them afterwards:

```bash
.agent-tools/crossref --id <id> [--mailto <email>] <subcommand> ...
```

| Subcommand | Purpose |
|---|---|
| `search-issn <ISSN> "<term>" [--rows] [--from-year] [--sort]` | search inside one journal — the only entry that scopes to a single journal |
| `search "<term>" [--rows] [--from-year]` | whole-registry search, no relevance ranking, unsuitable for topic discovery |
| `work <DOI>` | authoritative DOI metadata |
| `journal <ISSN>` | journal profile |

Shared options: `--rows` (default 10), `--from-year`, `--budget-seconds` (default 120), `--max-retries` (default 3), `--sort` (`search-issn` only: `relevance|score|published`, unset means the API default). `--mailto` joins the polite pool and can be faster; it defaults to the `CROSSREF_MAILTO` environment variable. No key required.

Result JSON is written to `.agent-ide/skills/crossref/data/results/<id>/<timestamp>_<command>_<hash>.json`.

## Output

Results go to stdout only, `tab`-separated, with no colour, prefix or rule lines; match counts, warnings and failure reasons go to stderr.

`search-issn` prints one paper per line, in a fixed column order:

```
title → year → cited → doi → journal
```

So `| cut -f4` takes the DOI and `| cut -f2` sorts by year. The total is on stderr (`[crossref] <N> matches in ISSN <ISSN>`).

`work` prints `key<TAB>value`, one item per line, with missing values written as `-`:

```
title / year / journal / volume / pages / doi / type / cited / license / license_url / authors / abstract
```

`journal` fields: `name / issn / publisher / subject`.

## Field meanings

- `license` / `license_url`: `License: None` only means Crossref has no registered open licence; it does not mean closed access. Whether the full text may be reused depends on the OA side having a full-text link.
- `abstract`: publisher-dependent; within one batch some records have it and others are always `-`. Never assume it exists.
- `cited`: Crossref's count, which differs from OpenAlex's — normalise before comparing across sources.
- `subject`: often empty; do not rely on it for discipline judgements.

## Fast failure

- When `--budget-seconds` runs out, retries stop and `[QUICK-FAIL]` is printed. Do not keep retrying one search.
- The tool produces metadata only; it never downloads full text. Full text is `arxiv download`'s job.
- Detail: [skills/01_quick_fail_discipline.md](skills/01_quick_fail_discipline.md).

## Scope

**This tool answers identifier questions and nothing else**: the table says what is in scope, so a topic search does not end up here.

| Aspect | Note |
|---|---|
| Fits | any journal, book or proceedings with a DOI |
| Strengths | exact filtering by ISSN; no key; returns title/authors/year/DOI/volume-pages/licence |
| Limits | abstracts are publisher-dependent; covers only DOI-registered publications; no full text |
| Does not fit | topic discovery, finding an OA copy, CS venue lookups → `arxiv --source openalex` |

## Install

**No key, no account, one install line** — that is the whole setup, and there is nothing to configure per project.

```bash
python3 .agent-ide/skills/agent-ide/agent-ide.py install --project . crossref
```

## Neighbouring skills

**Three neighbouring skills do the searching; this one resolves what they find**, and the split is deliberate: mixing them duplicates the lookup.

| Skill | Division of labour |
|---|---|
| `arxiv` | topic search (arXiv + OpenAlex) and PDF download |
| `pdf-reader` | PDF or URL → text |
| `overleaf` | block tree → LaTeX → PDF |
