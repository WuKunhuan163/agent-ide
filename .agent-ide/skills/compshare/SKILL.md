---
name: compshare
description: Compshare (UCloud) GPU instance CLI: stock, price, power, create, watchdog. Stock must go through CheckCompShareResourceCapacity — the only officially recognised sellable check.
---

# compshare

## Entry (read this first)

`.codebuddy/skills/compshare/SKILL.md` is a **symlink**; the real package sits at `.agent-ide/skills/compshare/` in the same project. Package layout: `SKILL.md` · `compshare.py` (entry) · `src/` · `panel/` · `data/`. The three notes that used to live in `docs/` (return codes, billing, no-card mode, state verdicts) now sit in the docstring of the code they govern: the return-code table at the top of `src/client.py`, the billing and no-card semantics in the `BILLING` comment in `compshare.py`, and the state and port verdicts in `_verdict` / `_probe_tcp` / `_channels`. **`data/` lives in the package directory, not under `.codebuddy`**; from the `.codebuddy` side you only see documents, which is normal and not a missing file.

There is exactly one way to run it: the project launcher. The interpreter path is baked in; it depends on neither PATH nor the system python.

```bash
.agent-tools/compshare zones
```

If the launcher is missing, install it first (one line, idempotent):

```bash
.agent-tools/agent-ide install compshare
```

**Do not run `compshare.py` with the system `python3`.** The local `python3` is 3.14 (Homebrew) without CA certificates, and every endpoint fails with `SSL: CERTIFICATE_VERIFY_FAILED`. To use an interpreter explicitly:

```bash
PKG=$(python3 -c 'import pathlib;print(pathlib.Path(".codebuddy/skills/compshare/SKILL.md").resolve().parent)')
/Users/wukunhuan/agent_ide_global_project/.agent-ide/runtime/standalone/python/darwin-arm64/python3.11/bin/python3.11 \
  "$PKG/compshare.py" zones
```

When the project has no package at all, pull it from the global project:

```bash
<global>/.agent-tools/agent-ide push --from-global --project <this project> compshare
<global>/.agent-tools/agent-ide install        --project <this project> compshare
```

`<global>` defaults to `~/agent_ide_global_project`. `data/` is per-machine state and **does not travel with the package**; after moving to another project you still place `credentials.json` yourself.

## What this is

The UCloud-style API behind Compshare: `POST https://api.compshare.cn`, form-urlencoded, with `Action` + `PublicKey` + `Signature` (parameters sorted by key, concatenated as `key+value`, PrivateKey appended, SHA1). One subcommand is one action; one line of output per record.

## Credentials

Source: `console.compshare.cn` → account centre → API keys → `https://console.compshare.cn/uaccount/api_manage`. The page gives **two values**: public key and private key (shown once). A single `sk-`-prefixed API key belongs to the model API and cannot be used here.

```bash
mkdir -p data && chmod 700 data
printf '{"public_key":"...","private_key":"..."}\n' > data/credentials.json
chmod 600 data/credentials.json
```

Precedence: `--public-key/--private-key` > environment `COMPSHARE_PUBLIC_KEY` / `COMPSHARE_PRIVATE_KEY` > `data/credentials.json`.

With no key, any subcommand **opens the key page** and exits 20; `--no-open` or `COMPSHARE_NO_OPEN=1` disables that (the panel and `watch` must disable it, or they steal focus every minute).

## Commands

```bash
compshare zones                                    # regions
compshare images [--grep cu128] [--raw]            # platform images; --raw prints one record to inspect fields
compshare types --gpu <card> [--zone cn-wlcb-01]     # legal CPU/memory combinations
compshare stock --gpu <card> [--cards 1] [--image <id>] [--all] [--zone <zone>]
compshare quote --gpu <card> --cards 1 --cpu 16 --mem-gb 64 --image <id> \
                [--region cn-wlcb] [--zone cn-wlcb-01] [--charge Postpay]
compshare ls [--running] [--ids]                   # instance list (complete, paginated)
compshare info <uhost-id>                          # current state: spec / IP / ssh reachable / watchdog
compshare exec <uhost-id> 'CMD' [--wait 120] [--init-grace 300] [--pipefail]  # run on the instance, pass the exit code through
compshare health <uhost-id> [--no-probe]           # 3-second verdict "usable now": 0 usable / 30 broken / 31 stopped
compshare ready <uhost-id> [--timeout 180] [--init-grace 180]  # wait until usable; exits at once if the card is initialising
compshare verdicts [--stale 24]                      # read-only: last verdict + how often it broke; --stale filters return candidates
compshare pool status|fill|grab|release-broken       # card pool: gap in usable cards / fill plan / grab a card / clear broken machines
compshare card <id> --kolors ready --smoke ok        # record config and smoke result (what makes a card usable)
compshare release <id> [--yes] [--keep-udisk]        # return it: both disks go; without --yes only the plan is printed
compshare pick [<id> ...]                            # read-only: one line per machine, for a human decision
compshare ssh-setup <uhost-id>                     # once: install the key + write the ~/.ssh/config alias
compshare ssh <uhost-id> [-- CMD]                  # stand-in for ssh; no CMD opens an interactive shell
compshare tail <uhost-id> <path> [-n 20] [--grep RE] [--exclude RE]
compshare status <uhost-id>                        # uptime / spent / GPU / running jobs
compshare doctor <uhost-id>                        # on-box environment: python/torch/nvcc/raster/rsync/disk
compshare settle <uhost-id> [--dry-run]            # wrap-up: report ETA while work runs, stop when idle
compshare push <uhost-id> <local> <remote>            # scp upload (no rsync on the remote)
compshare pull <uhost-id> <remote> <local>
compshare start <uhost-id> [--cardless A|B] [--no-watch] [--wait-ready 180] [--init-grace 300] [--force]
compshare reboot <uhost-id>                        # reboot, disk kept
compshare reinstall <uhost-id> [--image ID] [--yes] # reinstall the system disk; without --yes only the plan is printed
compshare wait <uhost-id> [--state Running] [--timeout 180]  # state only, not channels
compshare stop  <uhost-id>                         # clean shutdown of one machine
compshare kill  <id> [<id> ...] | --all [--dry-run]  # force stop, several or all
compshare release <id> [--yes] [--keep-udisk]       # return it: both disks go; without --yes only the plan is printed, and the machine must be Stopped
compshare create --image <id> --password '...' [--cards 1] [--cpu 16] [--mem-gb 64] \
                 [--region cn-wlcb] [--zone cn-wlcb-01] [--name x] [--disk-size 100]
compshare watch --gpu <card> --cards 1 --image <id> [--minutes 30] [--interval 20] [--open]
compshare watchdog <uhost-id> [--foreground] [--status] [--off]
```

`stock` requires `--image` (the API demands it); get an id first with `images --grep`.

## Hard rule: never assemble ssh / sshpass yourself

The password and IP sit in `data/instance-<id>.json`, but **you may not read them out and build a command line**. Reasons: the password then appears in the process table; `sshpass -p "$PW" ssh -o ...` is a long string rewritten every time and the port is easy to get wrong; and hosts rate-limit consecutive failures, so one bad attempt costs a long wait.

Always use these three:

```bash
compshare ssh-setup <id>                 # run once; afterwards the machine is "a name"
ssh cs-<id> 'nvidia-smi'                     # no password (the alias lives in ~/.ssh/config)
compshare exec <id> 'CMD'                # API-checked, path-completed, exit code from the remote
compshare tail <id> /root/xxx.log -n 50 --exclude Download
```

Everything `ssh-setup` does is repeatable: generate `data/id_ed25519` (600) → **append** the public key to the remote `~/.ssh/authorized_keys` (deduplicated by comment, existing content untouched) → maintain a `Host cs-<id>` block marked `# >>> compshare (managed) >>>` in `~/.ssh/config`. Nothing outside the block is modified; rerunning replaces only the same-named Host.

`exec` authenticates with the key first, and falls back to the password in `data/instance-<id>.json` only when stderr shows `Permission denied`. A remote command returning non-zero is **not** an authentication failure.

A machine that already has an alias can be used directly with `scp`/`rsync`/IDE Remote-SSH under the name `cs-<id>` — no IP or port needed (the port is 23, not 22).

## Wrap-up contract (read first; breaking it burns money)

**When a reply is sent, the machine is either `Stopped` or running the task this turn explicitly needs. There is no third state.**

A question is not a substitute for shutting down. Either finish in one pass (edit code → start → run → pull images → look at them → stop → confirm with `ls`), or stop first and then speak. Editing code, writing documents and reading literature use no GPU, so the machine must be `Stopped`.

Billing is **per machine**: a `Running` instance bills every moment, even at 0% GPU. The unit price varies by card type, so do not memorise a number: read `cost` and `up` from `compshare status <id>` (or `price_cny_per_hour` in `data/instance-<id>.json`). The five rules below are therefore pre-delivery checks, not advice:

1. **Never end a turn with "next: …".** While the machine is `Running`, the turn must close with `compshare settle <id>`: it either lists the jobs still running (with elapsed time) or stops the machine. A report that says "in progress" or "will do next" without one of those outcomes leaves the bill to someone else.
2. **Do not hold a GPU during download / install / compile.** Those phases need CPU and bandwidth. Either `settle` (stop) → `start --cardless A` (¥0.15/h) → finish → `start` with a card, or run the genuinely GPU-hungry job in parallel while waiting. An idle GPU waiting on a HuggingFace download is pure loss.
3. **Take numbers exactly; do not truncate with pipes.** `cmd | tail -3` cuts `command not found` out of view and lets `tail`'s 0 overwrite the exit code. Count with `grep -c`, match with `grep -E`, size with `du -sh`, space with `df -h`; when a pipe is genuinely needed add `--pipefail` (the remote prepends `set -o pipefail`).
4. **Image tags are not trustworthy; run `doctor` first thing after boot.** Measured: `cuda128_torch291_py312` is in reality Ubuntu 22.04 + Python 3.10 with no pip and no torch — only `/usr/local/cuda` is real. Any assumption of "the image ships X" has to be turned into a one-line piece of evidence with `doctor`.
5. **There is no rsync on the remote.** Upload and download with `push` / `pull` (scp through the alias); do not write `rsync`.

One command that shows whether money is burning:

```bash
compshare status <id>      # uptime / spent / GPU utilisation / running jobs
compshare settle <id>      # wrap-up: ETA if work runs, stop if idle
```

### After training: stop → start cardless → collect → stop

Artefacts cannot stay on the remote disk (unreachable once the instance stops), but **collecting them should not hold a GPU**. Four steps, order fixed:

```bash
# 1) stop the carded instance first (training is over, the GPU is no longer needed)
compshare stop <id>; sleep 45; compshare ls
# 2) start in cardless mode (¥0.15/h; 2 cores / 4 GB is enough for packaging and transfer)
compshare start <id> --cardless A --no-watch
# 3) pack remotely → pull → unpack locally → verify counts
compshare exec <id> 'cd <out> && tar -cf /root/<tag>.tar renders data *.json *.log; ls -lh /root/<tag>.tar'
compshare pull <id> /root/<tag>.tar ./tmp/<tag>.tar
mkdir -p tmp/<tag> && tar -xf tmp/<tag>.tar -C tmp/<tag>
compshare exec <id> 'du -sh <out>; ls <out>/renders | wc -l; wc -l <out>/data/loss.csv'
# 4) stop again
compshare stop <id>; sleep 45; compshare ls
```

**Exit**: only when the local file count matches the remote count and the key frames are present may step 4's `stop` run. The user should never have to ask "did you pull the results" — asking means this step was skipped.

**Forbidden**: `pull` directly on a carded instance. Transfer yields no compute, yet bills at ¥1.7/h.

### Standard wrap-up (copy it, do not invent one)

The moment a batch's `exec` returns, **in the same turn**:

```bash
compshare stop <id>                                    # 1) stop the carded instance
compshare start <id> --cardless A --no-watch           # 2) start cardless
compshare pull <id> /root/<tag>.tar ./tmp/<tag>.tar    # 3) collect
compshare stop <id>                                    # 4) stop again
sleep 45
compshare ls                                           # confirm Stopped, paste it into the reply
```

Backgrounding (`nohup ... &`) is not a reason to stay powered on — the results still have to be collected and the machine stopped.

## Reading `ls` (three states, told apart at a glance)

The columns are fixed: `ID state billing-tier region card-type GPU-count name`.

| Fragment | Meaning | Billing |
|---|---|---|
| `Stopped -` | powered off | 0 |
| `Running cardless` | **cardless** (ssh and file transfer work, no CUDA) | ¥0.15/h |
| `Running gpu` | **with a card** (can train) | by card type, from about ¥1.7/h |

The second column stays the bare state (`Stopped`/`Running`/`Starting`…), so existing uses such as `awk '{print $2}'` are unaffected; whether a card is attached is read from the third column — do not look at the `GPU` count, because a 4090 machine with a GPU count of 0 is in cardless mode.

## Four "stop" verbs, never interchanged

| Command | Scope | Checks for running work first | Destroys | Use |
|---|---|---|---|---|
| `stop <id>` | one | no | no | an explicit single shutdown |
| `settle <id>` | one | **yes** (stops only when idle, otherwise lists the ETA) | no | the default end-of-turn action |
| `kill <id...>` / `kill --all` | several / every Running | no, unconditional | no | stop billing right now |
| `release <id>` | one | no (requires Stopped) | **yes, irreversible** | return it: the instance disappears and the system disk is wiped |

The first three delete no disk: disks keep billing by capacity (zero within the free allowance). `kill` only stops the GPU/CPU/memory charge.

`release` calls `TerminateCompShareInstance`, and the official restriction is **only a Stopped instance may be deleted**. Therefore:

- While the instance is Running/Stopping, `release` sends one `stop` and exits 4 (telling you to run it again); it never deletes in the same call, because that delete would land on an unknown state.
- **Returning means nothing is left to pay for**: both the system disk and the data disk are deleted (`ReleaseUDisk=true`). A disk kept behind still bills by capacity, and this API offers no way to list or delete it afterwards (`DescribeCompShareDisk` / `DescribeCompShareUdisk` both answer 161 `Action not found`), so `--keep-udisk` is the only way to retain one — and it means console-only cleanup later.
- After deletion the instance disappears from `ls` rather than entering a final state; confirm by its absence from `ls`, not with `info` (`info` answers "record missing" for a deleted id, which is equally true of an id that never existed).

```bash
compshare stop <id>
compshare ls                    # wait until Stopped
compshare release <id>          # irreversible; prints the plan only, --yes executes
compshare ls                    # confirm it is gone
```

"Stop everything" done correctly:

```bash
compshare ls --running              # first see what is billing
compshare kill --all --dry-run      # confirm the list (no request sent)
compshare kill --all                # stop; partial failure exits 4 with per-machine errors on stderr
compshare kill $(compshare ls --running --ids)   # equivalent, composable with other filters
```

`ls` is **complete** (it pages past `Limit=100`), assumes no state and does not care where an instance came from; `--running` is the filter. `--ids` prints ids only, made for pipes.

## Sources (every conclusion must trace here)

The code cites reference codes (`REFS` constant); this section maps code → URL. Changing any "officially it says" conclusion means changing both places; `compshare states --urls` prints the mapping.

| Code | Document | What it supports |
|---|---|---|
| `FAQ` | https://www.compshare.cn/docs/operation/gpufaq | billing during card init/start, error codes, cardless limits, package billing while stopped, return and arrears |
| `BILL` | https://www.compshare.cn/docs/operation/charge/billdescribe | pay-as-you-go stops at shutdown, disks and images keep billing, daily/monthly refund proration |
| `API` | https://www.compshare.cn/docs/gpus/instance/describecompshareinstance | `DescribeCompShareInstance` fields, State enum (**Initializing omitted**), Limit ceiling 100 |
| `UAPI` | https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance | the complete State enum (including Initializing / Install Fail / Resizing / empty string) |
| `DISK` | https://www.compshare.cn/docs/operation/gpu/disk | system disk free allowance, local-disk migration, resize |
| `SPOT` | https://www.compshare.cn/docs/operation/gpuspot/gpuspot | spot reclamation, free protection window, no shutdown support |
| `AGREE` | https://www.compshare.cn/docs/overview/serviceagreement/frame | 3.3.8–3.3.10: pay first, dispute after; refunds need written agreement |

## State values: the two official documents disagree; the table wins

| Source | `State` enum |
|---|---|
| `API` (compshare, 2026-10-11) | Running / Stopped / Starting / Stopping / Install / Rebooting — **no Initializing** |
| `UAPI` (UCloud, 2026-04-24) | Initializing / Starting / Running / Stopping / Stopped / Install Fail / Rebooting / Resizing / empty |
| Measured (local records, 2026-11-06) | Initializing 50+ times, Starting several, Install twice, Running / Stopped |

So "does Initializing exist, and is it billed" cannot be answered by paraphrasing docs; query the table:

```bash
compshare states --urls   # value / billed|free|unknown / code + document URL
```

`unknown` is deliberate: for `Stopping`, `Rebooting`, `Install`, `Install Fail` and `Resizing` the vendor **does not say** whether they bill, so the tool writes unknown — it neither treats them as free nor guesses. The billing labels printed by `status` come straight from this table (`gpu_billed_initializing` / `gpu_not_billed` / `gpu_billing_unknown_x`).

## Definitions come from the tool, not from my wording

"Uptime" once had three different meanings (this run 5.15 h / cumulative 37.8 h / 0.3 h since the last verdict), and each time a redefinition papered over it. The definition is now data, not my sentence:

```bash
compshare gauges    # per number: which field, unit, and what a misread would conclude (self-checked)
compshare show <id> # the raw API record for one instance: whole, no fields dropped, no reordering
compshare correct   # list historical definition corrections
compshare correct "<old wording>" "<new definition>" --why "<field>"   # record one
```

Three constraints:

1. **Outward numbers may only use field names from `gauges`.** If you cannot write `field=value`, run `show` and read the raw record instead of paraphrasing — paraphrasing is where drift starts.
2. **Changing a definition requires three things together: a recorded correction, a code change and a table change.** Talking differently is not changing. `gauges` checks that every field emitted by `status` is in the table and exits non-zero otherwise.
3. **Universal claims need complete data.** Before saying "none anywhere / all missing / only one place has it", every region (`_targets`) must have been walked and every page (`_paged`) fetched.

## Three clocks; never read them interchangeably

One question — "how long has it been up" — has three answers, and mixing them turns 5 hours into 38:

| Field | Source | Meaning | What a misuse produces |
|---|---|---|---|
| `up=` | container `/proc/uptime` | this boot | reported as "total use", understating cost |
| `usage=` | API `UsageSeconds` | cumulative, every boot included | reported as "running this long", overstating risk and misreading a stuck day |
| `age_h=` | ledger `verdict-<id>.json` | hours since the **last verdict** | reported as uptime, which it is not |

Measured difference: `wk-09` showed `up=5.15h` and `usage=37.8h` in the same run.

Billing likewise has three definitions, and `status` labels them directly:

```
Running      → (no label, normal pay-as-you-go)
Initializing → gpu_billed_initializing    # official FAQ 2.2: card init is billed
Starting     → gpu_not_billed             # host not up yet, not billed
Stopped      → gpu_not_billed + disk_still_billed
package/daily/monthly → instance_billed charge=Month   # bills while stopped (FAQ 2.1)
```

## Two hard constraints of the official API

**One: never truncate at the application layer.** `Limit=100` is the first page, not the whole set. Any "just look at the first N" turns a conclusion wrong rather than smaller:

| Wrong form | Actual consequence |
|---|---|
| `Limit=100` without paging | 420 platform images, 100 seen → concluded "that image does not exist" |
| `for _ in range(10)` as a page limit | silently short beyond 1000 instances |
| printing `rows[:8]` / `[:900]` | fewer specs than reality → "that region has no large spec" |
| `if zone not in ("a","b"): continue` | the region is reported as "no stock" when it simply does not sell that card |

There is exactly one implementation entry: `_paged(action, key, id_field, region, zone, page=100)`, which stops only at `len(got) < page` or when a page brings no new id, and has **no page ceiling**. A new paged endpoint goes through it.

**Two: never assume a region.** Hard-coded `cn-wlcb` / `cn-wlcb-01` used to decide "north China 2A" on the user's behalf; the moment stock ran out there, the conclusion became "no stock anywhere". The rule now:

```bash
compshare stock  --gpu 4090 --image <id>      # omitted = walk all five regions in ZONES
compshare images --grep PyTorch                # omitted = full pagination per region, region/zone prefixed
compshare types  --gpu 4090                    # same
compshare ls                                   # instances carry Region/Zone, no lookup
```

Order of decision: **walk every region first, then conclude about a specific one**. To pin a region, pass `--region`/`--zone` explicitly; instance-scoped commands (`exec`/`health`/`start`) take Region/Zone from the instance record and never guess.

## Answering "what was it like before": read the original, then compare facts

When asked "what did we do yesterday / last time", "what changed versus the earlier code", "where was it strengthened", **read the full IDE context first** for the original words, then check against disk facts (`find -newermt`, file contents, `ls`/`card`):

```bash
.agent-tools/agent-ide context --id 毕设 --last 200 --since 2026-11-06 --out /tmp/ctx.txt
```

- The original text answers **what was asked and bounded at the time** (what the user said, what I promised);
- the disk answers **what was left behind** (files, timestamps, contents);
- when they disagree, the original text wins and the difference is stated.

`card --aux` notes, conclusions written in this file, and my own previous report are second-hand and cannot be evidence of "what happened then". Pasting a file list and claiming "robustness was strengthened yesterday" is indirect evidence dressed up as a record.

## Output conventions

The CLI states facts, not sentences. Two channels, fixed division:

* **stdout**: result records, one per line, space-separated. The agent reads this; with `--json` the whole block becomes JSON.
* **stderr**: progress and conclusion hints, one per line, skippable. A line starting `action:` is the only kind that actually asks for the next command.

Record formats (tokens are lowercase or verbatim states, never Chinese and never punctuation):

```
ready      <id> <sec>s
ready      <id> <sec>s jupyter-only
not-ready  <id> <state>                # powered off
not-ready  <id> <state> timeout <sec>s
not-ready  <id> <state> stuck
abort      <id> <state|ssh-unreachable> [<sec>s]
wait       <id> <state> <elapsed>s      # progress, only on state change or once per 30s
wait-ok    <id> <state> <sec>s
wait-failed<id> <state>
plan       id=… state=… image=… system_disk_gb=… wipes=system keeps=data
pick       <id> <state> <ip> <verdict> <why>
<id> <state> <ip> <verdict> <why>       # health / ls
```

### One line per object

Every command follows one shape: one object per line, the first token is the id, the rest are verdicts. No indentation, no sub-headings, no sentences. A human scans the first column; an agent reads the remaining tokens.

```
<id> try1 init-stuck 14s      # bootcheck: one line per attempt (verdict + elapsed)
<id> try2 stop-err 8903       # failed already at the stop stage, platform error code appended
<id> unhealthy 3/3            # this machine's three verdicts
summary healthy=0 unhealthy=1 total=1    # batch summary, always the last line
```

Codes such as `8903` must appear in the line rather than be replaced by "it failed": the code decides the next step (8903 = state does not allow it, usually a Stopping instance — wait for it, it is not a fault).

**Progress lines are not result lines.** `wait <id> <state> <sec>` appears only on a state change, and only in commands that have a process (`start`, `exec`); result-only commands use `quiet` to switch progress off, otherwise the reader gets noise such as `Starting 0s`.

Values of `verdict` and `why`:

| verdict | why values | Meaning |
|---|---|---|
| `ready` | `ssh-open` | exec works |
| `jupyter` | `jupyter-open ssh-down` | usable, but only through 8888 |
| `init-wait` | `state <X> <sec>s` or `ssh-timeout jupyter-timeout` | still coming up |
| `init-stuck` | `ports-refused` or `state <X> <sec>s><grace>s` | the container is not running |
| `not-running` | `state Stopped` | powered off |

Exit codes: `0` usable · `1` API error · `2` usage error (including unknown id) · `3` no stock ·
`10` network failure · `20` no credentials · `30` unusable · `31` stopped · `32` Jupyter only.

## Naming and renting: no machine is special

**Name them `wk-NN`.** Never `host-01`, `master`, `gpu-a` and other purpose-named machines: purposes change, numbers do not; once a machine has a private name it becomes "that special one" during scheduling, and every decision then starts by discussing it. Renaming affects neither the instance id, nor the disks, nor billing:

```bash
compshare rename <id> wk-09
```

**Rent with the same parameters.** Card type, image, system-disk size and region come from one set of `compshare create` arguments; never change the spec or image for one machine — that turns "why is this one different" into a permanent question.

**Data may not grow on one machine.** Weights and data either live where every machine can reach them (object storage, a custom image, a re-downloadable HuggingFace repo), or they are counted as reproducible. The moment some datum exists on exactly one machine, that machine is a single point of failure, and when it dies there is no option but to wait.

**Schedule from the ledger, not from a machine's history.** The order is always `verdicts` → `pick` → `health`; "what is on this machine" is not a reason to choose it, "can it work right now" is.

## Read the ledger before starting; do not reschedule onto a dead machine

`pick` answers "this moment" and cannot answer "how often has this one broken". That fact sits in `data/verdict-<id>.json`, and one command now reads it:

```bash
compshare verdicts            # one line per machine: name, id, last verdict, reason, how long ago
```

Machines judged dead sort first. **Run it before scheduling anything**, especially before decisions of the form "the data is on that machine so it is the only option" — data on a broken machine does not mean the machine can start; confirm it starts, then talk about the data.

Three checks up front; miss one and the same pit is entered again:

| Check | Command | Consequence of skipping |
|---|---|---|
| Has this one been judged dead recently | `compshare verdicts` | sending `start` to a dead container again: two minutes to `Initializing`, then stuck |
| Can it work right now | `compshare health <id>` | reading "container not running" as "still coming up" and waiting on |
| Is the data I need on this machine | `compshare exec <id> 'du -sh /root/data/*'` | assuming the model is there when it sits on another machine |

**Do not try a dead machine yourself**: `start` just repeats the same failure. Rescue means `reboot` / `reinstall` (which wipes the system disk) or the console — and all three need a human nod. Moving to a working machine is the human's choice; the tool only lays out the state of each.

## `start` refuses on its own: machines with three failures are not retried by default

The ledger command solved "visible", but visible is not the same as seen. So the verdict moved into `start` itself:

```
$ compshare start uhost-1wzocg7lg84s --cardless A --no-watch
start-blocked uhost-1wzocg7lg84s broken=3 last=0.5h
action: reboot | reinstall | release | --force
```

Returns in two seconds **without sending a single request**. Three conditions must all hold:

| Condition | Default | Meaning |
|---|---|---|
| `broken_count >= 3` | `START_BLOCK_AFTER` | three or more failures accumulated |
| the latest failure within 24 h | `START_BLOCK_WINDOW_H` | still failing, not a historical debt |
| the latest measurement was not `ready` | — | a machine already proven usable is not blocked by old failures |

It blocks exactly one action — repeating the same failure — and nothing else:

- without `--force` it does not start, exits `30`, and lists the four things that could actually change the situation;
- with `--force` it starts anyway: the tool does not decide for the human, it just stops routing you into that loop by default;
- `reboot` / `reinstall` / `release` are unaffected (`release` has its own `--yes`).

Why this has to be a gate rather than a sentence in a document: for a dead machine `start` returns success every time, so the signal "did it fail" does not exist; only the ledger, as external memory, can break the loop.

## Stock `no` does not mean no card can be attached

`CheckCompShareResourceCapacity` is called by the platform only when **creating a new instance**. For an **existing** instance, `StartCompShareInstance` takes another route and is not bound by that table's yes/no.

Measured 2026-11-06 (three machines that could all start cardless, while the stock API answered `no` for every 4090 combination in every region):

```
wk-05 uhost-1x8mlg61si27  --gpu → Running GPU=1 4090 price=2.05   ready after 53s
wk-02 uhost-1x8mkvqhpcwb  --gpu → Running GPU=1 4090 price=2.05   ready after 54s
wk-04 uhost-1x8mlb378pg6  --gpu → Running GPU=1 4090 price=2.05   ready after 55s
```

3/3 attached. So **stock `no` only means "creating a new instance right now would fail"**, not "an existing machine cannot take a card". Test attachment with `start --gpu --wait-ready 150`; do not infer it from the stock API.

Note that a carded start is slower than cardless (cardless 45–58 s; carded 53–55 s and noisier), so `--wait-ready 90` can misjudge; use 150 s for carded.

## Physical: `bootcheck` is the only entry for "can this machine still work"

**Use it first, discuss afterwards.** Whether a machine is dead is not decided by one `start`: a single failure may just be a bad scheduling draw. The check gives three attempts, and one success makes it healthy.

```bash
compshare bootcheck <id> [<id> ...]      # default: cardless A, 120s per attempt, 3 attempts, gaps 60s / 180s, 6 machines in flight
compshare bootcheck <id> --parallel 10   # widen the fan-out (billing and API limits argue against going much past 6)
compshare bootcheck <id> --keep          # leave it running when the check passes (default stops it)
```

**Why cardless is enough**: every failure sample (`Install Fail`, `Initializing` stuck) sits in the container layer before the GPU is involved; cardless costs ¥0.15/h against ¥1.7/h carded. So the check is always cardless, with `WithoutGpuSpec` passed and `GPU` omitted.

**Reading the output** (one line per attempt, one per machine, one summary):

```
uhost-1x8mlg61si27 try1 jupyter 48s     # container up, ssh not — still a successful boot
uhost-1x8mlg61si27 try2 ready 56s
uhost-1x8mlg61si27 healthy 2/3 ready
uhost-1x8mlg61si27 stopped              # successful machines are stopped too
summary healthy=1 unhealthy=0 total=1 left_running=0
```

**Three hard constraints** (drop one and this feature turns into a money sink):

1. **Cardless only**: the question is whether the container starts, which has nothing to do with a card;
2. **Stop cleanly before each attempt**: without clearing, the previous `Install Fail` / `Initializing` is inherited and all three attempts measure the same state;
3. **Everything is `Stopped` at the end, successful machines included**: wait for the state to settle after `stop`, and `left_running` in the summary must be 0 — if not, print `left <ids>`. `--keep` is the only exception.

**The result goes into the ledger**: healthy → `verdict=ready`; three failures → `verdict=init-stuck`, after which `start` is blocked by `_start_blocked` (`--force` still sends it) and a dead machine is no longer retried.

### Many machines, one command — it runs them concurrently

**Machines are independent jobs, so a sweep runs them in parallel.** `bootcheck` takes any number of ids and checks them with `--parallel`, six at a time by default:

```bash
compshare bootcheck <id> [<id> ...] [--parallel N]   # default N=6; one process, N machines in flight
compshare ls --ids | xargs -P 6 -I{} compshare bootcheck {}   # equivalent; use it when you want one process per machine
```

Passing fifteen ids to one invocation is no longer serial: per-machine time is platform boot latency (34–66 s on success, at most 3 × 120 s + 60 s + 180 s on failure), so a fleet costs roughly `ceil(N / parallel) × per-machine`, not `N × per-machine`. Measured: 15 machines six-way finished in 7 minutes; the earlier one-process-at-a-time sweep reached five machines in about ten minutes and was abandoned.

- **Never write your own loop** (`for id in ...; do compshare bootcheck $id; done`): it re-serialises the work and hides the concurrency in shell instead of the tool. The same holds for `start`, `stop`, `health`, `verdicts` sweeps.
- **Do not shorten `--allow`** to make a sweep feel faster. The defaults are the specification: 120 s per attempt, 60 s then 180 s between attempts. Successes land at 45–58 s, so 120 s is a 2× margin; a machine that would boot at 100 s is judged dead by `--allow 90`. The gaps only delay *failing* machines (a healthy one leaves after its first success), so the lever for wall clock is `--parallel`, never the allowance.
- **Bound the width at about six.** Every in-flight machine bills cardless (¥0.15/h), and the API rate-limits with `226619` (backed off by 20 s), so widening past six produces retries more than throughput.
- **Output stays grouped per machine** even at width 6: attempt lines are buffered and printed when each machine finishes, so `try1/try2/healthy` never interleave. (With `xargs`, each process writes its own stream; redirect per machine if you need files.)
- **A machine that throws does not take the sweep down**: that id is reported and counted unhealthy, the rest continue.

**After the sweep, reconcile the stops.** `ls --running` must be empty. When a summary says `left_running=1` / `left <id>`, or an attempt line reads `stop-err 226609`, the stop was refused — 226609 means the instance sits in `Install Fail`, not that it is still running — so confirm with `ls` and stop anything genuinely left, rather than assuming the sweep cleaned up.

## The time windows of a boot verdict

"Can boot" and "cannot boot" are **asymmetric** in time; measured 2026-11-06 (8 successes / 7 failures):

| Moment | What can be judged | Evidence |
|---|---|---|
| ~1–2 s | `Install Fail` → dead | 4 machines returned Install Fail straight at `Starting 0s` |
| ~3–5 s | `Running` without a public IP → dead (`no-eip`) | wk-12 hit `ssh-noroute` at 0 s and never changed over 123 s |
| 15–30 s | **only** "still coming up"; success cannot be judged | all 8 successes sat in `Initializing`/`Starting` between 15 and 30 s |
| 45–58 s | the earliest success signal | ready at 45/46/50/51/51/52/57/58 s |
| 90 s | still not ready → dead | wk-09/wk-10 were still stuck at 163–164 s and never recovered |

Conclusion: `--wait-ready 30` would have failed all 8 successful machines. Two fixed thresholds:

- **Just screening out bad cards**: `--wait-ready 5` (catches only the two instant failures, `Install Fail` and `no-eip`, and moves to the next machine);
- **Confirming a machine is usable**: `--wait-ready 90` (successes land at 45–58 s, a 50% margin).

## Downloads: liveness, triage, restart

The real time sink when rolling out weights in bulk is not bandwidth, it is **restarting on the same machine**.

**Do not judge liveness with `du`.** `du -sm <local_dir>` counts `.cache/huggingface/download/**/*.incomplete`, so after a few restarts the size only grows and cannot tell downloading from dead. The reliable signal is the write time of incomplete files:

```bash
find /root/data/models/kolors-diffusers/.cache -name "*.incomplete" -newermt "-4 minutes" | wc -l
```

Zero means not one byte was written in four minutes, which is the only thing that counts as stalled. Sample at least three minutes apart.

**Clear orphans before restarting.** Each `hf download --local-dir` run creates `.incomplete` files with a **different suffix** for the same target (one unet left three copies of 4.5 G / 4.8 G / 4.9 G), and the old ones are not removed:

- they do not resume, so the download starts over;
- they fill the disk (wk-03 reached 40 G of 59 G, 17 G left, and the next write would have failed).

```bash
find .cache -name "*.incomplete" ! -newermt "<start of this run>" -delete
```

**Stalled means a dead process; `kill` is a recovery action, not a destructive one.** The criterion is write time:

```bash
find .cache -name "*.incomplete" -newermt "-4 minutes" | wc -l   # 0 = dead
```

Zero (with the process still alive) means "alive but doing nothing" — monitoring it is then pointless, and watching for 30 minutes is indistinguishable from it having died. There is exactly one correct action, taken at once:

```bash
ps -eo pid,args | grep "hf download" | grep -v grep | awk '{print $1}' | xargs -r kill
find .cache -name "*.incomplete" -delete
setsid nohup env HF_HUB_DISABLE_XET=1 <py> -m ... >> /root/kolors.log 2>&1 &
```

The line is fixed: **writes present = do not kill** (that is progress, killing wastes the download); **four minutes with no writes = must kill** (that is a dead connection; not killing only waits for its timeout). Monitoring is not an action: one sample is enough, and the verdict converts immediately into kill/restart.

**Restart budget: twice per machine.** Fixed order:

1. Stalled → clear orphans + restart once, adding `HF_HUB_DISABLE_XET=1` (the long-lived xet connection is the most common hang);
2. Stalled again → give up on this machine and go through `pool fill`'s `rent`/swap path; do not try a third time here;
3. Never delete a half-finished artefact you want to keep: record it with `card <id> --kolors partial --note "<size>"` and resume when a card is available.

**Why twice**: of 8 machines, 3 stalled 2–3 times each; every restart costs 15–25 minutes and does not necessarily advance.

The reason for two attempts: of 8 machines, 3 stalled 2–3 times each; every restart costs 15–25 minutes and does not necessarily advance, while one orphan-clearing plus no-xet restart succeeds markedly more often. Past two attempts without movement, the problem is most likely the image or the node, and further waiting only holds up the batch.

## Transfers: the destination comes from the content, and every transfer is verified

```bash
compshare upload <id> <local-path...> [--name label]     # → /root/uploaded/<timestamp>-<content hash>/
compshare download <id> <remote-path> [--dest DIR]      # → ./downloaded/<timestamp>-<content hash>/
compshare xcheck <id> <remote-dir> [--local DIR]        # final state check: listing + comparison with the local side
```

**The destination cannot be chosen.** The directory is fixed as `/root/uploaded/<YYYYmmdd-HHMMSS>-<first 8 of entries-sha256>[-name]/`: the path comes from the content, the same batch re-uploaded lands in the same directory, and different batches never overwrite each other. Downloads work the same way, landing in `./downloaded/<timestamp>-<hash>/`.

**Verification is part of the process, not an option.** A two-way comparison runs immediately after the transfer:

| Case | Compared | Output |
|---|---|---|
| ≤ 4 GiB | per-file size + sha256 | `verify=ok` / `verify=mismatch` + `bad <file>` |
| > 4 GiB | per-file size + file count (`--no-hash` also takes this path) | `verify=ok method=size+count`, never claiming a hash check |

On a mismatch only the bad files are re-sent (`--retries`, default 2), never the whole package.

**Pits already baked into the code**:

1. `scp`'s exit code is untrustworthy: a broken stream can leave a half file and still return 0 → size + sha256 is the only authority.
2. macOS `tar` adds AppleDouble `._*` entries; unpacking on the remote then shows extra files and a mismatch → the producer sets `COPYFILE_DISABLE=1` and the listing filters `._*`.
3. The pipe direction differs between upload and download: upload is "local tar → ssh stdin", download is "ssh stdout → local tar". Writing one function for both makes the download unpack an empty directory (the first version did exactly that).
4. Aliases go stale: after an instance restarts its public IP and port change, and `~/.ssh/config` still holds the old address → rewrite the alias before transferring.
5. The first ssh often returns 255 (alias just written, sshd still starting) → wait two seconds and retry once instead of declaring it dead.
6. Disks fill: compare `df` free space with the local byte total before uploading, fail early, and leave no half files.

Fixed action after a transfer: `compshare stop <id>` — never leave a transfer window billing.

**Background jobs: no need to sit through a large transfer.**

```bash
compshare upload <id> <path...> --bg     # returns at once with job=… pid=…
compshare xfer status <id>               # done/total, bytes, rate, directory — one job per line
compshare xfer resume <id> [--job J]     # resume: re-send only the files not yet done
compshare xfer log <id>|--job J          # per file: ok/fail + attempts + error
compshare xfer run <job> [--stop]        # internal entry; --stop stops the machine when finished
```

The unit of work is **one file**: each file gets its own tar stream and its own `sha256sum`, failures retry three times with increasing gaps, and progress is written to `data/xfer-<id>-<hash>[-name].json`. Therefore:

- files above 4 GiB still get a hash check (no downgrade to `size+count`);
- an SSH drop affects only the current file, and `xfer resume` continues without starting over;
- `xfer status` is the only observation needed — no more guessing with `du`/`pgrep`.

**No automatic shutdown by default.** The cost was measured on 2026-11-07: a small three-file job stopped a machine that was in the middle of a 17 G download. Shutdown happens only with an explicit `xfer run --stop`.

## Passwords and shutdown: neither should be typed by a human every time

- **Default password** `Compshare2026` (`cli.DEFAULT_PASSWORD`). Neither `create` nor `grab` needs `--password` any more; changing it means editing one constant — never put the password on the command line, where it lands in shell history and logs.
- **Creation leaves a record**: after `CreateCompShareInstance` succeeds, `data/instance-<id>.json` is written with `password` / `region` / `zone` / spec. `_ssh_once` falls back to password auth when the key is refused, and without that record it cannot log in.
- **A grabbed machine is stopped immediately**: `pool grab` runs `stop` after creating one (printing a `stop <id>` line), because grabbing is about claiming a slot in the pool, not about idling at ¥2.05/h. Add `--keep-gpu` when it is needed right away.

## Quota: fail locally instead of hitting the platform

`MAX_INSTANCES = 15` (top of `compshare.py`). This is a **measured** value, not the 20 in the official table: the create documentation says "Level 2 = 20 machines", but with 15 machines on this account the 16th returned `226608` in cn-wlcb-01, cn-sh2-02 and cn-bj2-03 alike — a code absent from the official table (public codes stop at 226606).

```bash
$ compshare pool grab --target 16 --count 1 --gpu 4090 --image <id>
error quota=15 reached (15 instances); platform returns 226608 beyond this   # exit=3

$ compshare create --image <id> --region cn-wlcb --zone cn-wlcb-01 --cpu 16 --mem-gb 64
error quota=15 reached; release an instance first (platform returns 226608 beyond this)
```

Both entries fail before sending a request: `create` errors out, `grab` clamps `need` to the remaining headroom and prints `grab capped need=N->M`. A full quota therefore reads as one readable sentence plus exit code 3, not a string of platform codes. When the quota changes, change the single `MAX_INSTANCES` line.

## Naming: only the algorithm names machines, humans attach notes

A machine is a worker; its name is a number, not an identity. So neither `create` nor `grab` accepts a user-supplied name:

- the name is always `wk-NN`, with `_next_name()` taking the **lowest unused number**;
- when grabbing several at once, each new name is written back to `hosts` as it is created (without refreshing the snapshot all four came out as `wk-09`, measured);
- to record what a machine is for, use a note and leave the name alone:

```bash
compshare card <id> --aux "Shanghai 2B, grabbed 2026-11-06, not deployed"
compshare pool status        # the note trails the line as aux=…, the number is untouched
```

The note field is called `aux` everywhere (the old `note` migrated to `aux`; `--note` still writes as an alias). Consecutive numbering has a practical use: `wk-01..wk-12` is the complete pool inventory, a missing number is a missing machine, and no separate ledger is needed.

## The card pool: a usable card is not "a machine that is on"

**A usable card is one that is stable and ready when needed** — three conditions together:

| Criterion | Where it is recorded | Note |
|---|---|---|
| stable | `data/verdict-<id>.json` | `broken_count < 3`, or the latest measurement `ready` |
| kolors in place | `kolors=ready` in `data/card-<id>.json` | weights complete (unet + three shards + vae + tokenizer + scheduler) |
| smoke passed | `smoke=ok` in the same file | a real 0.1 run passed, not "dependencies installed" |

`Running` does not count as a usable card: running bills by the hour, so hoarding 10 machines is ¥20/h. A `Stopped` machine reports `GPU` as 0 (shutdown returns the card to the platform), so "can start" and "holds a card" are two different things.

```bash
compshare card <id> --kolors ready --smoke ok --note "unet + 3 shards + vae, 0.1 smoke passed at 8 steps"
compshare pool status             # effective / pending / unknown / broken + gap
compshare pool fill --target 10   # plan by gap: probe / configure / verify / rent / release
compshare pool grab --target 10 --gpu 4090 --image <id> --password <pw> --for 90
compshare pool release-broken     # dry-run by default, --yes actually deletes
```

**Filling the pool is continuous**: while `gap > 0`, refill alongside the experiments, in a fixed order — `probe` existing machines (no `card-<id>.json` does not mean no kolors), then `configure` (complete the weights), then `verify` (run the 0.1 smoke), and only then `rent` (grab a new card). Renting one more costs one more full price; an `idle` machine is merely unconfigured.

**A bad card does not hold a pool slot**: anything with `broken_count >= 3` that will not start goes to `release-broken`. The cost of keeping it is not money, it is that every round of work starts with "try it once more" — on 2026-11-06 two main machines sat in `Initializing` at the same time, 17 G on disk was unreachable, and the whole pipeline stalled exactly that way.

## Permanently obsolete machines: return them, do not keep them occupying a seat

A machine repeatedly stuck in `Initializing` costs more than those two minutes — it makes every round start with "try it first", and in the end nothing runs. So past a certain point the correct action is to **return it** (`TerminateCompShareInstance`), not to keep it and not to keep starting it.

Criteria (`compshare verdicts` prints both columns):

| Column | Meaning |
|---|---|
| `broken=N` | how many failures accumulated (`init-stuck` / `timeout` each count once, and a later `stop` does not reset it) |
| trailing `xh` | time of the latest verdict; `broken_at` records the latest **failure** separately |

A return candidate = **failed ≥ 3 times, the latest failure more than 24 h ago, and never once `ready` since**.

```bash
compshare verdicts --stale 24      # only the return candidates
compshare release <id>             # prints the plan by default, sends nothing
compshare release <id> --yes       # actually returns it: instance + system disk unrecoverable
```

Three constraints to respect:

1. **Confirm there is no unique data first.** A broken machine's disk is unreadable (ssh is down), so "is there anything on it that exists nowhere else" can only be judged from the records made at creation. Check each one before returning: is there anything on this disk that cannot be recovered elsewhere? If unsure, `reinstall` first (wipes the system disk, keeps the data disk) instead of releasing.
2. **The data disk goes with the instance by default.** `--keep-udisk` retains it, but a retained disk keeps billing (¥0.0005/GB/h) and cannot be deleted through this API, so keeping one is a deliberate debt, not a neutral default.
3. **Returning clears the ledger automatically.** After a successful `release --yes` the `verdict-` / `state-` / `instance-` records for that instance are deleted; otherwise `pick` and `verdicts` keep listing a machine that no longer exists.

Returning is **irreversible**, so by default only `plan release <id> state=Stopped wipes=system_disk keeps=data_disk` is printed, and `--yes` executes.

## No automatic machine switching, but never hanging: every command ends with a verdict

Two constraints hold together:

1. **The tool does not switch machines for you.** Which one to use is the human's decision. Hence there is no `up`-style "pick one automatically", and no logic that silently skips a machine by history — a silent skip turns "this one failed before" into "this one does not exist".
2. **No command may hang, and none may emit misleading text.** Waiting always has a bound and ends with a verdict whose reason matches the actual trigger (a timeout stays a timeout, a death stays a death).

```bash
compshare pick                     # read-only: one line per machine, for you to choose
compshare health <id>              # 3-second verdict on one machine, no retries, no waiting
compshare ready <id> [--timeout 180] [--init-grace 180]
compshare start <id> --wait-ready 180   # boot + bounded wait, one verdict
```

Exit codes: `0` usable · `32` Jupyter only (work possible, ssh down) · `30` unusable (timeout or judged dead) · `31` stopped.

### There are only four verdicts (`ready` / `start --wait-ready` share them)

| Verdict line | Meaning | Exit |
|---|---|---|
| `ready <id> after 42s` | ports listening, usable | 0 |
| `not-ready <id> <state> not ready within 120s (…)` | timed out this time, **the death criteria are not met**; it may still be coming up | 30 |
| `not-ready <id> Initializing stuck in init (… 311s > 180s)` | judged dead, with the official wording and the next step | 30 |
| `ready-ish <id> <state> Jupyter channel only (…)` | **work possible**, ssh down; use `http://<ip>:8888` | 32 |
| `not-ready <id> Stopped powered off` | stopped, `start` first | 31 |

Progress lines print only on a state change or every 30 seconds, and state facts only (`Initializing 120s so far (30s this attempt / 180s limit)`). No "almost there" judgements, and no closing reason that contradicts the trigger (for example calling a timeout "judged stuck in card init by official wording").

### The criterion is a channel, not a state string

`State` has six official values (`Running/Stopped/Starting/Stopping/Install/Rebooting`), and the `Initializing` and `Install Fail` we actually see are not among them; more importantly, **state and "can it work" are different things**: it can be `Initializing` with ports already open, or `Running` with every port refused. So the verdict reads two independent channels:

| Channel | Port | Meaning |
|---|---|---|
| ssh | 23 (container) / 22 (VM) | whether `exec` works |
| Jupyter | 8888 | the web channel inside the container |

Measured baseline (a healthy cardless instance): 22 open, 23 open, 8888 open (HTTP 302) → `exec` works.
The two broken ones: 22 open (host-side shared sshd, not counted), 23 refused, 8888 refused → nothing listening inside the container.

| Channel state | Verdict | What is possible |
|---|---|---|
| 23 open | `ready` | everything |
| 23 refused, 8888 open | `jupyter` (exit 32) | **work possible**, web only; ssh needs a reboot or reinstall |
| both refused | container not running | wait out the grace; past it, judged dead |
| no response (not RST) | still coming up | short `ready` wait |

This criterion exists to prevent two misreadings: calling "state stuck at `Initializing` but 8888 open" unusable, and calling "`Running` but every channel refused" usable.

### State table (official FAQ 1.1 / 2.2 wording)

| Observation | What it is | Action |
|---|---|---|
| `Running` + ssh port open | usable | `exec` |
| `Initializing` within grace | container starting | `ready <id>` short wait |
| `Initializing` past grace (default 300s), or ssh port `refused` | **container failed to start / container environment destroyed** (platform side) | judged dead; next step is reboot / reinstall / another machine, or the platform; **restarting the same one is useless** |
| `Install Fail` | failed in the install stage, same family | as above; schedule nothing on it until fixed |

Official wording (FAQ 1.1): "if the container fails to start, or its environment is destroyed in use, the instance sticks in initialising or starting; to resolve, join the group and contact the owner." FAQ 2.2: "an instance stuck initialising for more than 5 minutes … join the group and contact the owner."

The grace window counts from **the first observation of that state** — not from the API's `StartTime` (measured: it does not refresh during boot; a machine started six minutes earlier reported 13185 s), and not from "the duration of this call" (calling `ready` repeatedly would reset "stuck for 20 minutes" to "just started waiting", and it would never be judged dead).

### Port 22 open and 23 refused is not good news

A container instance is `root` on port **23**; `ubuntu` on 22 belongs to system images (VMs). On a container instance's public IP, **22 is the host node's shared sshd** and stays open even when your container never started. So:

- `22 open / 23 refused` = the node is alive, your container is not; it is neither a network nor a firewall problem;
- a local key hitting 22 and getting `Permission denied` is normal (it is someone else's sshd);
- continuing to `nc`, to `ssh -p 22`, or to wait is wasted effort. Get a verdict with one `health`.

### Wait bounds per command

| Command | Default | Death condition | How to change |
|---|---|---|---|
| `exec` | `--wait 120` | state reaches a terminal value; or init exceeds `--init-grace 300` | `--wait 0` returns at once |
| `ready` | `--timeout 180` | as above | `--init-grace` separately |
| `start --wait-ready N` | 0 (no wait) | as above | pass N to wait |
| `health` | no wait, 3-second probe | — | `--no-probe` |
| `pick` | no wait, state per machine | — | — |
| API call | 60s (`COMPSHARE_TIMEOUT`) | — | do not use 20s: a listing measured 20.6s |

**Deliberately absent**: automatic restart, automatic machine switching, automatic reinstall, and skipping instances by history. All four dress up "the platform side is broken" as "the tool is trying", while billing continues. Manual actions exist (`reboot` / `reinstall`), but a human must issue them, and `reinstall` only counts with `--yes`.

### Three steps when a machine breaks (no console needed)

```bash
compshare health <id>                 # 1) verdict: ready / jupyter / init-stuck / not-running
compshare reboot <id>                 # 2) every channel refused but the instance exists: reboot first (no disk wipe)
compshare reinstall <id>              # 3) still broken: reinstall. Read the plan first, add --yes to confirm
```

Official restrictions, all echoed in the command's errors:
* `ReinstallCompShareInstance` **works only on a `Stopped` instance**, wipes the system disk, keeps the data disk, and takes a 10-minute concurrency lock.
* The image used for a reinstall is the **live `CompShareImageId`**, not the local `instance-*.json` (written at creation and possibly pointing at another environment).
* This region (container instances in cn-wlcb-01) **does not support** `UpdateCompShareInstancePorts` (measured 230 "only supported for pod instances"), so no ports need restoring after a reinstall.
* A reinstall is irreversible, so by default only `plan id=… image=… system_disk_gb=… wipes=system_disk` is printed.

## Hard limits (all from official docs or measurement)

| Limit | Detail | What happens on hitting it |
|---|---|---|
| Instance quota | unrecharged Level 0 = 1; recharged Level 1 = 5; Level 2 = 20 | creation fails |
| Card types per region | each region sells a fixed few (the list changes; check per region with `stock --gpu <card>`) | `stock` skips silently (`machine type not configured`) |
| CPU : memory | must fall between 2:1 and 1:12 | `RetCode 8333 cpu memory ratio not in 2:1 - 1:12` |
| Password | must mix upper, lower, digits and a symbol | `RetCode 8314` (creation may let it pass, reset does not) |
| `stop` prerequisites | only `Running`; 10-minute lock per instance; not while imaging; spot instances cannot be stopped manually | `InstanceOperationInProgress` and similar |
| `start` prerequisites | only `Stopped`; 10-minute lock; not while reclaiming or with background tasks | as above |
| **Shutdown does not hold the card** | GPUs/CPU/memory are reclaimed by the platform and the card can be rented by someone else | a later `start` may fail for lack of a card; retry or change region |
| Disks | a data disk bills from creation regardless of use or mounting | deleting files saves nothing; only shrinking or deleting the disk does |
| System-disk allowance | 100 GB in VM regions, 50 GB in container regions | beyond that ¥0.0005/GB/h |
| Monitoring API | `GetCompShareInstanceMonitor` is unusable (see the last section) | the watchdog must go over SSH |
| Login | this App image = `root` + port 23; `ubuntu` + 22 is refused. Port 22 on the same IP is the host's shared sshd and being open says nothing about your instance | the watchdog depends on this |

`create` first runs `CheckCompShareResourceCapacity` and exits 3 without sending a request when the spec is not `ResourceEnough`. A successful creation starts per-second billing immediately, without waiting for `Running`.

## No stock in the current region: change region, never card type

This is a hard rule, not advice.

**Change only the region.** When the same 4090 is unavailable in `cn-wlcb-01`, look for the same 4090 in `cn-sh2-02` or `cn-bj2-03`. **Do not switch to H20 / A800 / 4090-48G** — the price differs by more than 3×, and changing card type replaces the entire validated premise (40-series sm_89 versus Hopper differ in compilation and memory budget), so the numbers stop being comparable.

Three constraints hold together:

1. **The card type may not change.** Price gap above 3×, and the whole validated premise goes with it.
2. **`quote` before `create`, and state the unit price.** `create` does not quote; creating without quoting spends money unilaterally.
3. **Stock checks must use the real image id from the instance record.** A wrong image makes the whole table answer `no` — `1a0k5gtmgpw5` and `1minbz219ceq` differ exactly this way, and that is how "no cards anywhere" was once misjudged.

### The correct redeployment order

Model and code are local and do not depend on the old instance's disk, so **never transfer files while paying for a GPU**:

```bash
compshare stock --gpu 4090 --cards 1 --image <real image> --all   # find a region with stock
compshare quote --gpu 4090 --cards 1 --cpu 16 --mem-gb 64 --image <id> [--zone <zone>]  # quote first
compshare create --image <id> --gpu 4090 ... --zone <region with stock>
compshare stop <new instance>            # stop right after creation, avoid idling
compshare start <new instance> --cardless B   # upload at ¥0.15/h
compshare push <new instance> <local model/code>
compshare stop <new instance>            # or go straight to start --gpu
```

Cardless mode (¥0.15/h) does not use GPU quota, so whether a 4090 is in stock does not affect the upload step.

## Billing and saving

Billing and cardless semantics live in one comment (above `BILLING` in `compshare.py`); the essentials:

- Pay-as-you-go: after shutdown GPU/CPU/memory stop billing, **disks and images keep billing**.
- Disks bill by capacity; deleting files does not reduce the charge. To save, shrink, delete the disk, or save an image and delete the disk.
- Custom images are free up to 30 GB, then ¥0.008/GB/day (cheaper than a cloud disk at ¥0.012/GB/day).
- Cardless mode is ¥0.15/h (`start --cardless A|B`; A = 2 cores/4 GB, B = 8 cores/16 GB).

## Watchdog

```bash
compshare start <id>            # attached at boot; --no-watch disables it
compshare watchdog <id>         # attach manually
compshare watchdog <id> --status
compshare watchdog <id> --off   # stop the watchdog only, instance untouched
```

One SSH read collects five quantities; any one over threshold counts as "busy":

| Quantity | Threshold | Why |
|---|---|---|
| max `utilization.gpu` across cards | ≥ 10% | the primary criterion |
| process count from `nvidia-smi --query-compute-apps` | > 0 | utilisation dips to 0 between iterations while the process still holds the card |
| `top` us+sy | ≥ 20% | data loading, CPU preprocessing |
| `loadavg1 / cores` | ≥ 0.5 | fallback |
| per-second NIC byte growth (non-lo) | ≥ 64 KiB/s | phases such as `pip install` or dataset transfer with low CPU but busy network |

loadavg alone misjudges: 8 of 16 cores saturated measured load 1.8.
CPU alone misjudges too: `pip install torch` showed CPU 0.4% and GPU 0, caught only by the network criterion (measured 259 KiB/s).

- `rounds` consecutive idle verdicts (default 20) → `StopCompShareInstance`.
- **No data → force shutdown**: `blind_max` consecutive rounds (default 5) without usable data (API/SSH error, or data holding no numbers) trigger an immediate `Stop` and a `force-stopped (no metrics)` log line. Reason: a watchdog that has lost observability is a machine burning money by the hour; a wrong stop costs a few hours, not stopping costs without limit. A failed force stop exits 3 and leaves `FORCE STOP FAILED`.
- Configuration lives in the `watchdog` section of `data/config.json`: `interval_seconds` / `rounds` / `gpu_util_min` / `cpu_busy_min` / `load_per_core_min` / `blind_max` / `boot_grace_seconds` / `boot_poll_seconds`.

Depends on `sshpass` (`brew install sshpass`) and the password in `data/instance-<id>.json`.

## Checking a machine after boot

```bash
.agent-tools/compshare info <id>            # one line of spec + one of IP + ssh ok/denied + watchdog
.agent-tools/compshare exec <id> 'nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader'
.agent-tools/compshare exec <id> 'python -c "import torch;print(torch.__version__, torch.cuda.is_available())"'
.agent-tools/compshare exec <id> 'nvcc -V | tail -2'         # required to build 3DGS
.agent-tools/compshare exec <id> 'df -h / /root | tail -2'   # whether the system-disk allowance suffices
.agent-tools/compshare exec <id> 'cat /proc/loadavg'
tail -f .agent-ide/skills/compshare/data/watchdog-<id>.log   # one line per watchdog round
```

`exec` returns remote stdout/stderr verbatim and **the exit code is the remote command's**, so `&&` works:

```bash
.agent-tools/compshare exec <id> 'test -f /root/.done && echo ready' || echo not-ready
```

`ssh denied` in `info` is usually an expired password in the record (someone reset it); fix the record or run `ResetCompShareInstancePassword`.
`ssh timeout` is host-side rate limiting: too many connections in a short window get refused for a while, one minute of waiting clears it. The tool already retries the first hop once and limits `NumberOfPasswordPrompts` to 1 so it is not mistaken for brute force.

**An `exec` straight after `start` will always fail to connect** — an instance takes about 40 s from `Initializing` to a listening sshd. But "wait 40 s" and "wait 10 minutes" are different things, so waiting is bounded and has a death condition:

- `exec` defaults to `--wait 120`: on connection-layer failures (timed out / refused / reset / banner) it retries, printing `waiting for ssh 26/120s` to stderr and `ssh ready after 40s (8 tries)` once connected. Authentication failures and non-zero remote exits are **not** retried and return immediately.
- Every third retry checks the instance state. A terminal state such as `Install Fail` / `Stopped`, or sitting in `Initializing` beyond `--init-grace` (default 300 s, matching the official "after 5 minutes contact the platform"), **stops at once** with the reason on stderr instead of burning the full timeout.
- To confirm "it is up" before working, use `ready <id>` (no side effects, exits on a death verdict) or `health <id>` (3 seconds).
- `--wait 0` restores the old behaviour (fail immediately); `info` uses 0 internally because it is only a quick state read.

## Local files (`data/`, 700, not transferred with the package)

| File | Contents | Mode | Note |
|---|---|---|---|
| `credentials.json` | `public_key` / `private_key` | 600 | the only credential source; deleting it removes access |
| `instance-<uhostId>.json` | region, spec, public/private IP, image, `login_user`, `ssh_port`, **plaintext password** | 600 | the watchdog and SSH depend on it; a new instance means a new file |
| `watchdog-<uhostId>.json` | `pid` / `started` | 600 | process liveness; `--off` deletes it |
| `watchdog-<uhostId>.log` | round-by-round verdicts | 600 | `busy` / `idle n/N` / `blind n/N` / `force-stopped` |
| `config.json` | optional `watchdog` overrides | default | absent means defaults |

## Panel

```bash
# runtime interpreter, for the reason above (system python3 lacks CA certificates)
/Users/wukunhuan/agent_ide_global_project/.agent-ide/runtime/standalone/python/darwin-arm64/python3.11/bin/python3.11 \
  <pkg>/panel/serve.py --port 8770          # open http://127.0.0.1:8770/
```

The panel sits in the package directory (`panel/`), works from any project, and does not depend on the project's `quick_access/`. It is a shell over the CLI: `/api/state` runs `images` + `stock` + `quote` and parses those output lines, injecting `COMPSHARE_NO_OPEN=1` into the CLI calls. **Changing CLI output format means changing the parsing in `panel/serve.py` in the same commit.**

## Cardless mode: downloads and installs should not burn GPU money

A carded pay-as-you-go instance bills **per machine** (unit price varies by card type; see `status`), and 0% GPU utilisation bills the same; cardless mode is ¥0.15/h, also 2 cores/4 GB (B tier 8 cores/16 GB). `hf download` / `pip` / `apt` / `gcc` / `scp` need no GPU at all.

Decide from `status`; switch when both conditions hold:

```
gpu=..., 0 %, 1 MiB        1 MiB of memory = no CUDA context
jobs are all hf / pip / apt / gcc / tar
```

Sequence (three pitfalls in the "cardless" part of the `BILLING` comment in `compshare.py`):

```bash
compshare stop $ID
compshare ls                     # wait for Stopped; start needs a terminal state
compshare start $ID --cardless A
compshare ssh-setup $ID          # required: the IP may change after start, so the alias must be rewritten
compshare doctor $ID
# ... download / install ...
compshare settle $ID             # stop when done; start with a card only for real training
```

Two hard reminders:

- **Shutdown does not hold the card**: the platform reclaims it, so a later `start` may fail for lack of one (change region or wait; do not hammer retries).
- **Cardless has no CUDA**: do not train there, and do not check `cuda.is_available()`; compiling `rasterizer` only needs nvcc, which works.
- **Judge a finished download against the file listing, not a `du -sm` total**: a `text_encoder/` holding only configs and no `.safetensors` still reaches the total, and that kind of gap only shows up with a per-file `test -s`.

## Choosing an image for 3DGS

40-series consumer cards are sm_89, and `diff-gaussian-rasterization` needs CUDA ≥ 11.8 to compile; on other architectures check that `nvcc -V` and `torch.cuda.get_device_capability()` agree. Pick a torch image whose name carries `cu12x` (e.g. `python310_torch240_cu124`); cu116 and below always fail. `App` in an image name means an application image (`root` + 23); `System` means a system image (`ubuntu` + 22).

## Confirmed unusable; stop trying

- **`Initializing` beyond 5 minutes, `Install Fail`**: official FAQ 1.1 classifies these as container start failure / destroyed environment, and the only remedies are reinstall, another image, or the platform. This is not slowness: waiting and restarting do not help.
- **Port 23 `refused`**: no sshd inside the container; port 22 on the same IP is the host's shared sshd and says nothing about your instance. Do not edit ssh config, do not raise `--wait`, do not retry `ssh -p 22`.
- **`GetCompShareInstanceMonitor`**: all four encodings of `UHostIds` (JSON string / `UHostIds.0` / repeated keys / comma-joined) return either 230 `Params [...UHostIds] not available` or 210 `Missing params [UHostIds]`; `MonitorMessages` in `DescribeCompShareInstance` stays empty for the first 15 minutes of `Running`. Monitoring only works over SSH.
- **Array parameters always use the indexed form**: `Disks.0.IsBoot` / `UHostIds.0`. A JSON string yields **200 with an empty body** (`Disks`) or 230 (`UHostIds`), and an empty body is not success.
- **`DescribeCompShareImages`** is plural; the singular returns 161 `Action not found`.
- **The console creation page offers no login-free deep link**, so no parameterised URL is generated — only `https://console.compshare.cn/`.

## Not yet verified

- Whether online disk shrinking is supported (`ResizeCompShareDisk` only shows growth).
- Whether other combinations of `create` name, password and image also return an empty body — only one parameter set has been used for a real creation.
- The API path for spot instances has not been exercised.
