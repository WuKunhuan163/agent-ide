# What the endpoint allows

This is the one place where the service's limits are written down, together with where
each number came from, so that no other document has to repeat them and no one has to
re-derive them.

| source | meaning |
|---|---|
| `[D1]` | the official API documentation |
| `[D2]` | the ecosystem repository's own description of the service |
| `[D3]` | the official client's built-in defaults |
| `[T]` | measured here, against the live endpoint |
| `[C]` | carried over from the archived tool |
| `[?]` | nothing published — the value is a policy choice or still unknown |

## The two channels

| | precision (a token) | flash (no token) |
|---|---|---|
| how it is addressed | its own versioned API, authenticated with a bearer token | a separate lightweight API, no credentials |
| file size | 200 MB [D1] | 10 MB [D1] |
| pages per file | 200 [D1] | 20 [D1] |
| several files per request | yes — batching is the point; the documented ceiling is 200 files but a single request may not ask for more than 50 links, so 50 is what can be used [D1] | no: one file per request [D1] |
| what the submission returns | a batch handle covering all the files in it | a task handle for that one file |
| what comes back when it finishes | one archive holding markdown, the block structure, and the document's figures | one markdown document |
| failure detail per file | a name, a state, a message, an archive address — and no code [T] | a state, **a code**, and a message [T] |
| how it is throttled | daily page allowance, below | per-IP request rate [D1] |

The token is not an optimisation: it selects the channel. Without one the skill falls back
to flash and says so, because the capability difference — no figures, no block structure,
twenty pages — is exactly what the caller needs to know.

The limits are ceilings on a *file*, not on a request: one precision request may carry
several files, each of them up to the limits above. Which is why the useful unit of
concurrency is "several documents at once", not "one document in several pieces" — see
`scheduling.md`.

## Daily allowance

- **1000 pages per account per day at top priority**, after which priority drops [D1].
  Dropping priority is not a refusal, so the local ledger warns and never blocks.
- A daily task-count limit and a separate allowance for HTML sources both exist, but
  **neither publishes a number** [D1]; they surface only when they are hit.
- **There is no allowance, usage or balance endpoint at all** [D1] — every endpoint is
  documented and none of them answers that question. So consumption can only be counted
  locally, and a ceiling is felt as a refusal rather than seen as a number.
- The web interface is reported to show a daily file allowance for flash. That number
  appears in no public document, so it is recorded as unverified and flash's ledger stays
  off by default.

## How long things take (measured here)

| quantity | value |
|---|---|
| asking for upload links | a fraction of a second [T] |
| uploading a small file | under a second [T] |
| a three-page precision run, end to end | about six seconds [T] |
| a one-page flash run, end to end | six to sixteen seconds [T] |
| a URL input, fifteen-page paper | about thirteen seconds [T] |
| six concurrent flash tasks | all six finished, eleven seconds wall clock, no throttling at all [T] |
| asking for a batch's state | most of a second, and works from a different process [T] |
| downloading a result archive | around a megabyte, under a second [T] |

The pattern behind those numbers matters more than the numbers: the endpoint spends three
to four seconds on fixed work per file and barely more per additional page. Splitting is
therefore only ever a response to a hard limit — never a way to go faster. The archived
tool cut files into five-page pieces, which multiplied the number of requests for no gain
at all.

## Time limits and validity

| item | value | source |
|---|---|---|
| upload link validity | 24 hours (stated for precision only) | [D1] |
| how long a submitted URL may stay cached | 900 seconds | [D1] |
| how often a callback would be re-delivered | up to 5 times (the skill uses polling, so this is only recorded) | [D1] |
| per-request timeout | no published value; the skill's default is 60 seconds, against measured replies of well under a second | [?] |
| accepting one file up to the size ceiling | the skill allows 300 seconds for a single upload; the official SDK's equivalent default is the same | [D3] |
| a whole run | the skill allows 30 minutes before calling it stalled; the official SDK's batch-level default is the same | [D3] |

## What is left unknown

Three numbers the service does not publish, and how the skill behaves without them:

- **concurrency** — the only signals are a "submission queue full" refusal and HTTP 429,
  so the in-flight budget starts modestly and adapts to what comes back;
- **daily task count** — recorded as unknown; the account is simply refused when it is
  reached, and a refusal of that kind stops the run for the day;
- **flash's daily file allowance** — unverified, so flash's ledger is disabled by default.

`docs/scheduling.md` explains what the skill does with each of them.
