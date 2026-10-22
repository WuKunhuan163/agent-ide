# How the code is put together

Read this before changing anything: it records the decisions that other decisions depend on,
and the places where adding something touches more than one file.

## Three stages, one direction

```
util → config → endpoint → plan → run → deliver → cli
```

- **`plan` decides.** It turns inputs into jobs and has no side effects — no network, no
  files written. Its output is plain data.
- **`run` executes.** It is the only layer that talks to the endpoint and the only place
  that writes run state.
- **`deliver` converts.** It turns whatever the endpoint produced into the on-disk shape.

Dependencies point one way only, and the arrow is the reason the layering is worth having:
`util` and `config` know nothing about the endpoint; `plan` cannot reach into `run`, so a
decision can never secretly depend on execution state; `deliver` cannot schedule, so
delivery cannot retry work. Two consequences that are easy to get wrong:

- `plan/quota.py` owns the ledger *file*, but it is `cli`/`run` that decides when a run is
  over and calls the write. Ownership stays in the planning layer; the moment of truth
  stays in execution; the dependency never reverses.
- Identifiers live in `util/ids.py`, low enough that planning and execution can both make
  one. They were briefly defined in the endpoint's data models, which is a layer that has no
  business inventing run names.

## Four invariants, and where each is enforced

1. **Concurrency exists in exactly one place** — the scheduler. Submission, polling and
   delivery are ordinary single-job functions that do not know they may be called
   concurrently. If a second place ever spawns work, the adaptive budget becomes a fiction.
2. **Configuration is resolved in exactly one place.** No module below `config` reads the
   environment or the stored overrides; everything receives a validated object. That is what
   makes `config set` take effect everywhere at once and what makes the whole pipeline
   testable without touching a real file. (The one deliberate exception is the transport's
   SSL certificate lookup, which reads the conventional certificate environment variables —
   that is an operating-system contract, not a configuration value, and it is documented in
   `protocol-notes.md`.)
3. **A result archive is downloaded once.** A job is marked delivered when its products are
   on disk, and delivery skips jobs that already carry that mark. A second attempt must
   download nothing.
4. **The upload request carries no content type.** The signed URL does not cover that
   header, and sending one produces a signature error that looks exactly like a broken
   channel. This rule is asserted in `tests/test_units.py` and explained in
   `protocol-notes.md`.

## Capabilities, not `if mode`

The two channels differ in *every* layer: pages, size, batching, whether submission returns
a batch or a task handle, whether a result archive with figures and blocks exists at all. If
each layer tested the mode, the differences would drift apart across three files.

So the differences are collected once into a capability set (`src/mode.py`), built from the
channel's own configuration namespace. Planning reads the page limit and the file-size limit
from it; submission reads whether batching exists; delivery reads whether a result archive
and figures can be expected; credentials read whether a token is required. No layer writes
`if mode == ...`.

Adding a channel is therefore a single-file change plus a configuration namespace — the
section below lists the exact places.

## The client is an interface, and that is not decoration

The scheduler takes an endpoint object satisfying a small protocol. That seam is the only
reason the adaptive budget, the retry policy and the window ladder can be tested without a
network or an allowance: `tests/test_units.py` runs a fake endpoint that refuses windows past
the end of a document and asserts that the ladder walks one window at a time and reports the
run as delivered. Any change that makes the scheduler import a concrete HTTP client would
remove that ability.

## Changing things

| change | touch |
|---|---|
| a new parameter | the definition area (`src/config/schema.py`) — bounds, source, and which module reads it; `docs/config.md` regenerates itself, so never edit it by hand |
| a new error code | the verdict table in `src/endpoint/errors.py`, plus the wording tests if the service reports it as text |
| a new product from the endpoint | `src/deliver/` — and a line in `docs/outputs.md` if it changes what a run leaves behind |
| a new capability on an existing channel | `src/mode.py`, then whichever layer reads the new capability |
| another channel entirely | `src/mode.py` + one configuration namespace + the endpoint methods it needs; nothing in `plan`, `run` or `deliver` should need an edit |
| a new verb | `src/cli.py` only — the layers below it do not know verbs exist |

## What differs from the archived tool

The archived tool is still on disk next to this one, so its documentation can still be read.
Two things about it are worth stating plainly.

**Numbers it got wrong.** It claimed a 600-page limit for the precision channel (the real
limit is 200); it placed the executable in a `dev_tools` directory that does not exist in
this ecosystem (the convention is `.agent-tools`); it told every new project to run an
installer that installs into that directory (there is nothing to install — the entry point
is a thin script); it described five-page chunking as protection against a five-minute
upload timeout (no such limit exists, and chunking around it cost fourfold requests); and it
documented parameters that the implementation did not have.

**Parameters it had, and where they went.** `--chunk-size` and `--retries` became ordinary
configurable parameters (`precision.split_page_limit`, `flash.split_page_limit`,
`common.retry_max`); the chunk threshold no longer exists as a separate number, because the
split threshold *is* the channel's page limit, and having both invited the two to disagree.
`--extract-images` and the fixed per-page output shape became unconditional products for the
precision channel; the archived tool re-cropped figures at a fixed resolution that the
service had already cropped for it. The multi-account key pool, the packaging scripts and the
page-by-page markdown layout were dropped for the reasons recorded in `scheduling.md` and
`outputs.md`.

One habit is worth keeping deliberately: the archived tool's documentation described
capabilities its code did not have, and drifted further with every release. Here, anything
generated from a definition (the parameter table) is not hand-written, and anything that is
hand-written states a rule rather than an inventory of the code.

## Which document may mention code

Two kinds of document, two standards, and they exist so that neither drifts:

- **Usage and contract documents** — `SKILL.md`, `endpoint-limits.md`, `errors.md`,
  `outputs.md` — describe behaviour, limits, commands and products in plain language. They
  may name a command, a parameter key, or a number the service publishes. They may not name
  a module, a function, a field or a sample measurement, because those change without the
  behaviour changing, and a reader who trusts them learns the wrong thing.
- **Technical documents** — `architecture.md`, `scheduling.md`, `protocol-notes.md` — are
  for whoever changes the code, so they may point at it. They are also where the *reasons*
  live: a rule whose reason is unwritten gets deleted by the next person who finds it
  inconvenient.

## The environment this runs in

The launcher executes the skill with the ecosystem's bundled interpreter, and agent-ide
installs the skill's declared `python.requirements` — PyMuPDF — into that interpreter. The
library is therefore present in practice, which is what makes measurement the normal path: a
source's page count *and* its per-page sizes are read before submission, and a source over
either limit is cut into windows (see `scheduling.md`).

The code still treats the library as optional. Without it a source cannot be measured, so it
is submitted blind and its page count is discovered by the ladder described in
`scheduling.md`; a source that is over the file-size limit in that state is refused, because
it can be neither submitted nor cut.
