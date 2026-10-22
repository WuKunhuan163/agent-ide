---
name: contact-user
description: >-
  Blocking user channel for this repo: the agent writes two input files, the user answers in a GUI window, the CLI prints the reply, and the round is archived and checkpointed.
---

# contact-user

The user is reachable only through this tool. The IDE chat panel is not the channel.

## A round

```bash
# 1. read the session the agent is about to report on (unlocks the round)
.agent-tools/contact-user --id <id> --ide-context

# 2. write both files (non-empty; whitespace-only counts as empty)
#    data/input/contact_msg_<id>.txt   what the user reads
#    data/input/commit_msg_<id>.txt    the git checkpoint message

# 3. block for the reply — its own command, never chained with step 2
.agent-tools/contact-user --id <id>
```

Step 3 prints the user's reply on stdout; continue the **same turn** from it. Then act on the reply and open the next round at step 1.

Step 1 is enforced: without a session token newer than the previous round, step 3 prints why and exits `7` without opening a window. The token is written by `--ide-context`, and only by an **unfiltered, on-stdout** one:

- `--conversation` narrows the read; the token records the scope and the round stays locked.
- `--out FILE` exports the same text but mints **no** token — a file cannot stand in for the text the agent reads, and the report would otherwise open unseen.
- A token whose window held 0 messages does not count either.

The output itself is plain UTF-8 text (no JSON envelope, no escapes, no colour), one block per message, so nothing between the store and the agent rewrites it.

Input files are consumed before the window opens and archived. After a git failure (exit 40) rewrite both before re-contacting.

## Reading back

```bash
.agent-tools/contact-user --id <id> --recent 20   # last N rounds, oldest first
```

`--recent` ends with **# latest directive** (the newest non-empty reply). That is the binding instruction; earlier rounds are reference. When `rounds` exceeds `selected`, raise N. Do not pipe it through `head`/`tail` — redirect to `/tmp/` and read in full if length is a concern.

Use it when a write/contact pair looks lost, when the user says context was missed, or after a round delivered a reply without being archived (active-session path). It is a supplement, not a substitute for lost mid-task context: if the round has to establish what to continue and that context is gone, stop and ask (see `collaboration` §3).

## Data layout

| Path | Meaning |
|---|---|
| `data/input/{contact,commit}_msg_<id>.txt` | drafts for the next round; consumed before the window opens |
| `data/contact_msg/<id>/<ts>_contact_msg.txt` | archived agent message |
| `data/user_response/<id>/<ts>_user_response.txt` | archived user reply |
| `data/locks/<id>.lock` | pid of the round in progress |
| `data/locks/<id>_handshake.txt` | how the window reported its outcome |
| `data/autosave/<id>/autosave.txt` | unsubmitted draft, restored on the next open |
| `data/window/<id>/geometry.txt` | last window size/position |
| `data/last_round/<id>.json` | start of the next `--changes` window |
| `data/session_context/<id>.json` | session token (proof of the pre-report read) |
| `data/session_mirror/` | separate git repo with the mirrored transcript |
| `data/config.json` | `session_history_root`, `session_ide`, `session_mirror_enabled` |

`data/` is never tracked by git. The two archives are also copied, append-only, outside the project after every delivered round — the shard comes from `replicas.root` in `skill.json` (`agent-ide replicas status` shows it, `agent-ide replicas sync` repairs a gap). Losing `data/` must not lose the conversation record.

## Session store

The IDE keeps its conversation on disk; the agent reads it from there, so a compaction cannot take the context away.

First start — pin the path, nothing is auto-detected at read time:

```bash
.agent-tools/contact-user --detect-history-root                    # `ide<TAB>path` candidates
.agent-tools/contact-user --set-history-root /abs/path/to/history  # validate + pin
.agent-tools/contact-user --id <id> --session-status               # confirm
```

Reads (each has a flag; never write inline `python3 -c` against `src.*`):

| Question | Flag |
|---|---|
| what happened since the previous round | `--changes [MAX] [--conversation C]` |
| everything, untruncated (unlocks a round) | `--ide-context [--until W] [--out FILE]` |
| which conversations exist, how big | `--session-list [N] [--since W] [--json]` |
| one conversation, in full | `--session-read <id\|prefix\|latest> [--full] [--json]` |
| messages per month | `--session-months [--exact]` |

Window bounds are `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`, `YYYYMMDD_HHMMSS` or an epoch; naive values are local time. `--out FILE` writes exactly the same text as stdout would.

Output is data on stdout and one-line notes on stderr (`contact-user: ...`):

```
# since=<ts> convs=1 msgs=198      <- read header
## <conversation> 198 msgs
### [18:10:45] assistant           <- one block per message

2026-10-22 10:10   12042  <conv>   <- --session-list: last msgs [text reason tools] conv
2026-10   89102                    <- --session-months
ide=codebuddy convs=76 msgs=137612 size=1.5G ...   <- --session-status
```

`--changes` is the compact orientation view (capped, tool payloads hidden) and never unlocks a round. `--ide-context` is the report view: every message, reasoning and tool output untruncated. `--json` replaces all of the above with one object per command.

## Transcript mirror

After every round the parsed store is mirrored into `data/session_mirror/` — one JSONL per conversation plus `index.json` — and committed there. It is a separate repository because `data/` is git-ignored by the project, so transcript history never enters the project checkpoint.

```bash
.agent-tools/contact-user --sync-session    # force a sync (incremental)
.agent-tools/contact-user --session-log 10  # mirror commits
```

Syncs are incremental: `index.json` holds the last mirrored timestamp and the tail of message ids. Mirroring and the round marker are auxiliary — a failure warns on stderr and never fails a delivered round.

## ID maintenance

Rounds are archived per agent id. To move rounds between ids (time-bounded):

```bash
.agent-tools/contact-user --merge-into <target> --sources <id> [...] \
    [--start-time YYYYMMDD_HHMMSS] [--end-time YYYYMMDD_HHMMSS]
.agent-tools/contact-user --delete-id <id>      # to the trash, not deleted outright
```

The id is chosen by the user and is **not** the project folder name. Resolve it in this order: the current message → the session context → an id already under `data/contact_msg/` (prefer an existing one; ask if several) → `contact-user resolve` (project basename) only when none exists.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 2 | malformed invocation | fix the flags |
| 3 | blank id-valued option | pass a real id |
| 4 | five windows, no reply | the user closed them; re-contact when appropriate |
| 7 | no session token | run `--ide-context` first |
| 10–13 | contact/commit file missing or whitespace-only | rewrite both |
| 20–21 | merge arguments invalid | fix `--merge-into`/`--sources` |
| 40 | git checkpoint failed | round archived but not committed; rewrite both files |

## Language

Contact the user the way the `collaboration` skill prescribes (`.agent-ide/skills/collaboration`). If that skill is missing, ask the user for the desired manner in the first round.
