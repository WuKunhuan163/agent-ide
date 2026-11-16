---
name: task-tree
description: >-
  A hypothesis tree whose nodes carry a verdict. Structure in
  data/<tree>/tree.json; resolve records pass/fail/marginal, settles parents, and
  moves the focus to the next open leaf. Use when the work branches (alternatives,
  prerequisites) instead of forming a line.
---

# task-tree

One tree is one file: `data/<tree>/tree.json`. Nodes are hypotheses, checks or goals; leaves are settled by `resolve`, parents aggregate their children, and `focus` points at the next leaf to verify.

## When to use it

- One question has several mutually exclusive routes (`one_of`: any one passing settles the parent).
- There are prerequisites (`--requires`: a node is `blocked` while a dependency is unpassed, and becomes `open` automatically once it passes).
- What was tried, and what was ruled out, has to survive for the next agent.

Linear work belongs in `task-queue`; the tree owns branching and evidence.

## Commands

**The verbs below are the whole interface; anything not listed here is done by editing files, which the tool will not detect as progress.**

```bash
task-tree init --root <node> --title "<goal>"          # create the tree (one root)
task-tree add <node> --parent <node> --title "..." [--type hypothesis|check|goal] [--body-file FILE]
task-tree add <node> --parent <node> --requires a b     # blocked until the dependencies pass
task-tree mode <node> all|one_of                       # how the node aggregates its children
task-tree next [--body]                                # the focused leaf, --body includes the text
task-tree body <node> --file FILE                      # write or replace a node's body
task-tree resolve <node> pass|fail|marginal --evidence "..." [--force]
task-tree focus [<node>]                               # show or move the focus
task-tree show                                         # the whole tree, * marks the focus
task-tree rm <node> --force                            # delete a subtree
task-tree check [--fix]                                # reconcile dangling parent/child/requires
task-tree export [--out FILE]                           # self-contained collapsible HTML
```

`--id` may come before or after the subcommand and defaults to `default`. The verdict is **positional**; there is no `--verdict`.

## States and progression

**States are ordered, and moving backwards is a separate verb, not a state change you type by hand**: read the progression column before setting one.

| State | Meaning |
|---|---|
| `open` | awaiting verification (only leaves can take the focus) |
| `passed` / `failed` / `marginal` | settled; `marginal` means partly holds and signals the hypothesis needs splitting |
| `blocked` | something in `requires` has not passed |

`resolve` does four things in order:

1. Write the state, `verdict` and `evidence`, and append to `history`.
2. Aggregate upwards to the parent (`all`: passes only when every child passes — with a failed child the parent stays open, because it was a branch that failed, not the goal; `one_of`: passes when any child passes, fails only when all fail).
3. On `pass`, unblock the nodes that depend on it.
4. Recompute the focus: the next `open` leaf in DFS order from the current node; when that subtree has none, wrap around the whole tree in DFS; if nothing is left, report `no open node left`.

`marginal` also triggers step 4, so the focus moves on. To keep splitting under the same hypothesis, pull the focus back explicitly with `add --parent <node>`.

## Division of labour with task-queue

- The queue owns order: one line, what is next.
- The tree owns structure: branches, dependencies, and the evidence for each branch.

A queue item may carry `node: <node-id>`; `task-queue resolve ... --tree-id <tree>` writes the same verdict into this tree, using the queue's own key as the node id when `node` is absent. When mirroring, the queue's `--evidence` overwrites the node's existing evidence.

## Export

`export` writes self-contained HTML (inline styles, native `<details>` folding) — no server, no network. The default path is `data/<tree>/tree.html`.

## Data and recovery

**Everything the tool persists is under one directory, and recovery means copying it back**: the table shows what each path holds.

| Path | Contents |
|---|---|
| `data/<tree>/tree.json` | nodes (with bodies), focus, history — the only authority |
| `data/<tree>/tree.html` | the most recent export |

`tree.json` is readable JSON, meant to be opened and diffed directly. Node bodies live in `body`; `show` does not print them, `next --body` and the exported HTML do. `check` looks for four problems: a non-root node with an empty `parent`, a `parent` that does not exist, a child missing from its parent's `children`, and a `requires` pointing at a deleted node. `--fix` drops those dangling references and moves the focus to a legal position.

`data/` is not committed to git.

## Install

**Install is one copy and one binding; there is nothing to build**, and running it twice is safe.

```bash
agent-ide install task-tree
```

Standard library only, no third-party dependencies.

## Exit codes

**Exit codes are the only machine-readable answer the tool gives**, so a script must branch on these and never on the printed text.

| Code | Meaning |
|---|---|
| 0 | normal |
| 2 | usage or data error (tree missing, node missing, duplicate id, refusal to delete the root) |
