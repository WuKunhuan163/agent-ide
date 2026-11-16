---
name: autodl
description: >-
  AutoDL GPU rental helper: inspect stock, start, stop and release a Container Instance Pro
  instance over the official API, then log in or run one command on it. Read this
  skill when a GPU box must be inspected or run on, or when a running box must be
  stopped so billing ends.
---

# autodl

Billing depends on exactly one thing: whether the instance is powered on. Idle and saturated cost the same, so this tool exists mainly for `stop` and for answering "what is still running".

## Verbs

**Pick the task you are doing, not the verb you remember**: every row is one task with the one command that does it.

| Task | Command |
|---|---|
| which token is in use | `credentials` / `credentials --set-token <t>` |
| available specs, images, regions | `gpus` |
| where a card type has stock | `stock [--region A,B] [--gpu <exact id>]` (no prices, by design) |
| instances on the account | `ls [--page N] [--size N] [--status running]` |
| state, ssh, price, ports, live load | `info <uuid>` |
| power on / power off | `start <uuid> [--start-command CMD] [--no-watch]` / `stop <uuid>` |
| wait for stock and get a console deep link | `watch --gpu <substr> --region <substr> [--max-price CNY] [--minutes N]` |
| destroy | `release <uuid> --yes` (snapshot first) |
| log in / run one command | `ssh <uuid>` / `exec <uuid> "nvidia-smi"` |
| private images | `images`, `image-save <uuid> --name <name>` |
| market prices and machine types | `market [--gpu substr] [--pro] [--all]` |
| automatic shutdown | `watchdog [uuid] [--foreground] \| --status \| --off` |

**There is no `create`**: the developer API does not rent machines, so new instances are created in the console only; this tool powers existing instances on and off and executes on them. There is also no `await` (now `watch`) and no `start --cpu`.

## Entry

**There is exactly one entry point per machine, and it prints the facts the rest of the session depends on.**

```bash
python3 .agent-ide/skills/autodl/autodl.py <command> [args]
# or, once installed
.agent-tools/autodl <command> [args]
```

## Data

All state is files under `data/`; no environment variables are read, so the same `data/` behaves identically in any shell.

`data/credentials.json` (0600, gitignored):

```json
{ "token": "", "account": "", "defaults": { "gpu_spec": "", "image": "", "cuda": 118, "region": "" } }
```

- `token` is the only required field; when missing, exit 3 names the file and the console path.
- `account` is echoed only.
- `defaults.*` is currently echoed by `credentials` and consumed by nothing — do not assume filling it saves you the argument.

Only one kind of token works: console → settings → developer token, pasted **verbatim** (no `Bearer `), a JWT whose `aud` is `develop_api`. Both product lines share it, both at `https://api.autodl.com`:

| Product line | Same token | Extra condition |
|---|---|---|
| Container Instance Pro (`instance/pro/*`) | yes | personal or enterprise verification |
| Elastic Deployment (`deployment/*`) | yes | enterprise verification |
| Elastic Deployment GPU stock (`machine/region/gpu_stock`) | yes | none |

Two look-alikes are deliberately **not** stored:

- Browser session tokens: the same JWT shape, but `aud` is not `develop_api`, every developer endpoint rejects it, and storing it only manufactures false "login timed out" leads.
- `private.autodl.com`: not a developer API host — `instance/pro/list` 404s there and the stock path answers `AuthorizeFailed`.

`credentials --set-token` validates with `POST /instance/pro/list` (the lowest bar that needs no extra permission) and writes nothing when validation fails.

`data/config.json` holds only `base_url` (empty means the official host; a value points at a proxy or local stub) and the `watchdog` block.

## Rules

1. **stdout is the answer, stderr is narration.** Data from `ls` / `images` / `info` / `gpus` / `stock` / `ssh` / `exec` goes to stdout, one record per line, no header, no totals, no prefix. Diagnostics (paging hints, warnings, failures) go to stderr prefixed `autodl: `. There is no `--json`.
2. **Success is silent.** `start` / `stop` / `release` / `credentials --set-token` print nothing on success; the exit code is the receipt. `image-save` prints only the new `image_uuid`, so it can be captured.
3. **Exit codes are a machine contract.** 0 success, 1 other/interrupted, 2 usage, 3 no token, 4 credentials rejected, 5 endpoint not found, 6 API refused the request, 7 network, 8 no access to the current resource, 9 cannot ssh non-interactively. `exec` passes the remote exit code through unchanged.
4. **Spending requires `--yes`.** `release` always needs a human `--yes`: without it, print `refused: … --yes to release` and exit 2.
5. **`release` requires a stopped instance.** When the state is not `shutdown`, exit 2 and suggest `autodl stop <uuid>`; one call never both stops and destroys.
6. **Every start carries a watchdog.** `start` detaches one before returning; see `docs/watchdog.md`. Known defect: `--foreground` raises KeyError on a missing `tokens` key, so foreground debugging is unusable.

No polling: `start` / `stop` / `release` return as soon as the API accepts them; check the outcome afterwards with `info <uuid>`.

## Limits

- Covers **Container Instance Pro** only, pay-as-you-go only. Console standard instances are not addressable; an instance absent from `ls` is out of this tool's reach.
- **The API cannot start without a GPU.** The official Pro documentation states `payload` takes `gpu` and that API start without a card is not supported yet. Cheap code edits go through the console's no-card mode.
- **There is no scheduled-shutdown endpoint**; the API only reports `timed_shutdown_at`.
- **A container cannot stop itself.** `--start-command "…; poweroff"` does not end billing; only an external `stop` does.
- **`no access to the current resource` is an account × product gate** — not lack of stock, not verification. Invalid parameters (`{}`, `disk 9999`) are rejected earlier by validation with `RequestParameterIsWrong`, while a forged `gpu_spec_uuid`, a forged `image_uuid` and a forged region all return the same sentence, which means a single gate sits in front of resource lookup. Waiting for stock is useless; the account needs Container Instance Pro API access enabled, and support needs the `request_id`.
- **`stock` reports `idle/total` per GPU model, not per Pro spec, and counts single cards**: 200 idle 4090s do not mean an 8-card machine. The response is `[{model: {total_gpu_num, idle_gpu_num, chip_corp, cpu_arch}}]` with no price field. `region_sign` is required: the region lives in the request, not the response, so query region by region and merge.
- **`stock --gpu` matches the whole identifier**: `4090` is rejected (it wants `RTX 4090`) and the error lists the accepted identifiers. The response shape is undocumented, so parse by structure rather than field position and exit 6 with one line on an unseen shape.
- **`market` is the only endpoint with prices, and it needs no token.** It calls `POST /api/v1/machine/list` (body: `page_index` / `page_size` / `region_sign_list` / `gpu_name_list` / `charge_type: payg`) and returns `region_name`, `gpu_idle_num`, `payg_price` (**whole-machine price**; divide by `gpu_number` for a per-card price) and `enable_container_pro` (whether the machine can host a Pro instance) — none of which the developer API exposes. By default it lists only `gpu_idle_num>0`.
- **`payg_price` has two scales; check where a number came from.** On the `market`/`watch` side it is treated as **li** (1/1000 yuan) (`round(price/10)` gives fen, then ÷100 gives yuan, so 1980 → ¥1.98/card·h); on the `info`/`snapshot` side it is taken directly as **fen** (÷100). Same name, different scale, not unified in code — confirm the source command before cross-referencing.
- **The envelope is the judge.** Success is only `code == "Success"`; HTTP status is ignored (a rejection also arrives as 200). Keep the `request_id` on rejection — it is the only string support can trace.
- `snapshot` and `status` are documented as `GET` with a JSON body, which is not portable; they are actually sent as query parameters.

## Reading `AuthorizeFailed`

The message is `login timed out, please sign in again` — it describes the symptom, not the cause. Every auth failure also carries a local diagnosis: the `aud` extracted from the JWT.

| `aud=…` | Meaning | Next step |
|---|---|---|
| `develop_api` | right type, expired or revoked | regenerate (re-logging into the console invalidates old tokens); if a fresh token also fails, the account cannot use Container Instance Pro yet |
| anything else | issued for another audience | wrong string pasted |
| absent | not a signed token | copy the developer token itself |

`credentials` prints the same field, so the credential type is visible before any rental.

## On the box

1. **Two filesystems, one rule.** `/` is small and holds only the environment; `/root/autodl-tmp` is large and holds weights, data and runs. Always measure with `df -h / /root/autodl-tmp`.
2. **`start` powers on with a GPU by default.** To edit code without paying for a card, use the console's no-card mode; the API has no such path.
3. **Probes go through `exec`, long jobs through `nohup`.** Training inside `exec` dies silently with the session.
4. **`stop` is the only action that ends billing.** A container cannot stop itself and there is no scheduled-shutdown API; the watchdog attached by `start` stops it when nothing is running.
5. Artefacts cannot live only on the machine: `stop` keeps the data disk, `release` deletes it — pull results back before releasing.

## ssh and exec

`ssh <uuid>` prints the ssh command and the root password (from the snapshot); the first line is the command, so `head -1` works. `exec` needs a non-interactive path, i.e. `sshpass` (`brew install hudochenkov/sshpass/sshpass`); when it is missing, exit 9 with one line rather than hanging on a password prompt.

## Files

**The files below are the tool's whole footprint**: anything not listed is written by the project, not by the skill.

| File | Holds |
|---|---|
| `src/client.py` | data files, endpoint paths, envelope, failure classification |
| `autodl.py` | the entry itself: verb routing, spend gates, line formats |
| `src/watchdog.py` | background shutdown: probe, criteria, detach, state file |
| `data/README.md` | field-by-field notes on which file to fill |
| `docs/*.md` | machine-side detail: lifecycle, disks, environment, long jobs, artefacts, watchdog, symptom table |
