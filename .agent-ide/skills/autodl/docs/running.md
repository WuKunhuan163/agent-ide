# Running work on the box

`exec` is one command over ssh, and it returns when the command returns. That
makes it right for probes and wrong for training.

## Two categories

| Work | How | Why |
|---|---|---|
| probe: `nvidia-smi`, `df`, `ls`, one-step smoke | `autodl exec <uuid> "…"` | seconds, you want the answer inline |
| training: anything from minutes to hours | `nohup … &` then poll the log | the ssh session dies, the process must not |

A long job started through `exec` without `nohup` dies with the session. The symptom
is a log that stops mid-epoch and no error anywhere.

## Long jobs

```bash
autodl exec "$UUID" "cd /root/autodl-tmp/project && mkdir -p /root/autodl-tmp/runs/exp1 && \
  nohup python run.py --config configs/exp1.yaml > /root/autodl-tmp/runs/exp1/out.log 2>&1 & \
  echo started \$!"
```

Then poll without holding a session:

```bash
autodl exec "$UUID" "tail -n 3 /root/autodl-tmp/runs/exp1/out.log"
autodl exec "$UUID" "pgrep -af run.py || echo gone"
```

`pgrep` plus the tail is the honest pair: one says whether the process is alive, the
other what it last said. A crashed job leaves the process gone and the traceback in
the log; a hung job leaves it alive with a timestamp that stops moving.

## Logs are the interface

Write them to the data disk, one file per run, and make the first line say what
produced them:

```bash
echo "== $(date -Is) $(hostname) $(git rev-parse --short HEAD)" >> out.log
```

Without that line, two runs compared a week later cannot be told apart — same
command, same config name, different code.

If the code already writes `metrics.jsonl` or an equivalent, prefer tailing that:
a parsed number per line is easier to read over ssh than a wall of progress bars.

## Exit codes

`exec` propagates the remote exit code, so the local shell sees the real result:

```bash
autodl exec "$UUID" "python -c 'import torch'" || echo "torch import failed"
```

Note that a `nohup ... &` wrapper returns 0 because the *launch* succeeded, not the
job. Only the log or `pgrep` tells you how the job itself went.

## Ending a run

Three things happen in this order, and skipping the last one is what costs money:

1. pull the results back (`rsync` in reverse, or a single `tar czf - | ssh … "cat >"`);
2. check nothing important is only on the box (`du -sh /root/autodl-tmp/runs/*`);
3. `autodl stop <uuid>`.

Step 1 is not optional and step 3 does not delete anything — the disk survives a
`stop`. What makes step 1 urgent is `release`. Layout, verification and the
weights-vs-训练meta split live in `docs/artifacts.md`.

If the run is long enough that you will not be watching, set a console-side timed
shutdown as a backstop — the API can read `timed_shutdown_at` but cannot set it.
