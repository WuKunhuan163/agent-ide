# The watchdog: what turns the box off while nobody is watching

`stop` is the only thing that ends the bill, and a container cannot stop itself.
The watchdog is the piece that does it from the outside, on a timer, without a
human deciding in the moment.

It is not "stop when the SSH session drops". Three facts make that the wrong rule:

1. A container cannot power itself off — `poweroff` ends the process, not the billing.
2. A dropped SSH session is invisible to the container; from its side nothing happened.
3. `nohup` jobs are *supposed* to outlive the session. Stopping on disconnect would
   kill a twelve-hour run on the first network hiccup.

What actually leaks money is the third case: the run finished at 03:10, nobody was
awake, and the GPU sat idle until morning. So the rule is **"no job, no writes,
thirty checks in a row"** — not "no connection".

## Arming it

**Arming it is one command and it survives your shell**: the block below is what you type, and the machine keeps doing it after you disconnect.

```bash
autodl start <uuid>            # power on, watchdog armed automatically
autodl start <uuid> --no-watch # power on bare, for a manual session
autodl watchdog <uuid>         # arm it by hand; prints the pid
autodl watchdog --status       # one line: running pid=… uuid=… since=… idle=… rounds=…
autodl watchdog --off          # stop the watchdog, leave the instance running
autodl watchdog <uuid> --foreground   # stay in this terminal (debugging the probe)
```

Arming is part of `start`, so the normal way to open a box cannot forget it.
The process is detached
(`setsid`-style, its own session), survives the shell that spawned it, and writes
to `data/watchdog.log`.

It does not start counting on the spot: `power_on` returns while the box is still
`starting`. The watchdog first waits for `running` (up to `boot_grace_seconds`),
logs `running; watching usage`, and only then begins the streak. If the boot is
cancelled or fails, it exits with a reason instead of waiting out the grace:

## What one tick does

**One tick is a fixed sequence of checks, and the block below is its literal order** — a check moved earlier changes what a tick can still save.

```text
state != running (after it has been running)? → exit, nothing to watch
ssh probe fails?                              → hold: do not count this round (see below)
a process holds the GPU / GPU busy / load high / file written in last N min?
                                              → streak = 0
otherwise                                     → streak += 1; stop when streak == rounds
```

The probe is a single SSH round-trip, and it measures **physical quantities, not
process names**:

```bash
echo "load $(cut -d' ' -f1 /proc/loadavg)"                       # one-minute load
echo "apps $(nvidia-smi --query-compute-apps=pid … | grep -c '[0-9]')"  # processes on the card
echo "util $(nvidia-smi --query-gpu=utilization.gpu … | paste -sd, -)"  # max % across cards
echo ---AUTODL---
find /root/autodl-tmp -maxdepth 4 -type f -mmin -1 | head -3
```

Two details that matter:

- **No name list.** The earlier probe grepped for `run.py|train.py`, which meant a
  renamed entry point, a `torchrun` wrapper, or a CPU-mode box all looked idle — a
  box silently billing while the watchdog counted down. Any GPU compute process,
  any card above `gpu_util_min`, or load above `cpu_load_min` now counts.
- **Several signals, not one.** GPU utilisation alone is not enough: a cold mount
  of a 5 GB checkpoint takes four minutes with the GPU at 0%, which is exactly
  when a GPU-only rule would kill the run. Hence process *or* utilisation *or*
  load *or* a recently written file.

## When the probe cannot answer

`ssh` exits non-zero, the network is down, the box is still booting. The tick is
dropped, the streak stays where it was, and the log says so:

```text
2026-10-27T11:05:02 network down (attempt 3): will retry, streak stays at 1
```

This is deliberate asymmetry. A false stop costs a rerun; a missed stop costs
money. The watchdog always chooses the cheaper mistake, which means **it never
stops a box it cannot see into**.

Network loss is not fatal: the loop sleeps one interval and tries again, so a
laptop that went offline for an hour resumes counting without intervention. Mac
sleep is the same shape — the process is suspended, not killed, and continues on
wake.

The one exception is authentication: if the token becomes invalid (`exit 4`) the
watchdog exits immediately, because it can never call `power_off` again and
polling would only produce noise. It says so in the log.

## Configuration

No environment variables. Everything is a file, in `data/config.json`:

```json
{
  "base_url": "",
  "auto_approve": true,
  "watchdog": {
    "interval_seconds": 60, "idle_minutes": 1, "rounds": 30,
    "boot_grace_seconds": 900, "gpu_util_min": 10, "cpu_load_min": 1
  }
}
```

| Key | Default | Means |
|---|---|---|
| `interval_seconds` | 60 | time between checks |
| `idle_minutes` | 1 | a file written this recently counts as "still working" |
| `rounds` | 30 | consecutive idle checks before `power_off` |
| `boot_grace_seconds` | 900 | how long to wait for `power_on` to reach `running` |
| `gpu_util_min` | 10 | a card at this utilisation or above counts as busy (%) |
| `cpu_load_min` | 1 | one-minute load at or above this counts as busy (CPU mode) |

60 s × 30 rounds = **30 minutes** from the last sign of life to `power_off`. The
window is the operator's call, not a default to be improved on: one check a
minute, thirty consecutive quiet minutes, off. The write window stays 1 minute
because it only has to catch the moment a job starts writing.

`--interval`, `--idle` and `--rounds` override them for one arming, and the
spawned process receives the same numbers, so what is running matches what was
asked for.

**Nothing to keep in sync.** Thresholds are numbers, not names: no entry point
has to be registered anywhere for the watchdog to see it.

## State and logs

**The watchdog keeps its own state on disk, and the table says which file survives a reboot**: anything not in that column is lost with the machine.

| File | Holds | Survives reboot |
|---|---|---|
| `data/watchdog.json` | uuid, pid, started, `phase` (`booting`/`watching`), the settings | no — removed when the loop ends |
| `data/watchdog.log` | one line per tick, one per failure, the reason for every stop | yes, appended |

`--status` reads the pid and checks whether it is alive; a killed process leaves a
state file behind, which `--status` reports as `stale pid=…`.

Reading the log after the fact is how you answer "why did it stop at 03:40":

```text
2026-10-27T03:10:00 tick idle 27/30
2026-10-27T03:11:01 tick idle 28/30
2026-10-27T03:12:02 tick idle 29/30
2026-10-27T03:13:03 stop: idle on 30 consecutive checks; calling power_off
2026-10-27T03:13:05 stopped; billing ends here
```

## What it will not do

- It never calls `release`. Stopping is reversible, deleting is not.
- It does not start the box. Power-on stays a decision, not a consequence.
- It does not survive the laptop being shut down — nothing on this side does. If
  that is the concern, the watchdog is not the answer; the answer is not to leave
  a box running while the laptop is off.
