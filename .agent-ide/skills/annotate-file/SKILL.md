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
annotate-file open --doc <path> [--id <id>]   # create or refresh an instance, start the server, print the url
annotate-file list                            # id, document, number of items
annotate-file url --id <id>                   # url only
annotate-file stop                            # stop the server
annotate-file serve                           # run the server in the foreground
```

`open` derives the id from the file name when `--id` is absent, starts the server if it is not running, and prints exactly one line — the url. **That line is what the reply carries.**

## Reading the list back

When the user says the document is marked, read the instance and apply:

```bash
cat .agent-ide/skills/annotate-file/data/<id>.json
```

Each item is one change: `quote` locates the text, `note` says what to do with it. **Apply them in order, in one pass** — the list exists so that a single round covers every item.

After the pass, tell the user to reload the page. Marks whose quote no longer matches the document are stale and lose their highlight.

## What the page does

- Marks each span in its own colour with a number at the top-left of the first line.
- Hovering a mark shows the note with **copy** and **delete**.
- Every add, delete and clear is written to the json immediately (temp file, `fsync`, rename), so closing the page or restarting the server loses nothing.

## Boundaries

- **The page never edits the document.** It records what should change; the agent edits.
- **One instance, one document.** Two documents are two instances and two urls.
- **Items are not a conversation.** `note` holds the instruction only — no greeting, no questions to the agent.
