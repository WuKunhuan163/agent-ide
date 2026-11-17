---
name: annotate-file
description: >-
  Mark up one markdown file in a browser and hand the whole list of changes back in one batch: the user selects a span and types what should change, the entries accumulate in the instance's json, and the agent applies them in a single pass. Use it when a document needs many small corrections and one message per correction would cost a round each.
---

# annotate-file

One instance serves one document. The user marks text in a browser; the changes accumulate on disk; the agent applies the list in one pass.

## When to use it

- A document needs **many small corrections**, and doing them one message at a time wastes rounds.
- The user wants to **see the document while marking it**, not read a diff.
- The corrections are **local** — a phrase, a sentence, a paragraph — not a restructure.
- The user asks for **a flat written introduction of something** ("平铺介绍 X", "write it to tmp and serve it"): write the prose to `tmp/<name>.md`, then `open` it under the same `<name>`. **Reuse the file and the id when the previous introduction covers the same subject and its items have already been applied** — one subject, one file, one url.

**The browser opens once, at the first serve; a later edit does not open it again.** After `open` creates a new instance, open it in the system browser (`open "http://127.0.0.1:<port>/<id>/"`). When the same instance's document is later rewritten and re-served with `open`, **do not open the browser again** — the page reloads the document from disk on refresh, and a window that jumps to the front uninvited is a second interruption for a change the user is already watching. Open again only when the user asks.

**What a served introduction looks like.** The body is in the user's own language; **anything that is an external promise** — a title, a CV description, a fixed abstract — stays in its original wording (English, as given) and sits at the top of the file inside a `>` blockquote. **Do not label it "Locked"**: the quote block is the signal, and a second label is one more line to maintain. Everything below the blockquote is the part the user is free to mark.


## The instance

An instance is one json under this skill's `data/`:

```json
{"id": "owner-intro", "doc": "tmp/owner-intro.md", "created": "...", "updated": "...",
 "items": [{"line": 13, "end": 13, "quote": "path is not guessed", "note": "make it decisive"}]}
```

| Field | Meaning |
|---|---|
| `id` | names the instance and is the first path segment: `http://127.0.0.1:8765/owner-intro/` |
| `doc` | the served document, relative to the project root; change it on the next `open`, the items stay |
| `items` | the change list in the order it was marked: `line`, `end`, `quote`, `note`, `at` |

**One port, many instances.** `8765` serves all of them; the path segment picks one; `/` lists them.

## Commands

```bash
annotate-file open --doc <path> [--id <id>] [--body <path>]   # create or refresh an instance, start the server, print the url
annotate-file list                            # id, document, number of items
annotate-file url --id <id>                   # url only
annotate-file stop                            # stop the server
annotate-file serve                           # run the server in the foreground
```

`open` derives the id from the file name when `--id` is absent, starts the server if it is not running, and prints exactly one line — the url. **That line is what the reply carries.**

## Serving a document that is being edited

`open` prepares the page for reading a moving document, and the preparation is part of the instance, not a habit of the agent:

1. **Commit first.** Anything uncommitted in the served document is committed on `open` — message `annotate: <doc> before serve`, that path only, nothing else staged.
2. **Store no baseline.** The diff is computed against `HEAD` on every request, not against a commit remembered at serve time. A stored baseline goes stale as soon as the document is edited and committed again, and a stale baseline paints the whole file as changed; comparing with `HEAD` is self-correcting, because a committed change simply stops being marked.
3. **Paint the diff.** `/api/<id>/doc` returns `changed`, the new-file line numbers whose content differs from `HEAD` — what is uncommitted right now, nothing older.
4. **Check the mirror.** `open --doc <intro> --body <body>` stores the pair; the page header then reads `镜像同步 · <body 行数>/<intro 行数> 行`, or turns red with the body's path when the two files' mtimes disagree. `open` also prints one warning line to stderr in that case.

```
annotate-file open --doc staging/execution-loop-intro.md --id loop \
  --body .agent-ide/skills/overleaf/src/template/docs/strategy-results-first/execution-loop.md
```

**Serve only when asked.** Editing a served document does not require another `open`: the page reads the file from disk, so a refresh shows the change. Run `open` only when the user says serve, open, reopen or show this version. An extra `open` commits, resets the baseline and clears the diff colour while the reader is annotating.

## Reading the list back

When the user says the document is marked, read the instance and apply:

```bash
cat .agent-ide/skills/annotate-file/data/<id>.json
```

Each item is one change: `quote` locates the text, `note` says what to do with it.

**An item marked on a served introduction is a specification for the document it summarises.** Apply it to that document's own lines and report the `path:line`; rewriting only the served copy leaves the document the user reads every day unchanged. **Apply them in order, in one pass** — the list exists so that a single round covers every item.

After the pass, tell the user to reload the page. Marks whose quote no longer matches the document are stale and lose their highlight.

## What the page does

- Marks each span in its own colour with a number at the top-left of the first line.
- Hovering a mark shows the note with **copy** and **delete**.
- Every add, delete and clear is written to the json immediately (temp file, `fsync`, rename), so closing the page or restarting the server loses nothing.

## Alignment: what the intro may say

`docs/alignment.md` is the companion chapter on 口径对齐. It governs any intro document served beside a body:

- the L1 title is always `# <本体文件名> 口径对齐介绍文档`; scope, version and date go into the first paragraph, never into the title;
- the intro mirrors the body rather than summarising it: same numbers, same terms, same keys, and a user's scope or style request is layered on the default rather than replacing it;
- a sync runs before any writing: compare, decide by the more recently edited side, then `open --doc <intro> --body <body>` — the page header showing `镜像同步 · <n 行>` is the evidence.

Read that chapter before editing a served intro, not after.

## Boundaries

- **The page never edits the document.** It records what should change; the agent edits.
- **One instance, one document.** Two documents are two instances and two urls.
- **Items are not a conversation.** `note` holds the instruction only — no greeting, no questions to the agent.
