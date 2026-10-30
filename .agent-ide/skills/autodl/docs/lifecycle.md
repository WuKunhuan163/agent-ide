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

AutoDL 的「无卡模式」是一台**没有 GPU 的计费档**：机器照常开机、SSH 照常可用，
只是不占显卡，所以便宜得多。它适合改代码、装依赖、下行模型这类不碰 CUDA 的活。

This API cannot reach it. `start` sends `payload: "gpu"`, which is the GPU boot,
and there is no second payload value. So:

- 要进无卡模式，只能去控制台点「无卡模式开机」；`autodl start` 只会开 GPU。
- 已经在无卡模式里的机器，`ls` 依然显示 running，`exec` 依然可用 —— 判断依据是
  `info <uuid>` 里的 GPU 字段与 `nvidia-smi` 是否报错，不是状态字符串。
- 开机状态的机器，无卡与有卡之间切换要再走一次控制台关机/开机，不能热切。

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

- 或者干脆在控制台设「定时关机」兜底，再在本地按日志决定是否提前 `stop`。

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
