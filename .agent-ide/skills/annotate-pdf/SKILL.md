---
name: annotate-pdf
description: >-
  Mark up a pdf in a browser and hand the whole list of changes back in one batch: the user selects text on a page the way any pdf viewer allows, types what should change, and the entries accumulate in the instance's json with the page number, the page-relative rectangles of the selection and the selected words. Use it when a pdf needs many small corrections and one message per correction would cost a round each.
---

# annotate-pdf

The pdf twin of `annotate-file`: same page, same colours, same hover card, same one-pass hand-back. The difference is the locator — a page number plus a box, instead of a line number.

## When to use it

- The document is a pdf and the corrections are **local** — a phrase, a caption, a figure, a table cell.
- The user wants to **see the page while marking it**, not read a list of page/coordinate pairs.
- Many corrections at once: mark them all, apply them in one round.

## The instance

One json under this skill's `data/`:

```json
{"id": "paper", "doc": "workspace/literature/paper.pdf", "pages": 12,
 "created": "...", "updated": "...",
 "items": [{"page": 3, "quote": "the metric saturates at 0.82",
            "rects": [{"x": 0.12, "y": 0.30, "w": 0.40, "h": 0.021},
                      {"x": 0.12, "y": 0.34, "w": 0.31, "h": 0.021}],
            "note": "this sentence contradicts §2.1", "at": "..."}]}
```

| Field | Meaning |
|---|---|
| `id` | names the instance, first path segment: `http://127.0.0.1:8766/paper/` |
| `doc` | the served pdf, relative to the project root |
| `pages` | page count, read when the instance was opened |
| `items[].page` | 1-based page number |
| `items[].quote` | the selected words, whitespace collapsed, capped at 300 characters |
| `items[].rects` | one box per line of the selection, **relative to the page: 0..1 from the top-left**, so the same item survives any zoom or re-render at another dpi |

**One port, many instances**: `8766` serves all of them, `/` lists them.

## Commands

```bash
annotate-pdf open --doc <path.pdf> [--id <id>]   # create or refresh an instance, start the server, print the url
annotate-pdf list                                # id, document, page count, number of items
annotate-pdf url --id <id>                       # url only
annotate-pdf stop                                # stop the server
annotate-pdf serve                               # run the server in the foreground
```

`open` derives the id from the file name, counts pages, starts the server if needed, and prints one line — the url. **That line is what the reply carries.**

## Reading the list back

```bash
cat .agent-ide/skills/annotate-pdf/data/<id>.json
```

Each item: `page` says where, `quote` says which words, `rects` says where they sit on the page, `note` says what to change. **`quote` is the locator** — search the pdf's extracted text for it; **`rects` is the fallback** for text that does not extract cleanly (scans, figures) — multiply the relative values by the rendered page size and read the region. Apply every item in one pass.

Pages are rendered and cached at `data/<id>/p<NN>.png`; they are rebuilt when the pdf is newer than the cache.

## What the page does

- Select text on any page the way a normal pdf viewer does — click and drag, or double-click a word; the selection is stored as page + one box per selected line + the words themselves.
- Press Enter after typing the change; each item has its own colour and a number at the top-left of its first line.
- Hovering a number shows the note with **copy** and **delete**.
- Every add, delete and clear is written to the json immediately (temp file, `fsync`, rename), so closing the page or restarting the server loses nothing.

## Boundaries

- **The page never edits the pdf.** It records boxes and notes; the agent edits the source.
- **One instance, one pdf.** Two pdfs are two instances and two urls.
- **`note` holds the instruction only** — no greeting, no questions to the agent.
- **Rendering needs PyMuPDF**; the package declares it in `skill.json`, and the page shows the error text if a page cannot be rendered.
