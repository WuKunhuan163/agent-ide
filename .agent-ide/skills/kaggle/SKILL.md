---
name: kaggle
description: >-
  Kaggle API helper for this repo: one Kaggle account per agent id, notebook
  push/pull/edit/monitor, live log streaming from a running kernel, dataset
  upload, Chrome-isolated notebook open. Read this skill when the user says a
  notebook finished or has results, when a notebook or dataset must be pushed to
  Kaggle, when progress of a running kernel must be read locally, when a Kaggle
  page must be opened, when a GPU notebook needs a human Run All, or when the
  user asks to check Kaggle quota/account state.
---

# kaggle

This skill exists so the agent never hand-writes `kaggle` CLI calls. It wraps
the official `kaggle` CLI, keeps one Kaggle account bound to one agent id, and
enforces contracts the raw CLI does not: the GPU anti-P100 protocol
(switchable via `config --gpu-interlock`), the
artifact-acceptance flow, and two passthrough refusals.

## What it is actually for

Five capabilities, in the order they get used:

| Capability | Command | Why the raw CLI is not enough |
|---|---|---|
| Bind one account to one agent | `config --status` / `--switch-user` | The CLI reads one global token file; this skill keeps a token pool and a per-agent binding, so two agents never fight over `~/.kaggle` |
| Turn a local folder into a run | `notebook push <dir>` | Nine gates before the API call: slug/hash resolution, placeholder expansion, GPU check injection, dataset-source validation, RUNNING-state refusal. The raw `kernels push` is refused outright precisely because it skips them |
| Watch a run | `status` / `logs` / `stream` | `status` reinterprets Kaggle's misleading states (a stale ERROR over a running log becomes `RUNNING`); `stream` is the only way to read a log while it is still running |
| Bring results back | `monitor` / Downloads-first acceptance | Artifacts land in a predictable local tree and zips are extracted in place |
| Avoid the P100 lottery | `config --gpu-interlock on` | API pushes send `enable_gpu=false`; the injected GPU guard then marks a CPU session `AWAITING_GPU_SELECTION`, and a human picks T4 x2 |

Everything below is detail on those five. If a task does not need one of them,
it probably does not need this skill.

## Entry point

Every invocation goes through the thin entry, which bootstraps the agent
context from `--id` and then dispatches:

```bash
python3 .agent-ide/skills/kaggle/kaggle.py --id <agent_id> <group> <verb> [args]
```

There is no `entry.sh` and no global pool binary. `--id` is mandatory and is the
agent's own id, not a Kaggle account; it may appear anywhere in the argument
list. When the top-level word is not one of the groups this skill owns
(`config`, `dataset`, `chrome`, `runtime`, `notebook`, `quota`), the call falls
through to the official CLI, but only past the two passthrough gates described
below. A missing `--id` exits 10; a missing group prints help and exits 11.

## Command surface

| Group | Verbs |
|---|---|
| `config` | `--status`, `--username <user>`, `--switch-user <user>`, `--token-file <path>`, `--verify`, `--gpu-interlock <on\|off>` |
| `dataset` | `find <query>`, `ls \| files <owner/slug>`, `create <folder> <title>`, `version <folder> -m <msg>` |
| `notebook` | `open`, `pull`, `edit`, `push`, `status`, `logs`, `stream`, `monitor` |
| `chrome` | `check` |
| `runtime` | `path [kind] [name] [--ensure]`, `ensure` |
| `quota` | `set <user> [--gpu <t>] [--tpu <t>]`, `show [--username <user>]` |

Anything else is passed through to the official `kaggle` CLI unchanged.

## The paths you will actually walk

**First deploy of a notebook.**

```bash
... config --switch-user <account>          # the account that owns the slug
... notebook push <dir> --no-open           # builds, gates, pushes, starts the run
... notebook status <slug>                  # RUNNING / QUEUED / AWAITING_GPU_SELECTION
... notebook stream <slug> --tail 20        # live log while it runs
```

**Poll progress without holding a connection.** `stream` replays from the
session start every call, so poll it on an interval rather than keeping one
open. Silence between arm boundaries is normal; the closing `[INFO] listened …`
line is what distinguishes "nothing new" from "stream broken".

**Re-deploy after a config change.** `push` mints a fresh six-character hash and
therefore a new slug, so the previous run keeps going and burns quota. Either
delete the old kernel (`kernels delete <user>/<slug> -y`, which also cancels its
run) or pin the slug with `--no-hash`.

**Collect results.** `monitor` downloads and extracts; on a GPU-interlock ledger
it refuses, because a human Run All is what starts the run. When the user says a
notebook finished, look in `~/Downloads` for `results_*.zip` first — `status`
can still read `AWAITING_GPU_SELECTION` after the user already ran it.

**Upload the weights once.** `dataset create <folder> <title>` then
`dataset version <folder> -m <msg>`; both keep `isPrivate: true` and refuse the
mistakes the raw CLI leaves to you.

## Accounts: agent id vs Kaggle username

The agent id and the Kaggle account are independent. An agent binds exactly one
account, and the binding lives in `data/agents/<agent_id>/config.json`:

```json
{ "username": "<kaggle_username>" }
```

Tokens are shared, not per-agent: they sit in
`data/accounts/<kaggle_username>/kaggle.json`, stored `0600`. Registering a
downloaded `kaggle.json` copies it into that pool and binds the agent to it.

```bash
python3 .agent-ide/skills/kaggle/kaggle.py --id <agent_id> config --status
python3 .agent-ide/skills/kaggle/kaggle.py --id <agent_id> config --token-file ~/Downloads/kaggle.json
python3 .agent-ide/skills/kaggle/kaggle.py --id <agent_id> config --switch-user keffwu
python3 .agent-ide/skills/kaggle/kaggle.py --id <agent_id> config --verify
```

`--status` prints the agent id, the bound account, the accounts available on
disk, and whether a token is present. `--token-file` does **not** touch the
network: it registers the token, and live verification is the separate
`--verify` command, which probes the API with a one-line read-only request.
`--username` records a username without a token and without validating it;
`--switch-user` requires a token to already exist for that account and exits 21
otherwise. With no flag at all, `config` dumps the raw config file.

There is no per-command `--account` override; account resolution is
deterministic — bound account first, then the only token on disk (which is then
auto-bound), otherwise an error telling you what to run. When an agent has no
bound account and nothing on disk, `resolve_username` opens the Kaggle API
settings page once in the isolated Chrome profile so the human can create a
token, then raises `AUTH_NO_ACCOUNT` (20). Several tokens on disk and no binding
is also 20, with the list of candidates.

## Dataset group

```bash
... dataset find "<query>"            # remote search: datasets list -s
... dataset ls <owner/slug>           # remote file listing; alias: files
... dataset create <folder> <title>
... dataset version <folder> -m "<message>"
```

`create` and `version` enforce rules the raw CLI leaves to you. A folder above
100 GiB is refused up front (code 33) rather than left to the CLI's automatic
multipart path. `dataset-metadata.json` is created or repaired on the way
through: it always carries `id = <username>/<slug>`, `isPrivate: true`, and a
default license of `CC0-1.0`. `create` appends a timestamp to the title so
repeated uploads do not collide. `version` requires `-m`, refuses when the
folder has no metadata, and refuses when the metadata's owner is not the account
the agent is bound to — in that case it tells you to run
`config --switch-user <owner>` first.

Uploads always use `--dir-mode zip`.

Note that `dataset create` slugifies the folder name with a laxer rule than the
notebook refs use: characters other than spaces/underscores survive. Do not
assume the uploaded slug equals the notebook-style slug.

`sync_local_dataset(folder, username, token)` is the same logic without a CLI
verb; `notebook push --local-dataset` calls it and writes the returned
`owner/slug` into `dataset_sources`.

## Notebook group

Verbs: `open`, `pull`, `edit`, `push`, `status`, `logs`, `stream`, `monitor`.

A notebook can be named three interchangeable ways — `user/slug`, `user:slug`,
or a bare `slug`. A bare slug is resolved through the event log for `open`
(unique owner wins, ambiguous is refused, unknown is refused with "push it
first"), and through the bound account for the other verbs.

### open

```bash
... notebook open <slug>
```

Runs `chrome check`-style preflight, then launches the isolated Chrome profile
at `https://www.kaggle.com/code/<user>/<slug>/edit`.

### push

```bash
... notebook push <dir> [--local-dataset <path>]... [--remote-dataset <owner/slug>]... \
    [--auto-download [dir]] [--no-open] [--force-push] [--no-hash]
```

Push is the single deploy path; a first deploy and a hotfix go through the same
pipeline, in this order:

1. Load `kernel-metadata.json`, backfill the defaults the CLI would reject
   (language, privacy, empty source lists), and pick `code_file` — `main.ipynb`
   if present, else `main.py`. Neither present is exit 11. The title must be at
   least 5 characters, every `dataset_sources` entry must be a legal
   `owner/slug`, and an `.ipynb` must be valid JSON.
2. Resolve the three placeholders `<NOTEBOOK_HASH>`, `<KAGGLE_USERNAME>`,
   `<BUILD_TS>` in the metadata and in the code. A fresh six-hex-character hash
   is generated per push and replaces any existing `-<hash>` suffix on the
   title, so each deploy is a new slug by default. Any placeholder left
   unresolved refuses the push. `--no-hash` skips generation **and** the hash
   placeholder — the slug then stays the same as the previous push.
3. Inject the GPU CHECK assertion when authoring `enable_gpu` is true: the
   notebook is expected to fail loudly on a CPU session, which is what marks it
   `AWAITING_GPU_SELECTION` later instead of a real failure. Injection is
   best-effort and only warns on failure.
4. Print the preflight checklist. Then, if the notebook reads `/kaggle/input`
   but `dataset_sources` is empty, refuse unless `--force-push`.
5. Refuse a push while the recorded state of that notebook is `RUNNING`, unless
   `--force-push`. If the ledger entry belongs to a different account, that is
   warned about but not blocked.
6. Push. The authoring metadata keeps `enable_gpu=true`, and what reaches the
   API depends on the **GPU interlock** (`config --gpu-interlock <on|off>`,
   default `on`). On: the API layer is pushed with `enable_gpu=false` — the
   anti-P100 protocol — the injected GPU CHECK marks the CPU session
   `AWAITING_GPU_SELECTION`, and the human picks T4 x2 then Run All. Off: the
   API layer is pushed with `enable_gpu` as authored, Kaggle starts the run
   itself on its default accelerator, and `monitor` may poll it. A raw
   `kernels push` probe with `enable_gpu=true` (2026-10-17) landed on 2 x Tesla
   T4 and no P100, which is why this guard is now a switch rather than
   unconditional. The authoring metadata is restored afterwards either way.
7. Pull the pushed metadata back and warn if any `dataset_source` did not land.
8. Print the post-push guidance (slug, the `notebook open` command, the
   acceptance steps) *even when the push exits non-zero*, because a non-zero
   exit here is often just the GPU guard on a CPU session.
9. Record the run in `state.json` (`RUNNING`, or `PUSH_EXIT_<code>`) with the
   `requires_user_gpu` flag, and append to `event_log.json`. Then optionally
   hand off to `monitor` (`--auto-download`, CPU notebook only — a GPU ledger
   skips it) or `open` (the default on exit 0; suppress with `--no-open`).

A failed push returns 32, an owner mismatch 31. Both still print the guidance.

### pull / edit

```bash
... notebook pull <slug> [-d <dir>]
... notebook edit <slug> <patch.json> [--enable-gpu] [--append-cell <code>]
```

`pull` downloads the source and metadata. Without `-d` it lands in a fresh
folder under `notebooks/` named `<slug>-<timestamp>-<hex8>`, so a pull never
overwrites an earlier snapshot.

`edit` is a pull, a patch and a push in one step: it applies a JSON array of
`[old, new]` string pairs (first match replaced; a pair that does not match only
warns), optionally appends a cell, prints a unified diff, then pushes back to
the *same slug* (`assign_id=False`, `no_hash=True`, `force_push=True`). It
handles both `kernel_type` values: an `.ipynb` gets a new trailing code cell, a
`.py` script gets the code appended under a comment marker. `--enable-gpu`
rewrites the authoring metadata's `enable_gpu` to true, which is how a GPU
notebook gets declared without a full re-deploy.

### status / logs / stream / monitor

```bash
... notebook status <slug>
... notebook logs <slug> [-f|--follow]
... notebook stream <slug> [--timeout 20] [--grep <regex>] [--tail <n>]
... notebook monitor <slug> [-d <download_dir>] [--no-logs]
```

`status` reads the kernel state and classifies it before reporting. The
classification is deliberately forgiving, because Kaggle's own answers are
misleading in two common cases: a stale `ERROR` left by an earlier CPU session
while the log shows training progressing is reported as `RUNNING`, and a
notebook that hit its own CPU-only guard is reported as `AWAITING_GPU_SELECTION`
with a banner telling the human to pick T4 x2 and Run All. A real `ERROR`
returns code 35; everything else, including `AWAITING_GPU_SELECTION`, returns 0.
A 404 is read as `QUEUED`; 401/500 fall back to reading the log.

`status` also prints when the run started and how long it has been going:

```
keffwu/kolors-front-logo-fe3f5d has status "RUNNING"
  started 2026-10-23 09:44:39 UTC+08:00 · running 00:26
```

The second line exists because **Kaggle reports `lastRunTime` in UTC and says so
nowhere**. Read as local time, a 26-minute run looks like an 8-hour stall — that
mistake has already been made once. The clock is stamped UTC at parse time and
converted only afterwards; the offset is printed so a screenshot cannot be
misread again.

`logs` prints the kernel log, unwrapping the JSON log envelope, and tolerates
the 404 a just-pushed kernel returns while it is still registering.

`stream` is the only way to read a log **while the kernel is still RUNNING**.
`kaggle kernels logs` reads the finished session and returns an empty body until
then; `stream` goes to the midtier SSE endpoint instead:

    GET https://www.kaggle.com/api/v1/kernels/logs/stream/{owner}/{slug}

with the account's kaggle.json as basic auth. Two properties decide how to use
it. **It replays from the session start on every call** — the command reads
"the log so far", it does not resume a cursor, so callers poll it rather than
holding one connection for an hour. **Silence is normal** — a notebook that
prints only at arm boundaries looks idle for minutes, so the command always ends
with a line stating how long it listened and how many events arrived, which is
what separates "nothing new" from "stream broken". `--timeout` bounds the listen
(default 20 s), `--grep` filters, `--tail n` buffers and prints only the last n
matching lines. A 404 means the kernel has no session yet and returns 0, like
`logs`; 401 returns 22, while 403 is reported as a possible missing/private
slug *or* a stale token (Kaggle answers the same code for both), so it returns 52.

Polling pattern: `stream --tail 5` every minute or two, rather than one long
connection. Note that a notebook which prints nothing between arms produces no
new events, so the absence of lines is not evidence of a stall — check `status`
alongside it.

`monitor` polls the status (5s while running, 10s before it starts) while
streaming `logs -f` (unless `--no-logs`), and once the run reaches `COMPLETE`
downloads the artifacts through the whitelisted `kernels output` path into
`runtime/output/<slug>` (or `-d`) and extracts any zips in place. It refuses
GPU-ledger notebooks outright (code 12) — while the interlock is `on`, because
then a human Run All is what starts the run; with the interlock `off` the ledger
no longer means that and the refusal does not fire — and tells the agent to stop monitoring
and align with the human instead — a GPU notebook needs a human Run All, so
polling it is pointless.

### The Downloads acceptance flow

When the user says a notebook has finished, the agent's first move is *not* to
query the API — `status` lies in the `AWAITING_GPU_SELECTION` case after the
user already ran it. The flow is: look in `~/Downloads` for the `results_*.zip`
/ `logs_*.zip` the browser produced, unzip and parse those, and only fall back
to the API (`kernels files`, then the reserved `kernels output`) when
Downloads is empty. Artifacts land under
`data/agents/<agent_id>/runtime/output/`. Never ask the user to download an
artifact by hand unless a download genuinely failed after retries; in that case
report the failure and the exact command so the user *may* run it.

## chrome group

```bash
... chrome check
```

Read-only. It prints a verdict for the Chrome profile — whether it is corrupt,
whether the log tail looks corrupt, which Chrome processes hold it, where the
log is, and the suggested action — and returns 41 when a manual fix is needed.
It never launches Chrome and never modifies the profile. The agent runs it
before any `notebook open`.

Opening a page always goes through an isolated profile: `notebook open` calls
`preflight_chrome_open(account)` and then launches Chrome against
`data/accounts/<kaggle_user>/chrome_profile`. The cold-start settings page uses
the agent-level profile (`data/agents/<id>/chrome_profile`). There is no
fallback to the system browser: a missing Chrome or a spawn conflict is a hard
`BROWSER_FAILED` (40), not a silent swap. Never open a Kaggle link with a bare
`open`/`xdg-open`.

## runtime group and the data layout

```bash
... runtime path [root|deploy|output|logs] [name] [--ensure]
... runtime ensure
```

`path` resolves and prints a path without touching the network; the kind
defaults to `root`, and `--ensure` creates it. `ensure` creates the whole tree.

Everything the skill writes for an agent hangs off `data/agents/<agent_id>/`:

- `config.json` — the account binding.
- `state.json` — the notebook ledger, keyed by `user/slug`, holding `status`,
  `updated_at`, `requires_user_gpu`, plus the `quota` block.
- `event_log.json` — append-only audit records of
  `{timestamp, username, action, target}`; this is also what backs the bare-slug
  owner lookup.
- `notebooks/` — pull snapshots.
- `runtime/` — `deploy`, `output`, `logs`.

Replicas of the pre-per-agent `global_state.json` / `event_log.json` are
migrated into the agent dir on first read.

## quota group

```bash
... quota set <kaggle_user> [--gpu <time>] [--tpu <time>]
... quota show [--username <kaggle_user>]
```

This is a local ledger of remaining GPU/TPU time, recorded by hand in
`state.json`; Kaggle exposes no API for it. Both values **default to `0m`** when
omitted, so pass them explicitly. Times accept `29h50m`, `1790m`, `29h`, `45`
and similar forms. `show` prints one account or all.

## Passthrough and the two contracts

Anything the skill does not own is handed to the official CLI as-is. There is
no per-family verb whitelist to maintain — but exactly two named contracts
stand in front of it:

1. **`kernels push` is refused.** It is the one forbidden verb, because
   pushing through the raw CLI would bypass the push gates that only
   `notebook push` implements — the GPU protocol among them. Turning the
   interlock `off` changes what those gates do, not whether they exist: the
   refusal stands either way. It points the agent at
   `notebook push` / `notebook edit`.
2. **`kernels output` is reserved for `monitor`.** A routine call is refused;
   the only sanctioned caller is `monitor`'s artifact recovery. A human who
   really means it can pass `--allow-output` or set `KAGGLE_ALLOW_OUTPUT=1`.

Every other passthrough command — `datasets download`, `competitions list`,
`models list`, and so on — runs unchanged. Both refusals raise
`BLOCKED_BY_CONTRACT` (12) with the reason and the correct command.

## Credentials, retries, limits

The token the CLI runs with comes from `data/accounts/<user>/kaggle.json`, or
from `KAGGLE_CONFIG_DIR` / `KAGGLE_USERNAME` / `KAGGLE_KEY` if already set in
the environment. If the `kaggle` executable is missing the call exits 50; a
timed-out or otherwise failed child process exits 51 or 52.

Retrying is intentionally shallow: only HTTP 409 is retried, three attempts,
five seconds apart. Authentication failures are classified as 22, an exceeded
quota as 34, everything else non-zero as 52. 404/500/401 during notebook
observation are handled by the observation layer instead (see `status`), not by
retries.

## Exit codes

`0` ok · `10` no agent id · `11` usage · `12` blocked by contract ·
`20` no account / `21` token missing / `22` auth rejected ·
`31` push owner mismatch / `32` push failed / `33` dataset too large /
`34` quota exceeded / `35` kernel failed ·
`40` browser failed / `41` browser profile corrupt ·
`50` kaggle CLI missing / `51` exec timeout / `52` exec failed.

Every command returns one of these; nothing exits 0 silently. Authentication
failures (22) carry a recovery message that names the token path and the
re-register command.

## Interaction with other skills

`contact-user` is the channel for anything that needs the human: a GPU notebook
waiting on Run All, a corrupt Chrome profile, a quota wall, or the report that a
notebook finished. The `kaggle` skill never opens a chat panel of its own.
