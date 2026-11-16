---
name: heartbeat
description: No stopping while the backlog is open. A Stop hook pushes one queue item back into the session at the moment it was about to end — one item at a time, with progress counted from artefact files rather than from self-reports. Bound to a session, never to a project; unmatched sessions stay completely silent. Suited to long unattended chains, and to the case where a model loses context mid-way and forgets what it was doing.
---

# heartbeat

A session-level heartbeat: the right to push belongs to the hook, not to the model.

## Mechanism

The Stop hook reads the payload; when the session matches a binding and the queue still has unfinished items, it emits `{"continue": false, "stopReason": "<prompt>"}`. The prompt names exactly one item, carries that item's criteria, the artefact path, and the `inc`/`block` commands to run at the end, and states that a second item must not be started in the same turn. Any exception is swallowed, logged, and the process exits 0 — the hook may never break the host session.

## Rules

1. Only the hook may initiate a push. The CLI has no "push one now" verb; the model can only record (`inc` / `done` / `block` / `doing` / `todo`).
2. One item per push, and stop after pushing it.
3. Progress is verified from artefacts, never from self-reports: `inc` counts the lines in the `--evidence` file matching `--pattern` and refuses (exit 4) when the count does not strictly grow.
4. Bound to a specific session, never to a project. A session binding does not fire merely because the directory matches.
5. Backlog data lives in this skill's `data/`, one file per session, never in the project directory — the scope of the data is the scope of the effect.
6. Unmatched sessions are entirely silent: no output, no log line; the log records only nudge / hold / autoblock / error.
7. The same item pushed `stall_limit` times with no change in the artefact line count becomes `blocked` automatically, and the next item takes its place.
8. Chains need limits and expiry: `max_nudge_per_chain`, `chain_gap_seconds`, `max_age_hours`.
9. Whether the install works must be diagnosable: `doctor` reports whether the binding hits the session, whether the backlog file exists, whether the hook is registered, and where the chain counter stands.
10. Project-specific pre-push checks go through `pre_nudge_check` with an external command; they are never hard-coded into the tool.
11. Configure through commands, never by editing the config file: one wrong character is not reported, it just silently stops working.
12. No identity guessing: the CLI accepts an exact session only and never falls back to "there is only one binding and the directory matches"; the hook trusts only the `session_id` in the payload. Do not inject this skill into a project running several agents in parallel — `SKILL.md` is loaded by every session in the project. Run `.agent-tools/heartbeat` directly when needed.
13. One session runs one task line at a time; when unrelated new work arrives while the main line is still open, run `off` first.

Only `Stop` is handled. `SubagentStop` and `UserPromptSubmit` are unusable: a subagent and its parent share one `session_id` and the payload carries no field that separates them. `install` writes the `Stop` event only; `uninstall` scans every event for entries containing this tool's command.

## Install and binding

**Install is a copy plus one binding, and the binding is what makes a heartbeat belong to a task** rather than to the machine.

```bash
agent-ide install heartbeat    # writes the launcher (interpreter path baked in)
heartbeat.py install [--scope user|project] [--loop-limit N|-1]   # installs the Stop hook, idempotent
```

The default is the user scope; `bindings` narrows the effect. `--loop-limit` caps re-entry (default 20; legal values are -1 or 1..100, and out-of-range values are silently reduced to 1 upstream).

```bash
heartbeat.py sessions                    # pick the session id here; a session is remembered only after one Stop
heartbeat.py bind --session <id> --work /path/to/project
heartbeat.py on --session <id>
heartbeat.py doctor
```

`bind` accepts `--session` only; `--cwd` is rejected. `unbind <session>` removes a binding, `exclude <id>...` excludes sessions.

## Backlog

**The backlog is what accumulated while nothing was watching**: read it before starting anything new, or the first tick drowns in stale work.

```bash
heartbeat.py add "<text>" --evidence <path> --pattern '<re>' \
  --judge "<what counts as finished>" --total <N>
```

- `--evidence` + `--pattern`: the progress source. It runs without them, but `stall` then cannot see progress and only the chain limit holds the line.
- `--total`: the target line count in the artefact, not the number of lines this item adds. The starting point is counted from the file at registration time, so `--total 12` means "reach 12 lines". Reaching it marks the item `done` automatically.
- `--judge`: written into the prompt as criteria for the model; the tool never executes it.
- `set <id> [text]` can change `--total / --evidence / --pattern / --judge`, so a wrong path or regex does not mean rebuilding the queue.

State machine `todo → doing → done`, with `blocked` reachable at any time (carries a reason and takes no part in pushes).

## Commands

**Each command answers one question about the loop**, and the table names the question rather than the verb.

| Command | Purpose |
|---|---|
| `heartbeat.py` / `hook` | Stop hook entry, reads stdin |
| `payload` | print the JSON the hook received |
| `on [--session <id>]` / `off` | enable / disable (`off` silences immediately) |
| `bind` / `unbind <session>` | bind / unbind |
| `add` / `rm <id>` / `set <id>` | register, remove, retarget |
| `inc` / `sync` / `done` / `doing` / `todo` / `block` | record progress and change state; omitting the id acts on the current item |
| `list` / `sessions` / `exclude <id>...` / `doctor` | inspect and self-check |

Any command accepts `--as <session-id>` to declare the caller's identity (equivalent to `HEARTBEAT_SESSION`).

Exit codes: `2` usage error, `3` no such task, `4` artefact did not grow, request refused, `5` not bound (or `install` found no launcher).

## Configuration (`data/config.json`, defaults)

`enabled` false, `sessions` [], `exclude` [], `bindings` [], `max_nudge_per_chain` 200, `chain_gap_seconds` 1800 (a longer gap starts a new chain and resets the count), `stall_limit` 6, `max_age_hours` 24 (measured from the last progress, not the last push), `pre_nudge_check` "" (a shell command run before pushing; non-empty stdout is appended to the prompt).

## Data layout

Everything lives in this skill's `data/`, never in the project directory: `config.json`, `sessions.json` (sessions seen), `heartbeat.log` (nudge / hold / autoblock / error only), `tasks/<key>.json` (one queue per session).

## Boundaries

- Never across sessions; a queue per session.
- Never injected into a project running several agents in parallel.
- No scheduling: it only intervenes at the moment the session was going to stop anyway — use cron for exact timing.
- It does not replace `task-queue`: the queue owns "what is next" (a durable FIFO), the heartbeat owns "when the next thing is pushed at you".
- No judgement of content.

## Symptom → command

**Start from the symptom, not the verb**: the table maps what you are seeing to the one command that diagnoses it.

| Symptom | Command |
|---|---|
| Nothing happens at all | `doctor` (binding hit, task file present, hook registered) |
| No session id to bind | `sessions` (one Stop must have run first) |
| exit 5 unbound | `bind --session <id> --work <dir>`, or add `--as <session-id>` |
| `inc` exits 4 | the artefact did not grow: do the work, or `sync` to pull the real line count |
| The item was auto-blocked | `list` for the reason, `todo <id>` to re-enable |
| The hook looks installed but never fires | rerun `install`, then `doctor` |
