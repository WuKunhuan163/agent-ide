# How work is cut up, spaced and paced

The scheduling decisions live in `src/plan/planner.py` (what to submit) and
`src/run/scheduler.py` (when to submit it). This document records *why* they are what they
are, because most of them are counter-intuitive and the obvious alternative was the one the
archived tool took.

## The shape of a plan

Planning turns inputs into **jobs**. A job is one submission: a source, and optionally a
page range — and a job that carries one uploads the pages it stands for, cut out in memory,
rather than the whole file plus a range. Nothing else is decided here — not batching, not
concurrency, not timing.

A URL is fetched into `data/sources/` before planning, so it can be measured like any other
source, and `--pages` names how much of a single source to read, each span of a comma list
becoming a job of its own.

Two independent things can put a source past what a channel accepts:

- **the page limit** — 20 pages for flash, 200 for precision;
- **the file-size limit** — 10MB for flash, 200MB for precision.

A source inside both is one job with no page range. A source over either is cut into
consecutive windows that stay under **both** limits, greedily: as many pages as fit, closed
by whichever ceiling is reached first. The page count alone cannot decide that — 150 pages of
scans are far over 200MB while 150 typed pages are not — so the planner measures the
serialized size of each page and budgets with it. Pages are measured one at a time, which
makes the sum over a window an upper bound for that window: the estimate errs towards a
smaller window, the direction that costs one request instead of a refusal.

When the size profile cannot be read at all the page ceiling still applies; a source that is
over the *file* limit **and** cannot be measured cannot be cut either, so it is refused
before submission with that reason.

## Splitting cuts in memory, and only ever at a limit

A window is cut out of the source in memory at upload time and sent as its own PDF, so the
request carries no page range: the file *is* the range. No trimmed copy is ever written to
disk. The archived tool wrote `chunk_0000.pdf` files into a directory relative to the
current working directory and then reassembled page numbers by hand — two ways to be wrong,
and both of them were.

Nothing downstream is ever told a range. A window exists only as the PDF of its own pages:
"pages 201-400 of this file" becomes a document of pages 201-400 before it is uploaded, and
that document is what the endpoint measures. Naming a range *and* sending a subset is what
goes wrong — page `201-400` of a file that is only 200 pages long — and with the window
materialised there is nothing left to name. A window that cannot be cut at all (no PDF
library present) fails with that reason instead of being submitted as a range of the whole
file.

Splitting is *never* a speed measure. Measured here, the endpoint takes roughly 3–4 seconds
of fixed work per file and little more per page: a three-page document takes about six
seconds end to end. So the archived tool's five-page chunks, applied to everything above
five pages, multiplied the request count fourfold for a file that was well inside the
limit, and did so *serially*. Cutting a file only when it exceeds a limit, at the limit
itself, is both fewer requests and the same product.

## The ladder: windows for a source the plan could not measure

A blind submission — a source whose page count could not be measured — that comes back
refused for length is replaced by windows **one at a
time** (`_ask_for_window`). The first window starts at page 1, and each window that finishes
justifies asking for the next one.

Where the file ends is decided locally, by the **mapping table** (`planner.window_map`): a
span that starts past the last page maps to nothing, and a window with an empty mapping is
simply not submitted. A 250-page document read in 200-page windows therefore costs three
requests — the blind one, then `1-200`, then `201-400` (mapped to the 50 pages that exist) —
and stops, instead of spending one on `401-600` only to be told there is nothing there. The
window that does travel is an ordinary PDF of exactly the pages in its mapping, never a
range of the original file.

Observed end to end on a 25-page document through the flash channel before the mapping
existed: the blind submission was refused with the service's own sentence ("file page count
exceeds API limit (20 pages), please input page_range…"), then `1-20` succeeded, then `21-40`
succeeded — the service clamped it to the pages that exist — and then `41-60` was refused,
which ended the ladder. The run reported **two windows delivered, nothing failed**, and the
last window was not recorded as a deliverable. That last step is now local, which is the same
outcome one request cheaper.

One window at a time rather than all of them up front, because the alternative is absurd in
retrospect: a 250-page source would have queued submissions that could not
possibly succeed, against a queue that is known to fill up. The ladder is also bounded, so
a source that keeps producing windows cannot loop forever.

A second safeguard: a refusal is only treated as "past the end" once at least one window of
that source has finished. If the *first* window is refused, that is a real failure and the
job is reported as one — the file could not be split at all. And a source whose page count
cannot be measured at all has no equivalent PDF to build, so it fails with that reason
instead of climbing a ladder that cannot work.

## Batching and concurrency are different tools

The endpoint's batch ceiling is the reason the unit of concurrency is a **document**, not a
piece of one: a single precision request may carry up to 50 links, each for a separate file.
Splitting one file into forty pieces and submitting them concurrently multiplies the request
count by forty against per-IP throttling and a queue that fills up — while the service is
already parsing that file's pages in parallel on its side.

The scheduler is the only place in the skill that runs anything concurrently. It holds a
budget of in-flight jobs and lets the endpoint's own feedback move that budget:

- it starts at `common.concurrency_initial` (4 by default);
- a "queue full" refusal or HTTP 429 **halves** it (`concurrency_down_factor`);
- after `concurrency_probe_after` clean finishes it **rises** by `concurrency_up_step`,
  capped by `concurrency_max`;
- a job whose failure is not about capacity does not touch the budget at all.

The ceiling is 6 and marked uncalibrated, because the service publishes nothing about
concurrency. Six concurrent flash tasks were measured completing with no refusal at all, so
6 is a verified floor rather than a guess — but it is a floor, not a limit, and raising it
is an experiment to be run, not a number to be copied.

## Waiting

Waiting is one loop with three parts: a cheap state probe, a backoff, and one deadline for
the whole run.

- **The probe asks only for state.** The official SDK's equivalent downloads the whole
  result archive every time it observes a finished file, which is ruinous as a status
  check; the skill asks the bare endpoint instead. The archive is downloaded once per job,
  when the products are actually wanted, and never again.
- **The backoff is a fixed sequence** (`common.backoff_steps`) rather than an interval
  multiplied by a factor. One sequence, read in one place, is easier to reason about than
  two knobs that can disagree.
- **One deadline** (`common.poll_total_timeout_s`, 30 minutes by default) covers submission,
  waiting and retries together, so a stalled task cannot hang the process.

Progress goes to standard error while all this happens: each state change for a flash task,
and a count of finished files for a batch. Without it, a two-minute wait looks like a hang.

## The ledger

There is no way to ask the service what the account has used — every endpoint is documented
and none of them answers that question — so consumption is counted locally, one calendar
day at a time, in the timezone named by `common.quota_reset_tz` (the service never says when
*its* day rolls over, so this is a stated choice rather than a discovered fact).

Two details matter:

- **Only pages are counted, and only for precision.** The 1000-page allowance belongs to the
  precision channel; flash is throttled by request rate instead. Counting flash's pages into
  the same ledger quietly consumed the precision allowance — observed once, at ten pages,
  and fixed.
- **The ledger warns, it does not refuse.** The documented behaviour above the allowance is
  a drop in priority, not a rejection, so refusing locally would invent a limit the service
  does not have. A refusal that *does* arrive stops the run.

## What is deliberately not here

**No key pool, no rotation.** The archived tool rotated between several accounts to stretch
a daily allowance. Since no endpoint reports consumption, that rotation could only guess
when to switch, and a wrong guess either wasted an allowance or burned a token. One slot is
kept in the interface, and nothing more.
