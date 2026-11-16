# Disks, and moving code and data across

Two filesystems exist on every AutoDL box, and confusing them is the most common
way to lose an afternoon.

| Path | What lives there | Survives | Size |
|---|---|---|---|
| `/` (system disk) | image, apt packages, conda envs, `/root/*` except the data disk | power-off | small |
| `/root/autodl-tmp` | whatever you put there | power-off | large |

Never hardcode either number. Ask:

```bash
autodl exec "$UUID" "df -h / /root/autodl-tmp"
```

The rule that follows: **weights, datasets, runs and pip caches go on
`/root/autodl-tmp`; only the environment stays on `/`.** A 5 GB checkpoint written
to `$HOME` fills a small system disk and the failure surfaces as a write error
halfway through training, which reads like a code bug.

## Where a project should live

**A project lives on exactly one disk, and the one it lives on decides whether it survives a release**: the tree below is the layout that follows.

```text
/root/autodl-tmp/
  models/        kolors, sd2, conditioning artifacts
  data/          meshes, images, inputs
  runs/<exp>/    logs, checkpoints, metrics.jsonl, renders
  cache/         HF_HOME, TORCH_HOME, pip cache, TMPDIR
```

Every one of those is then addressable from the code through environment
variables, so the same checkout runs on Kaggle and here without edits:

```bash
export WORK_DIR=/root/autodl-tmp/runs/exp1
export DATA_DIR=/root/autodl-tmp/models:/root/autodl-tmp/data
export HF_HOME=/root/autodl-tmp/cache/hf
export TMPDIR=/root/autodl-tmp/cache/tmp
```

## Code: rsync from the laptop

`autodl ssh <uuid>` prints two lines: the ssh command, then `password <pw>`.
`rsync` wants the two parts separately:

```bash
SSHCMD=$(autodl ssh "$UUID" | head -1)     # ssh -p 12345 root@region.example.com
PORT=$(echo "$SSHCMD" | sed -n 's/.*-p *\([0-9]\{2,\}\).*/\1/p')
HOST=$(echo "$SSHCMD" | sed -n 's/.*@\([^ ]*\).*/\1/p')

rsync -avzP --exclude='.git' --exclude='__pycache__' --exclude='runs/' \
  -e "ssh -p $PORT -o StrictHostKeyChecking=accept-new" \
  ./project/ root@$HOST:/root/autodl-tmp/project/
```

`-P` keeps partial files, so an interrupted sync resumes instead of restarting.
Reverse the two sides to pull results back.

For a repo that already has a remote, `git clone` on the box is cleaner than
`rsync` — but only after pushing, and it drags `.git` history onto a disk you pay
for.

## Data: prefer the platform's own downloader

Downloading 5–12 GB of weights from outside China is the slowest step in the whole
setup. Two routes that work:

- ModelScope (`pip install modelscope`), which is fast from inside AutoDL and
  carries Kolors, SD2 and most public checkpoints.
- HuggingFace with a mirror endpoint: `export HF_ENDPOINT=https://hf-mirror.com`.

Then set the cache to the data disk **before** the download, not after:

```bash
export HF_HOME=/root/autodl-tmp/cache/hf
```

Otherwise the 12 GB lands on `/` and the box is unusable before the download ends.

## Verify what arrived

A truncated download shows up as a JSON parse error or an unexpected `safetensors`
size, minutes into a run. Check sizes at the end of the transfer:

```bash
autodl exec "$UUID" "du -sh /root/autodl-tmp/models/* && find /root/autodl-tmp/models -name '*.incomplete'"
```

`*.incomplete` means HF gave up and left a partial blob. Delete it before retrying,
or the next run resumes into a corrupt file.
