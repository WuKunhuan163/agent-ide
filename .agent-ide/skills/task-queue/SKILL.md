---
name: task-queue
description: >-
  One durable FIFO per id. Keeps "what is next" outside the conversation and
  writes the head's verdict back to a task_tree node. Use for contract stacks,
  hand-off work items, or any list whose order must survive a crash.
---

# task-queue

One FIFO per id. The order lives only in `data/<id>/queue.json`; items live in `data/<id>/tasks/<key>.yaml`.

## When to use it

- A series of things must be done in an order that should not live only in the conversation.
- Each finished item leaves a `pass / fail / marginal` verdict that is written into the matching `task-tree` node.
- Hand-off: the next person runs `next` and does not have to read the previous conversation.

## Commands

**Four verbs, one queue, one head**: everything the tool does is a push, a pop, a resolve or a list, and only the head can be resolved.

```bash
task-queue push note.md --id <queue>          # enqueue at the tail; --front inserts at the head
task-queue next --id <queue> [--body]         # show the head (--body prints the full text)
task-queue list --id <queue>                  # one line per item, with status and position
task-queue pop --id <queue>                   # remove the head, archived as popped
task-queue resolve pass --id <queue> [--tree-id <tree>]
task-queue check --id <queue> [--fix]         # reconcile index against disk
```

`--id` may come before or after the subcommand; it defaults to `default`.

## Items

`push` accepts any text file:

- `.md`: the whole text goes into `body`; the title is the first non-empty line with a leading `# ` stripped, or the first 80 characters of that line when there is no heading.
- `.yaml`: reads `title` / `status` / `body`.

The source file is moved after enqueueing (the queue owns it), and `<key>` is `timestamp_title`.

```yaml
id: <timestamp>_<slug>
title: Write the queue tests
status: pending
created: <ISO 8601>
body: |
  Cover push/next/resolve/check…
```

`resolve` takes the head, writes `status` (passed/failed/marginal) and `verdict`, copies it to `data/<id>/_archived/`, then removes it from the index.

## Division of labour with task-tree

- The queue owns order: who is next.
- The tree owns structure: which hypothesis an item hangs under, and what the whole tree looks like.

`resolve --tree-id <tree>` actually calls `task-tree --id <tree> resolve <key> <pass|fail|marginal> --evidence "…"` (the verdict is positional; there is no `--verdict`). When the tree does not exist the queue prints one line and leaves the exit code untouched; when mirroring, `--evidence` overwrites the node's existing evidence wholesale.

## Data and recovery

**The queue survives a crash because it is a file, and the table says which file does what**: recovery is copying it back, not replaying commands.

| Path | Contents |
|---|---|
| `data/<id>/queue.json` | the order, the only authority |
| `data/<id>/tasks/<key>.yaml` | items |
| `data/<id>/_archived/` | history of popped and resolved items |

`check` looks for two kinds of mismatch: an index entry whose file is missing, and a file on disk that the index does not record. `--fix` drops dangling entries and appends unrecorded files by key. Moving machines: `queue.json` and `tasks/` must travel together.

`data/` is not committed to git.

## Install

**One copy and one id; there is no daemon and no state outside that directory.**

```bash
agent-ide install task-queue        # writes .agent-tools/task-queue
```

Depends on `pyyaml`, installed into the skill's runtime by `install`.

## Exit codes

**Exit codes tell you whether the head moved**, which is the only thing a scheduler needs to branch on.

| Code | Meaning |
|---|---|
| 0 | normal |
| 2 | usage or data error (missing file, invalid YAML, corrupt index, index entry with no file — the message suggests `check --fix`) |
| 3 | the queue is empty but a head was requested |
