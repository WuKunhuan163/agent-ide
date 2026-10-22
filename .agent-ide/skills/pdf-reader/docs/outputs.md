# What a run leaves on disk

```
.agent-ide/skills/pdf-reader/data/
├── config.json                     the parameters the user changed, and nothing else
├── token.json                      the cloud credential, readable only by its owner
├── quota.json                      the local ledger: one day at a time
└── runs/<run_id>/
    ├── run.json                    the run record: handles and per-job truth
    ├── summary.json                the same, keyed by ids, for a reader
    └── jobs/<job_id>/
        ├── full.md
        ├── content_list.json       precision only
        └── images/<name>.jpg       precision only, as delivered by the server
```

Everything under `data/` is runtime state: a credential, a ledger, run records and
products. The credential, the ledger and the runs are kept out of version control;
`config.json` holds only the parameters someone chose to change, so it is small and
deliberately not ignored.

## Identifiers

A **run id** is a timestamp followed by a short random tail: fixed width, no source name,
so runs sort in time order and can never collide within the same second. It is what a
person types to resume or inspect a run.

A **job id** is a short opaque token — it names a directory and a row in the summary, and
carries no meaning beyond that.

The name sent to the endpoint is a different thing again, and it matters more than it
looks: a batch reports its files back by name and by nothing else. So the planning layer
gives every job in a run a distinct name. A window of a source is named after the source
plus the pages it covers (`paper_p1-200.pdf`), and two inputs that happen to share a file
name are suffixed, so that a run can never be ambiguous to itself.

## Why the products are per job

One run can hold several page windows of the same source — a 450-page file becomes three
jobs. Writing the products per job means windows cannot overwrite each other, and a single
failed window can be retried without touching the others.

## What is deliberately not written

| not written | why |
|---|---|
| the endpoint's result archive | it is an intermediate form; the products are extracted from it and the archive is dropped |
| the layout and model dumps the archive also contains | not publicly specified, and the official client ignores them too; reading them through a private field is what made the archived tool fragile |
| cropped figures | the archive already contains the figures the service decided on; re-cropping them locally duplicated work for no gain |
| page-by-page markdown | the endpoint returns a document, not a set of pages; splitting it per page invented a structure the products never had |
| converted DOCX / HTML / LaTeX exports | they can be requested from the endpoint but are outside what this skill is for |

## The summary, and why it is keyed by ids

The summary is keyed by run and job identifier — never by an absolute source path. The
archived tool's summary was keyed by absolute path, which made the file meaningless as soon
as it was read anywhere else. Each entry records the source as it was given, the page range
if any, the state, the failure message if there was one, and the paths that were written
relative to the run.

## Resuming without doing the work twice

A job counts as delivered once its products are on disk — recorded by a marker in the run
record. Because of that marker, finishing a run is idempotent: already-delivered jobs are
skipped, and a second attempt downloads nothing.

The run record is written **before** polling begins and before any request goes out, and its
handle is the run's first line, so a process killed mid-wait is always resumable from what is
already on disk — and the handle the caller saw is enough to find it.

## What a call prints

One stream for a person, one number for a script.

**stdout is empty** for every verb but one: `config list --markdown` prints the parameter
table, because that table *is* what the caller asked for — it is what `docs/config.md` is
generated from. Nothing else writes to stdout, so a caller that redirects it to `/dev/null`
loses nothing.

**stderr** carries the rest: one line per event, prefixed `pdf-reader: `.

```
pdf-reader: run 20261016_194300_197921 -> /tmp/pr_out4
pdf-reader: concurrency 4/6
pdf-reader: submit paper_p1-6.pdf
pdf-reader: ok paper_p1-6.pdf 6p 11.8s 4 blocks
pdf-reader: 1/1 done, 0 failed, 1 written; summary at /tmp/pr_out4/summary.json
pdf-reader: warning: no token found; falling back to flash
pdf-reader: error: precision mode needs a token
```

A level is spelled out only where it changes what the line means; a bare `pdf-reader:` line is
ordinary progress, and `-v` adds `pdf-reader: debug:` lines — upload sizes, the local ledger,
and the static notes that are true of every call rather than of this one.

The **exit code** is the machine-readable channel: 0 for a complete run, non-zero for a
partial or failed one (see `errors.md`). The per-job truth is in `run.json`, and in
`summary.json` which the closing line names.

Four rules keep it short, and they are what a new line has to pass:

- **One event, one line.** A fact already printed is not printed again.
- **One form.** A message does not change wording with the flag that triggered it.
- **No hand-made alignment.** Fields are separated by a single space; padding that lines up
  columns has to be redone by hand every time a field changes.
- **Anything true of every call belongs to `-v`.** It is not news for this one.
