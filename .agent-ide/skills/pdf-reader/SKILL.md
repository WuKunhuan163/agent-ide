---
name: pdf-reader
description: >-
  Read a PDF, or a URL pointing at one, into text that can be worked with — markdown,
  the block structure behind it, and the figures it contains — through the MinerU
  endpoint. Read this skill whenever a paper, report or slide deck has to become text,
  when a URL should be parsed without being downloaded first, when a document is larger
  than the endpoint's page limit, or when an earlier read stopped early and has to be
  finished, **and whenever a draft is about to cite a paper (\cite, a Related Work paragraph, "X shows that…")**. This is the only sanctioned way to turn a PDF into text here — not pdftotext, not PyMuPDF, not a `fitz` heredoc.** If you are about to run one of those, you are bypassing this
  skill, and the text you get cannot be re-derived later.
---

# pdf-reader

A PDF, or a URL pointing at one, becomes text you can work with: markdown, the block
structure behind it, and the figures the document contains. The parsing itself happens on
the MinerU endpoint; this skill is the client. Its job is to decide how a document has to
be cut up against the endpoint's real limits, submit it, keep a record it can resume
from, and write the products somewhere predictable.

Neighbouring skills: `arxiv` fetches papers, `lit_research` reads and files them. This
skill is the conversion step in between.

## Never turn a PDF into text with anything else

The tempting alternative is one line — `pdftotext -layout`, `python -c "import fitz…"`, a quick `PyMuPDF` heredoc. It works, which is why it gets used. It is still wrong here, for three reasons that all showed up on 2026-11-13, when three papers were dumped by an inline `fitz` script and twelve sentences were quoted out of those dumps:

1. **The command disappears.** A heredoc leaves no record, no resume point, no parameters. Next week nobody can say which pages were read, or re-derive the text if a claim is challenged. This skill writes `run.json` and the products, so a read is an artifact rather than a memory.
2. **Page anchors get lost or invented.** This skill splits against the endpoint's real limits and the output keeps page structure; a flat dump plus a hand-written `===== PAGE n =====` header is a claim about pagination that nothing verifies.
3. **Token accounting is invisible.** The flash channel is free and says so; a local extractor silently spends nothing, so it also has no ceiling and no notice when it truncates — the failure that produces "the paper does not mention X" when it does.

**This file is the rule; there is no other copy to consult.** The skill gets copied onto someone else's machine, **where no global directory can be pointed at** — so everything this rule needs is written here.

So: a PDF becomes text through this skill, full stop. If a file defeats the flash limits (10 MB / 20 pages), that is a fact to report and handle here (`fetch`, `--pages`, the token channel) — not a licence to swap tools. A note may say "flash limit exceeded, read pages 1-20"; it may never say "extracted with fitz".

## `waiting-file` is an uplink problem, not a size ceiling

A job that ends with `state=waiting-file` (or blows `upload_timeout_s`) never reached the endpoint: the bytes were not accepted, so nothing was parsed. **It is not the file being too large** — a window is materialised first, in memory, as its own PDF (`src/run/submit.py: put_job`), and the job name carries the range (`paper_p1-2.pdf`). A 28 MB / 28-page file asked for `--pages 1-2` uploads about 2 MB.

So read the failure as transport and act on transport:

- retry with `fetch --run <run_id>` rather than resubmitting from scratch;
- move the window later (`--pages 10 12`) if the first pages are image-heavy;
- raise `common.upload_timeout_s` (default 300 s; one measured 8 MB window took 302 s on a ~27 KB/s uplink);
- do not conclude "both channels reject this file", and never fall back to a local extractor because of it.

## Before anything else: `--id`

Every call takes `--id <agent>`, and that is an **agent** id, not a MinerU account — it
belongs to this collaboration ecosystem, not to the endpoint. It may be written before or
after the verb, but it is never optional.

## A token selects the channel

There is no mode flag in practice. A stored token means the precision channel; without
one the skill uses the free flash channel and *says so* rather than refusing, because
flash is a legitimate degraded channel and the caller needs to know what it cannot
produce. `--flash` forces flash even when a token is stored.

A token is free; it comes from the endpoint's own user centre. Store it with
`keys set <token>`, inspect it with `keys status`, drop it with `keys delete`. It can also
be passed as `--token` for one call, or supplied as the `MINERU_TOKEN` environment
variable. The stored copy lives in the skill's data directory with owner-only permissions,
and it is only ever sent as a bearer header to `mineru.net`.

What each channel can do — pages per file, file size, batching, what the products
contain — is tabulated once, with its sources, in `docs/endpoint-limits.md`. No other
document repeats those numbers.

## Commands

**`read`** is the only way to submit work.

| flag | meaning |
|---|---|
| `-p/--pdf` \| `-u/--url` | the inputs; one or the other, never both |
| `-o/--output` | where this run writes, used exactly as given |
| `--pages` | read only part of a single source, e.g. `1-200` |
| `--ocr`, `--lang`, `--model` | sent to the endpoint explicitly, never left to drift |
| `--flash` | force the free channel |
| `--token` | a token for this call only |
| `--set KEY=VALUE` | override one parameter for this call only |

Several inputs in one call are one run: they share a record, a directory and a
concurrency budget. A source larger than the channel's page limit becomes several windowed
jobs inside that same run.

**`fetch`** finishes a run that stopped early. `fetch --run <id>` continues from the local
record; `fetch --batch <batch_id>` works from the server's handle alone, which is the way
back if the local record was lost. It is idempotent: products already on disk are skipped,
so a second call downloads nothing.

**`keys`** — `set`, `status`, `delete`.

**`config`** — `list`, `get`, `set`, `unset`, `reset`. One generic form and no
per-parameter flags: `config set <KEY> <VALUE>`. Keys are namespaced (`common.`,
`precision.`, `flash.`) so that the two channels can never share a name with two
meanings. Values are validated against bounds pinned to the endpoint's own ceilings, and
`config list --markdown` regenerates `docs/config.md`.

## What the caller sees

Standard output is empty. Everything goes to standard error, one line per event, prefixed
`pdf-reader: ` — the run handle as the run's first line (so a killed process is resumable
from what the caller already saw), progress, per-file results, warnings, advice, and a
closing tally naming the run directory:

```
pdf-reader: run 20261016_194300_197921 -> /tmp/pr_out4
pdf-reader: submit paper.pdf
pdf-reader: ok paper.pdf 1p 12.5s 1 blocks
pdf-reader: 1/1 done, 0 failed, 1 written; summary at /tmp/pr_out4/summary.json
```

`-v` adds `pdf-reader: debug:` lines; a level is spelled out only where it changes what the
line means, so a bare `pdf-reader:` line is ordinary progress. Machine callers use the exit
code and `run.json` rather than parsing these lines. `config list --markdown` is the single
exception that writes to stdout — the markdown table *is* the requested product, and it is
what gets redirected into `docs/config.md`.

Exit codes:

| code | meaning |
|---|---|
| 0 | everything asked for was delivered |
| 1 | nothing was delivered |
| 2 | something was delivered and something was not; a later `fetch` can collect the rest |
| 64 | the request or the stored configuration was wrong, so nothing was submitted |

## How a run proceeds

**One run is one document through one pipeline, and the block below is its literal order**: a stage skipped here does not fail loudly, it returns half a parse.

```
read → resolve parameters → plan the jobs → warn about quota → schedule
                          ┌─ submit: ask for upload links, then upload the bytes
                          ├─ poll:   ask only for the batch's state
                          └─ run record written before polling, so it is resumable
     when a job is finished ─→ download its result once → write the products
```

Four things are worth knowing before reading the code:

- **Splitting is virtual, and it happens only at a limit.** A file past the page limit
  becomes jobs that each carry a page range; no trimmed copy is ever written to disk, and
  a file that fits is never cut up, because the endpoint's cost is dominated by a fixed
  per-file delay rather than by page count.
- **When the page count is unknown the split is discovered.** A URL is never downloaded
  just to be counted, and a local file can only be counted when an optional library is
  present. In both cases the submission is blind and the endpoint's own refusal drives the
  windows, one at a time.
- **The in-flight budget adapts.** The endpoint publishes no concurrency limit, so the
  only signals are a "queue full" refusal and HTTP 429: a refusal halves the budget, a
  clean streak creeps it back up.
- **The state probe is cheap.** Only the batch's state is asked for; the result archive is
  downloaded once per job, when the products are actually wanted. The account's usage is
  never asked for, because no endpoint reports it.

## Parameters

Every tunable is declared once, in the definition area, together with its bounds (pinned
to the endpoint's ceilings), what reads it, and where its value came from. `config set`
stores a change; `--set KEY=VALUE` applies one to a single call; an environment variable
named after the key does the same from a shell. The precedence order and the full table
are in `docs/config.md`, which is generated from the definition area rather than written
by hand.

## Page counts, and what happens without the optional library

Counting a local file's pages needs PyMuPDF; it is optional, and the interpreter the
launcher uses here does not have it. That is not a failure: the file is submitted whole,
the endpoint's page-limit refusal is what reveals that it is too long, and the file is then
walked window by window until a window comes back empty. URL inputs are always blind, for
the same reason — counting their pages would mean downloading them.

## Long runs

A run narrates itself on standard error: submission, each state change while waiting, a
per-file line when it finishes, and a summary. One wall-clock budget covers the whole run
(thirty minutes by default) so a stalled task cannot hang the process.

Results do not live forever — the endpoint expires finished tasks — so products should be
collected promptly rather than re-fetched days later.

## Documentation map

**Four documents, four different questions; find your question in the right column** rather than reading the code.

| document | answers |
|---|---|
| `docs/endpoint-limits.md` | what the service allows, per channel, and where each number came from |
| `docs/outputs.md` | what a run leaves on disk, why, and what is deliberately absent |
| `docs/errors.md` | how failures are reported and what the run does about each kind |
| `docs/config.md` | every parameter (generated from the definition area) |
| `docs/scheduling.md` | how work is cut up, batched, spaced and paced — and the measurements behind it |
| `docs/architecture.md` | how the code is layered, what must stay true, and what to touch when something is added |
| `docs/protocol-notes.md` | how requests are shaped, and the traps that shaped them |
