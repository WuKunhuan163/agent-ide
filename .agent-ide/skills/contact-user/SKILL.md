---
name: contact-user
description: >-
  Blocking user channel for this repo: the agent writes two input files, the user answers in a GUI window, the CLI prints the reply, and the round is archived and checkpointed. Also the only way to read the IDE conversation: when the user asks "what did you just do", "read the full context", "看看语境", the first command is `.agent-tools/contact-user --id <id> --ide-context`.
---

# contact-user

The user is reachable only through this tool. The IDE chat panel is not the channel.

## Reading the conversation — start here

`--ide-context` *is* the context read. When the user asks about the context, the
session, or what the agent just did, the first command is always:

```bash
.agent-tools/contact-user --id <id> --ide-context [ROUNDS]
```

Do not explore for it first. Specifically, none of these is a step toward the
context:

- `ls data/` / `cat data/config.json` — `data/` holds drafts, delivered-round
  archives, locks and tokens. It is empty on a fresh checkout and never
  contains the conversation itself.
- `--help` — the flags are documented below.
- `--detect-history-root` / `--set-history-root` — first install only, or after
  `--ide-context` fails by saying there is no history root. Running it as a
  warm-up costs calls and delays the read.

Choosing the arguments:

- Unknown budget: use the default (last 100 rounds). Raise it (`--ide-context
  300`) when the work spans more; do not estimate by grepping the output.
- Unknown id: `.agent-tools/contact-user resolve` prints it. Look for an id
  under `data/contact_msg/` only when `resolve` is clearly wrong.
- The read is large in a long session (hundreds of messages, megabytes). If it
  will not fit, write it once with `--out /tmp/ctx.txt` and read that file in
  pieces — but `--out` mints no token, so a report round still needs the
  unfiltered on-stdout read.
- For the last few turns only, use `--recent N` (archived rounds, ends with
  `# latest directive`) rather than slicing the full read with `grep`/`tail`.
  The full read is for reconstructing what happened; `--recent` is for the
  current instruction.

## Bound conversation

An agent id and a conversation id can be registered as one pair, so later reads
use that conversation without repeating `--conversation`:

```bash
.agent-tools/contact-user --id <id> --bind-conversation <conv>   # once
.agent-tools/contact-user --bindings                             # what is registered
.agent-tools/contact-user --id <id> --unbind-conversation        # drop it
```

`<conv>` may be a full id, an id prefix, or `latest`; the full id is what gets
stored. The table lives in `data/config.json` under `conversation_bindings`.

A bound read is the whole of that id's context, so it reports `scope=all`,
prints the `report anchor:` line and unlocks the round — same as an unfiltered
read. An explicit `--conversation` still narrows and stays locked. Binding
fails when the conversation is not in the pinned store, and `--bindings` marks
a stored pair `(missing)` once it disappears.

The binding chooses *which* conversation, not how much of it: `--ide-context`
still reads its last ROUNDS rounds, so pass `--since` when the whole history is
wanted.

## A round

```bash
# 1. read the session the agent is about to report on (unlocks the round)
#    the last line it prints is this round's anchor:
#    report anchor: 1d79f89f · 24 msgs
.agent-tools/contact-user --id <id> --ide-context

# 2. ask for the two draft paths, then write exactly there
#    (`contact<TAB><abs path>` / `commit<TAB><abs path>`)
.agent-tools/contact-user --id <id> --input-path

#    never assemble `data/input/...` yourself: a relative path resolves against
#    the shell's cwd, and some other project's `data/` silently takes the draft.
#    contact_msg.txt  what the user reads — must carry the anchor line printed
#                     by step 1, verbatim
#    commit_msg.txt   the git checkpoint message
#    both non-empty (whitespace-only counts as empty)

# 3. block for the reply — its own command, never chained with step 2
.agent-tools/contact-user --id <id>
```

Step 3 prints the user's reply on stdout; continue the **same turn** from it. Then act on the reply and open the next round at step 1.

Step 1 is enforced twice: without a session token newer than the previous round, step 3 prints why and exits `7` without opening a window; and the draft must quote the token's anchor (`report anchor: <digest8> · <n> msgs`, taken from the end of the read), or step 3 exits `7` and prints the exact line to add. The digest covers the printed window, so a report written from memory, or one whose read was piped into `head`, cannot supply it.

The token is written by `--ide-context`, and only by an **unfiltered, on-stdout** one:

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

## Journal

A long-running id accumulates thousands of rounds. `--archive` writes one markdown file from a slice of them and **changes nothing on disk**; `--prune` is the only command that moves rounds out of the archive. Exporting never deletes, because the archive is the sole record a compressed session leaves behind.

```bash
.agent-tools/contact-user --id <id> --archive /path/journal.md [--summary FILE] [--tail 5] [--since W] [--until W] [--title T]
.agent-tools/contact-user --id <id> --prune [--tail 5] [--since W] [--until W]
```

Both use the same window: `--since` / `--until` bound the rounds by time, `--tail` (default 5) keeps the newest rounds untouched, and anything outside the window is left alone. The two flags are mutually exclusive — one writes, the other deletes, and they are never run as one act.

The file holds a title, a header comment naming the id and range, `## Summary` (the `--summary` file body, or a placeholder), then `## Raw Context` with paired `### Agent Prompt N` / `### User Response N` blocks. A leading `#` inside archived text is escaped, so a quoted heading cannot restructure the document.

`--prune` moves the selected rounds to `~/.Trash/<id>_contact_archive_<ts>/` (falling back to `data/trash/`), two files per round. Write the summary for this slice only — it is the part a future reader uses.

## Data layout

Every `data/...` below is relative to this skill's own folder (`.agent-ide/skills/contact-user/`), never to your shell's cwd. Nothing under `data/` is a source of context: it holds drafts for the next
round, archives of rounds already delivered, locks, and tokens. A context read
starts at `--ide-context`, never with `ls` on this tree.

| Path | Meaning |
|---|---|
| `data/input/{contact,commit}_msg_<id>.txt` | drafts for the next round; consumed before the window opens |
| `data/contact_msg/<id>/<ts>_contact_msg.txt` | archived agent message |
| `data/user_response/<id>/<ts>_user_response.txt` | archived user reply |
| `data/locks/<id>.lock` | pid of the round in progress |
| `data/locks/<id>_handshake.txt` | how the window reported its outcome |
| `data/autosave/<id>/autosave.txt` | unsubmitted draft, restored on the next open |
| `data/window/<id>/geometry.txt` | last window size/position |
| `data/last_round/<id>.json` | when the previous round ended; an older read is refused |
| `data/session_context/<id>.json` | session token (proof of the pre-report read) |
| `data/session_mirror/` | separate git repo with the mirrored transcript |
| `data/config.json` | `session_history_root`, `session_ide`, `session_mirror_enabled`, plus the window settings below |

`data/` is never tracked by git. The two archives are also copied, append-only, outside the project after every delivered round — the shard comes from `replicas.root` in `skill.json` (`agent-ide replicas status` shows it, `agent-ide replicas sync` repairs a gap). Losing `data/` must not lose the conversation record.

## Window settings

The window's layout and the bell live in `data/config.json`, not in code:

| Key | Default | Meaning |
|---|---|---|
| `window_geometry` | `360x280` | opening WxH, optionally `+X+Y`; without a position the window opens flush with the top of the screen, horizontally centred. Once the user resizes or moves the window, both size and position are remembered per agent id in `data/window/<id>/geometry.txt` and win over this default |
| `window_font` | `Arial` | editor font family |
| `window_font_size` | `14` | editor font size |
| `window_rows` | `15` | editor height in text rows |
| `bell_interval` | `90` | seconds between bells while the window waits; `0` rings once and stops |
| `autosave_ms` | `1000` | draft autosave period; `0` saves only on change and on close |
| `gui_attempts` | `5` | windows a round opens before it gives up (1..10) |

A value that cannot be used falls back to its default, so a typo costs no reply. Missing keys are filled from the same defaults the next time the file is saved.

## Session store

The IDE keeps its conversation on disk; the agent reads it from there, so a compaction cannot take the context away.

First start — pin the path, nothing is auto-detected at read time. This is a
one-time setup step, not a probe to run before a context read; `--ide-context`
itself says when the root is missing:

```bash
.agent-tools/contact-user --detect-history-root                    # `ide<TAB>path` candidates
.agent-tools/contact-user --set-history-root /abs/path/to/history  # validate + pin
.agent-tools/contact-user --id <id> --ide-context 5                # confirm (five rounds)
```

One read: `--ide-context [ROUNDS]`, untruncated, and the only read that unlocks a round.

A round is one user message and everything that follows it. The window is
counted in rounds, not in time: the default is the last 100 rounds, and a project
left untouched for a week reads the same window as one read an hour ago. The
count is a floor, not a cap — pass a larger number when the work spans more
(`--ide-context 300`). `--since W` replaces the count with an explicit start
(`YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`, `YYYYMMDD_HHMMSS` or an epoch; naive values
are local time). `--out FILE` writes exactly the same text as stdout would.

Output is data on stdout and one-line notes on stderr (`contact-user: ...`):

```
# since=<ts> convs=1 msgs=198      <- read header
## <conversation> 198 msgs
### [18:10:45] user                <- one block per message
### [18:10:52] assistant
### [18:10:53] tool
```

Every message, reasoning, tool call and tool output is printed in full: there is
no compact substitute and no cap, because a summarized window is what makes a
report drift from what was actually said.

## Transcript mirror

After every round the parsed store is mirrored into `data/session_mirror/` — one JSONL per conversation plus `index.json` — and committed there. It is a separate repository because `data/` is git-ignored by the project, so transcript history never enters the project checkpoint.

This is a core feature, not an extra: it is what lets an agent recover the conversation when the IDE store is rotated, the session is compacted away, or a report has to be based on what was actually said. Keep it. The mirror is also what `--recent` reads, so archived rounds survive without depending on the live store still being where it was yesterday.

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
| 7 | no session token, or the draft does not quote the read's anchor | run `--ide-context`, then add its `report anchor:` line to the draft |
| 10–13 | contact/commit file missing or whitespace-only | rewrite both |
| 20–21 | merge arguments invalid | fix `--merge-into`/`--sources` |
| 40 | git checkpoint failed | round archived but not committed; rewrite both files |

## Language

Contact the user the way the `collaboration` skill prescribes (`.agent-ide/skills/collaboration`). If that skill is missing, ask the user for the desired manner in the first round.
