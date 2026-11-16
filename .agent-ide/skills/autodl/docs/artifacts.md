# Bringing things back

A box is rented by the hour and can be `release`d by one command, so the question
is never "will I remember this" — it is **what leaves the box before the box goes
away**. Three kinds of thing, three different answers.

| Kind | Examples | Where it ends up | Pull back? |
|---|---|---|---|
| Code | `modules/`, `configs/`, `run.py` | the laptop stays the source of truth; the copy on the box is disposable | no |
| training metadata | `metrics.jsonl`, `loss.csv`, `renders/`, `*.log`, `manifest.json`, `latest.ply` if small | pulled back into the local `runs/<exp>/` | **yes, always** |
| Weights and caches | `*.pt`, model dirs, `HF_HOME`, compiled extensions | stays on `/root/autodl-tmp` | no — too big, and reproducible |

The split matters because it decides what has to be checked. Code has no return
trip: it is edited here, rsynced out, and if it differs from the laptop that is a
bug. Weights have no return trip either: they are rebuilt by a script. Only the
middle row is irreplaceable — a 12-hour run's numbers exist nowhere else.

## What `stop` and `release` actually do

**`stop` and `release` differ in what they keep and what they bill**: read the power and cost columns together before choosing one.

| Action | Power | `/root/autodl-tmp` | Cost |
|---|---|---|---|
| `stop` | off | **kept** | stops |
| `start` | on | kept | resumes |
| `release` | gone | **deleted** | stops, instance unrecoverable |
| `image-save` | — | **not included** | storage for the image |

So `stop` is not the deadline; `release` is. Pulling results back is urgent only
when the instance is about to be released or reclaimed — not every time it is
powered off. What `stop` does require is that nothing is still running, because a
job dies with the boot.

`image-save` captures the **system disk** — the environment: installed packages,
the compiled rasterizer, pinned versions. It does not capture the data disk. An
image is how the next box skips a 40-minute install; it is never how a checkpoint
survives.

## The pull, in order

**The pull is ordered, and the order is what makes it resumable**: the block below is the sequence, not a menu.

```bash
# 1) what is there, and what is large enough to think about
autodl exec "$UUID" "du -sh /root/autodl-tmp/runs/exp1; \
  find /root/autodl-tmp/runs/exp1 -type f -size +100M"

# 2) reverse rsync; -P resumes, no --delete on a pull
SSHCMD=$(autodl ssh "$UUID" | head -1)
PORT=$(echo "$SSHCMD" | sed -n 's/.*-p *\([0-9]\{2,\}\).*/\1/p')
HOST=$(echo "$SSHCMD" | sed -n 's/.*@\([^ ]*\).*/\1/p')
rsync -avzP -e "ssh -p $PORT -o StrictHostKeyChecking=accept-new" \
  root@$HOST:/root/autodl-tmp/runs/exp1/ \
  ./workspace/01_pipeline_geometry/1.1_sim_3dgs/runs/exp1/

# 3) verify before releasing the box
autodl exec "$UUID" "find /root/autodl-tmp/runs/exp1 -type f | wc -l"
find ./workspace/01_pipeline_geometry/1.1_sim_3dgs/runs/exp1 -type f | wc -l
```

A silent truncation is the failure mode that hurts: `rsync` interrupted midway
leaves a plausible-looking `metrics.jsonl` with the last 3000 steps missing, and
nothing about it looks wrong when opened. Two cheap checks catch it — file count
on both sides, and the last line of the metrics file matching the step count in
`manifest.json`.

## Where it lands locally

**Where a pulled artefact lands is decided by the command, not by where you were standing**: the tree below is the result.

```text
workspace/<stage>/<experiment>/runs/<YYYYMMDD-HHMM>/
  manifest.json      what ran: config hash, seeds, steps, git rev
  metrics.jsonl      one line per logged step
  logs/              stdout of the run
  renders/           panels, strips — pulled back, not regenerated
```

The date in the directory name is the run start, not the pull time, so two pulls
of the same run land in the same place and `rsync` makes the second one a no-op.

These files are training metadata in this repo's vocabulary — the same word used for what
comes back from Kaggle. They are read locally, quoted in the thesis, and are the
only evidence that a number was produced by a run rather than typed.

## Big artifacts: three routes, none of them rsync

1. **Leave it running.** `stop` keeps the disk; come back tomorrow. This is the
   default and costs nothing while stopped.
2. **`image-save`** before `release` — environment only, not checkpoints.
3. **Upload from the box** to a netdisk / object store, then pull from there. The
   only route if the instance must be released and the checkpoint is 1 GB+, since
   a laptop-side `rsync` of that size over a home connection is the slowest link
   in the chain — and it will be attempted exactly once, at the worst moment.

`release` is irreversible, so the order is: pull training metadata → decide about the
weights → `image-save` if the environment was expensive → `release`.
