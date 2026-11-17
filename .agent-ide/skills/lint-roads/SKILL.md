---
name: lint-roads
description: >-
  Check a thesis draft directory against the roadmark contract: the five header keys of every section file, SECTION pointers into the positioning document, sign ids and their four fields, STATUS vs the signs actually present, bare `--` cells, and `[pending: id]` markers. Use it before handing a chapter back, or when a section file was edited by hand and may have drifted from the contract.
---

# lint-roads

Ten checks over the `2.x.*.draft.tex` files of one assemble directory, plus the work queue those sign lines describe.

## When to use it

- A section file was edited and you need to know it still honours the contract before compiling.
- The queue is being handed to someone: `--queue --md` prints it as a table that pastes into the ledger.
- After the positioning document was renumbered: `SECTION` pointers are checked against it, and a pointer into a missing section is a defect.

## Usage

```bash
lint-roads                                   # defaults to report/final/assemble
lint-roads <assemble-dir>
lint-roads <assemble-dir> --queue            # id, kind, what, owner, blocks, since
lint-roads <assemble-dir> --queue --md       # same, as markdown
```

Exit code 0 means clean; 1 means at least one defect, each printed as `FAIL <file>:<line> <reason>`.

## What it checks

| # | Check |
|---|---|
| 1 | the first five lines are `% SECTION`, `% CLAIM`, `% NEEDS`, `% HANDS`, `% STATUS`, in that order |
| 2 | `SECTION: n <- thesis §x.y` names a section that exists in the positioning document |
| 4–7 | every `% PENDING/DECIDE/ABSENT(id):` line has a valid id, appears once, and carries four fields `what \| owner: | blocks: §x.y | since: YYYY-MM-DD`; `what` may not contain a digit |
| 8 | `STATUS: blocked(id)` names a sign that is in the same file |
| 9 | the number of bare `--` table cells does not exceed the number of signs |
| 10 | every `\emph{[pending: id]}` in the body has a matching sign |

## Files it reads

- `2.*.draft.tex` (or `5.*.draft.tex` in an older tree) inside the given directory.
- The positioning document, tried in order: `<repo>/workspace/毕设立意.md`, `<repo>/workspace/thesis-positioning.md`, `<assemble-dir>/毕设立意.md`. **If none exists, the section-pointer check is skipped rather than failed** — a draft tree can be linted without the positioning document present.

## Boundary

It reads and prints; it never edits a draft, never fills a sign in, and never decides whether a claim is true. A clean run means the files obey the format, not that the content is right.
