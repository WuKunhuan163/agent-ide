---
name: hook
description: Register a condition → context rule inside the IDE. A rule fires on a keyword (the prompt contains it) or on similarity (the prompt is closer than a threshold to a stored context), and when it fires, its value is injected into the model's context before the answer. `hook` is the tool's name; registration checks for a duplicate id and records the IDE type.
---

# hook

**`id` is the dedup key, and it is the only one.** A registration is identified by its id: `add` refuses an id that exists (exit 3), `set`/`rm`/`on`/`off` act on ids, and the IDE entry follows from the id — one id, one entry. Nothing else needs a duplicate check, because nothing else can produce a second copy.

One rule is a condition and a value. The condition is checked against the prompt the user just typed; the value is text put into the context of the answer that is about to be written. Nothing else happens: no file is edited, no command is run.

## What a rule is

```json
{"id": "loop", "ide": "codebuddy", "trigger": "keyword",
 "keywords": ["对比行文", "行文闭环"], "match": "any",
 "inject": "read staging/execution-loop-intro.md before answering", "enabled": true}
```

| Field | Meaning | Required |
|---|---|---|
| `id` | the rule's name; **registration refuses a duplicate** (exit 3) | yes |
| `ide` | where the rule is installed: `codebuddy` today, from `models` | yes |
| `trigger` | `keyword`, `sim`, or `fn` | yes |
| `fn` | the predicate's name; `tools` today | for `fn` |
| `keywords` | for `keyword`: the list; `--match any\|all` decides whether one or every word must appear | `keyword` |
| `key` / `threshold` | for `sim`: a stored context copied to `data/keys/<id>.md`, and the cosine below which nothing fires (default 0.55) | `sim` |
| `inject` | the value: text, or `@path` to read a file at registration (`fn` needs none) | no for `skill` |

`fn` is the predicate class: a function decides, not a word list. The one predicate today is `tools` — it answers "does the prompt name an installed tool". `tools` merges the launchers under `.agent-tools/` with the directories under `.agent-ide/skills/` by name, and injects one line per name that appears — `【name】先读 <path>（<lines> 行）：<first sentence of description>`, or `【name】已安装：<launcher>` when the tool has no SKILL.md. A new skill needs no registration, and this tool is a skill like any other, so mentioning `hook` injects its own SKILL.

Two triggers, two meanings. A keyword trigger is a gate: the word appears or it does not. A similarity trigger is a measure: the prompt and the stored context are reduced to token sets (words ≥2 characters, plus Chinese bigrams), and cosine is compared with the threshold. 
## Registering

```bash
hook add --id loop --trigger keyword --keywords "对比行文,行文闭环" --inject "先读 staging/execution-loop-intro.md 再答"
hook add --id shelf --trigger sim --key data/keys/shelf.md --threshold 0.62 --inject "先 ls 两个文献库"
hook add --id skill --trigger skill                     # the skills directory is the list
hook list / set <id> / rm <id> / on [id] / off [id]
```

**No generator lives here.** A value is authored per rule and edited in place; nothing in this skill derives values from another document, because a generated value is a second copy that drifts from the document it was cut from. Editing `data/inject/<id>.md` is the way a value changes.

**Registration is the install, in one act**: `add` writes the rule files and, in the same call, guarantees exactly one `UserPromptSubmit` entry in the IDE's settings pointing at this launcher. `rm` removes the rule; when the last rule goes, the entry goes with it. There is no separate install step and no state that says "registered but not wired".

**The duplicate check is by id across the whole registry**, not per project: two projects sharing this tool must use different ids, or the second `add` is refused with the original's trigger.

## How it fires

The IDE calls this launcher with no arguments and the payload on stdin. It reads the prompt from `prompt`, `message`, `text` or `content`, evaluates every enabled rule, and writes the matched blocks to stdout as plain text — no JSON wrapper:

```
【skill｜skill hook】
【hook】先读 .agent-ide/skills/hook/SKILL.md（87 行）：Register a condition → …
```

A hook is a condition and a value: the value is context injected verbatim under a one-line head `【<id>｜matched <condition>】`. Nothing else is appended — no second kind of block, no trailing receipt block, no `cmd` field. The value itself opens with an `【aware】` line: answer `回执：<id> → <the first action it triggers>` at the very top of the reply, before any work. Every value carries that line, so awareness and the receipt live in the value rather than in the launcher. Unmatched prompts produce nothing at all. Any exception is logged to `data/hook.log` and the process exits 0 — a broken rule may never break the session.

## Data

**One rule, one package**, so a rule can carry code as well as text:

```
data/hooks.json            index: ide, ids, updated
data/hooks/<id>/hook.json  the rule — id, ide, trigger, keywords | key + threshold, enabled, entry
data/hooks/<id>/inject.md  the value injected when it fires
data/hooks/<id>/*.py       optional: `hook <id> ...` runs this (resolved in the package first, then beside hook.py)
data/keys/<id>.md          the stored context for a similarity rule
data/capture/<id>.txt      the last prompt that fired, for rules with `capture`
data/hook.log              fire / error lines only
```

The older shape (`data/hooks/<id>.json` + `data/inject/<id>.md`) still reads, so an
existing rule keeps firing; `add --package` writes the package form. `hook <id> <args>`
runs the package's own `entry` module, which is how a rule owns a state machine instead
of a paragraph of advice.

Code that must travel with the skill lives beside `hook.py` (`plan.py`), because `data/`
is per-project state; a rule may still keep a module of its own inside its package when
only that project should run it.

**`plan-auto` is the default shape of a rule that wants every prompt**: trigger `fn: always`
plus `auto_instance: true` (and `capture: true`) means the hook stores the prompt on every
message and lets the package allocate or resume a tree, injecting the instance number and
the next node. Nothing waits for a keyword.

**`plan` is the worked example**: `hook plan init → add → ready → start → done → ack →
(next | replan → add|drop|move → resume) → close`. Instances live in the rule's own data space,
`data/plan/<project>-<stamp>-<summary>/tree.json`: deleting a project's `tmp` must not
delete the plan, and the tree doubles as the trace.

**Output is one line per fact, `+` added, `-` removed, `=` unchanged**: `add` prints `+ <id> <trigger> <condition>` and the value's path, `rm` prints `- <n>`, `list` is a fixed-width table, `test` prints the measured number, `doctor` prints `key value` rows. No sentences.

`list` reads the rule files, `doctor` reports the count of rule files against the count of value files and names any rule whose value is missing. The data lives here, never in the project directory.

## Boundaries

- Injects plain text; never edits a file, never runs a command, never blocks the prompt, never wraps the output in JSON.
- One event only: `UserPromptSubmit`. Rules about stopping belong to `heartbeat`.
- The keyword list is matched as substrings, so a one-character keyword fires on almost everything; `models` and `list` exist to be read before adding one.
- A similarity threshold is per rule and is chosen from `test` output; copying another rule's number is guessing.
