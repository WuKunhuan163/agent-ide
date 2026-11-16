# Lifecycle, billing and the CPU mode

An instance is in exactly one of three states, and only the first one bills.

| State | Costs money | Disk survives | How to reach it |
|---|---|---|---|
| running | yes, per second | yes | `create`, `start` |
| shutdown | no | yes | `stop` |
| gone | no | no | `release` |

`stop` keeps everything on disk: the image, the conda environments, `/root/autodl-tmp`.
`release` deletes the machine, and the disk with it. Only two things outlive a
`release`: a private image made with `image-save` (system disk only — the
environment, not `/root/autodl-tmp`), and whatever was copied off the box
beforehand. See `docs/artifacts.md` for which files have to make that trip.

## The CPU mode is console-only

AutoDL's "GPU-less mode" is a **billing tier without a GPU**: the machine boots and SSH
works as usual, it just holds no card, so it costs far less. It suits work that never
touches CUDA — editing code, installing dependencies, pulling weights down.
This API cannot reach it. `start` sends `payload: "gpu"`, which is the GPU boot,
and there is no second payload value. So:

- The only way in is the console's "boot in GPU-less mode"; `autodl start` boots with the GPU.
- A machine already in GPU-less mode still shows `running` in `ls`, and `exec` still works --
  the tell is the GPU field in `info <uuid>` and whether `nvidia-smi` errors, not the status word.
- Switching between GPU-less and GPU on a running machine needs a console stop/start; it is not hot-swappable.

This is the one place where the honest answer is "the CLI is not enough, go to the
console", and pretending otherwise only costs a GPU-hour.

## Spend checklist before `create`

1. `ls` — is one already running? Reuse it. Two boxes on one account is how a
   bill doubles without anyone noticing.
2. `info <uuid>` — if it exists, what does it cost per hour right now?
3. `gpus` — the spec id and the region. A region with no free card defers the boot.
4. `create --gpu <spec> --image <uuid> --yes` — bills from the first second, so
   intend to use it immediately, not "after I finish editing locally".

`create` prints only the new id; capture it:

```bash
UUID=$(autodl create --gpu v-48g --image base-image-l2t43iu6uk --yes)
```

## Shutdown discipline

There is **no timed-shutdown endpoint**: the API only reports `timed_shutdown_at`
when one was set in the console. And a container cannot power itself off — a
`--start-command "…; poweroff"` does not end the spend.

So the only reliable stop is an outside call. Two habits that work:

- Nor does a wrapper on the box help: `nohup …; wait; poweroff` ends the process,
  not the billing. The stop has to come from this side:

  ```bash
  autodl exec "$UUID" "tail -n 1 /root/autodl-tmp/runs/x/metrics.jsonl" || true
  # when the log says done:
  autodl stop "$UUID"
  ```

- Or set a "scheduled shutdown" in the console as a backstop, and let the local log decide whether to `stop` earlier.

## Snapshots

`image-save <uuid> --name <name>` freezes the system disk into a private image, so a
later `create` starts with the same CUDA, torch and compiled extensions. It is worth
doing exactly once — after the environment is proven by a real run, not after a
successful `pip install`. The data disk is **not** part of the image: weights, runs
and checkpoints stay behind.

A snapshot costs disk quota, not GPU time; the expensive part of an environment is
the rebuild, not the image.

## When to `release`

Release when the disk holds nothing you cannot regenerate: no checkpoints, no runs,
no downloaded weights. Otherwise leave it in `shutdown`, which is free and keeps
`/root/autodl-tmp`. `release` is refused while the instance is running, so the order
is always `stop` then `release`.
