# Failure table

Each row is a symptom, the one command that separates the candidates, and what the
answer means. The exit codes are the tool's own contract (see `SKILL.md` §Rules).

| Symptom | First check | Meaning |
|---|---|---|
| `autodl: no token …` (exit 3) | `autodl credentials` | token file empty or `AUTODL_TOKEN` unset |
| exit 4 | `autodl info <uuid>` | token rejected — wrong account, or pasted with a `Bearer ` prefix |
| exit 8 | nothing local fixes it | `无当前资源访问权限` = account×product gate on the dev API. Not 实名, not capacity: bogus spec/image/region return the same sentence, and an idle Pro card was refused too. Ask AutoDL to enable 「容器实例Pro 开放API」 for the account, quoting the `request_id` |
| exit 6 | the API's own message | the request itself was refused for some other reason |
| exit 7 | `ping`/retry | network to the API, not the instance |
| `autodl exec` exit 9 | `which sshpass` | `sshpass` missing locally; it will not prompt |
| `ssh: connect … refused` | `autodl info <uuid>` | still booting (sshd not up yet), or shutdown |
| `no kernel image is available` | `nvidia-smi --query-gpu=compute_cap` | extension compiled for other architectures |
| `not a supported wheel` | `python -V` vs the wheel's `cp3xx` tag | ABI mismatch, not a version issue |
| `CUDA out of memory` | `nvidia-smi` | something else resident, or the step is too big |
| `No space left on device` | `df -h /` | wrote to the system disk instead of `/root/autodl-tmp` |
| log stops mid-epoch, no traceback | `pgrep -af`, then `dmesg \| tail` | process killed (OOM killer) or the ssh session took it down |
| `release` refused | `autodl ls` | instance still running; `stop` first |
| job still alive past its deadline | `autodl info <uuid>` | timed shutdown is console-side; the API only reports it |

## The two that look like code bugs

`no kernel image is available` and a log that just stops are the pair that gets
misdiagnosed most often, because neither mentions its own cause.

For the first, the compile-time architecture list is the thing to read, not the
traceback:

```bash
autodl exec "$UUID" "python -c 'import torch;print(torch.cuda.get_device_capability())'"
# and the arch list the build was given:
autodl exec "$UUID" "grep -r 'gencode\|TORCH_CUDA_ARCH_LIST' /root/autodl-tmp/project/setup.py 2>/dev/null | head"
```

For the second, distinguish "died" from "hung" before touching the code:

```bash
autodl exec "$UUID" "pgrep -af python || echo gone; tail -n 40 /root/autodl-tmp/runs/exp1/out.log"
```

Gone with a clean tail means the kernel killed it (memory) or the session did
(signal). Alive with an old timestamp means it is waiting — a lock, a download, or
a dead socket.

## A log that stops right after "downloading"

Weights are being written to a full disk. This is the third variant of the same
mistake and it is worth checking `df -h /` before reading any stack trace.
