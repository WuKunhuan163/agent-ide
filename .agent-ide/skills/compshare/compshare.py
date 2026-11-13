"""The compshare command line: stock, quote, power on/off, create.

Same principles as the autodl skill: one line per record, space-separated fields, missing data left empty, never guessed.
Stock must go through CheckCompShareResourceCapacity — it is the only endpoint the official docs allow for
deciding whether something can be rented right now (https://www.compshare.cn/docs/gpus/instance/checkcompshareresourcecapacity);
fields on Describe-class endpoints do not mean sellable.
"""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import os
import json
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from src import client, lifecycle, ops, sshsetup, transfer, watchdog
from src.client import ApiError, NoCredentials

# The console create page offers no login-free deep link, so only the entry point is given; no parameterised URL is invented.
CONSOLE_URL = "https://console.compshare.cn/"

# Official region table (2026-10 docs). Container regions have no separate public IP and ship a 50G free local system disk.
# Source: https://www.compshare.cn/docs/operation/gpu/disk
ZONES = [
    ("cn-wlcb", "cn-wlcb-01", "North China 2A", "VM"),
    ("cn-sh2", "cn-sh2-02", "Shanghai 2B", "VM"),
    ("cn-bj2", "cn-bj2-03", "North China 1C", "Container"),
    ("cn-sh2", "cn-sh2-01", "Shanghai 2A", "Container"),
    ("cn-sh2", "cn-sh2-03", "Shanghai 2C", "Container"),
]

# Billing semantics (official docs: https://www.compshare.cn/docs/operation/charge/billdescribe):
#
# | Item | After shutdown | Unit price |
# |---|---|---|
# | GPU / CPU / memory | stops | — |
# | System disk (within allowance) | billed, but 0 | 100GB free in VM regions; 50GB free in container regions |
# | System disk (over allowance) | billed | 0.0005 CNY/GB/hour ≈ 0.012 CNY/GB/day |
# | Data disk | billed | as above; billed from creation regardless of content or mounting |
# | Custom image | billed | free up to 30GB, then 0.008 CNY/GB/day |
# | Cardless mode | billed 0.15 CNY/hour | tier A 2 cores/4G, tier B 8 cores/16G |
#
# Corollary (the only correct direction for saving money): disks bill by **capacity**, not by content — deleting files saves nothing,
# only shrinking or deleting a disk does. Within the allowance, do nothing; over it, if the environment must be kept, save a custom image
# (0.008 < 0.012 CNY/GB/day) and then delete the disk; if the environment is reproducible, just delete the disk. Note layered image storage:
# deleting files only records a "deleted" marker and does not shrink the image; a smaller image must be rebuilt from a clean base.
#
# ## Cardless mode (0.15 CNY/hour, A = 2 cores/4G, B = 8 cores/16G)
#
# The two prices differ by more than 13.7×: carded pay-as-you-go bills per machine and charges at 0% GPU utilisation, cardless charges only 0.15 CNY/hour.
# Do not memorise the carded unit price — it is set by card type, region and billing mode together; the only trustworthy sources are
# `price_cny_per_hour` in `data/instance-<id>.json`, and `status` deriving it from spent/uptime.
#
# `hf download`, `pip install`, `apt install`, `gcc` builds and `rsync`/`scp` need no GPU at all.
# One criterion, read from `status`: `gpu=..., 0 %, 1 MiB` (1 MiB = no CUDA context)
# and every job is hf / pip / apt / gcc / tar. When both hold, go cardless instead of arguing that training starts soon.
#
# Standard sequence: stop → ls (until Stopped) → start --cardless A → ssh-setup → doctor → work
#           → settle (wrap-up shutdown) → start with a card for real training + ssh-setup.
#
# Three pitfalls:
#   1. Shutdown does not hold the card. Once the platform reclaims the GPU someone else can rent it, so a later start may have nothing to allocate. The right moment to go cardless is
#      "the download is already large and no GPU is needed soon", not "boot → stop at once → boot again"; if attaching a card fails, change region (check
#      `stock` first) or wait — do not hammer retries (the platform rate-limits).
#   2. After start the IP (and sometimes the port) changes, while exec reads the old IP from `data/instance-<id>.json`;
#      run `ssh-setup` after every start, or you will connect to a machine that no longer exists.
#   3. Cardless mode has no CUDA. Do not train there, and do not verify with `torch.cuda.is_available()`;
#      compiling the rasteriser only needs nvcc, not a card.
BILLING = {
    "system_disk_free_gb": {"cloud": 100, "pod": 50},
    "disk_cny_per_gb_hour": 0.0005,
    "image_cny_per_gb_day": 0.008,
    "image_free_gb": 30,
    "cardless_cny_per_hour": 0.15,
}


# Exit codes: one source of truth. The table in SKILL.md syncs from here; no more scattered literals.
RC_OK = 0            # usable / success
RC_API = 1           # the API returned an error
RC_USAGE = 2         # usage error
RC_STOCK = 3         # insufficient stock / force-stop failed
RC_NET = 10          # network failure
RC_NOCRED = 20       # no credentials
RC_UNAVAILABLE = 30  # instance unusable (timeout or judged dead)
RC_STOPPED = 31      # powered off
RC_JUPYTER = 32      # Jupyter channel only
RC_RELEASABLE = 33   # machines are due for return (verdicts --stale hit)


def _json_out(payload) -> None:
    """Machine-readable output. The agent reads this instead of parsing prose with split()."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def out(line: str = "") -> None:
    print(line, flush=True)


def err(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


# ---------- basic queries ----------

def cmd_zones(args) -> int:
    data = client.call("DescribeCompShareSupportZone")
    for z in data.get("ZoneInfo") or []:
        out(f"{z.get('Region','')} {z.get('Zone','')} {z.get('Describe','')} {z.get('ZoneId','')}")
    return 0


def _paged(action: str, key: str, *, id_field: str, region: str | None = None,
           zone: str | None = None, page: int = 100, **extra) -> list[dict]:
    """Fetch a paginated endpoint completely, with **no page ceiling**.

    Why this function must exist: `Limit=100` is the first page, not the whole set. The official response carries 70+ platform images
    (measured; image endpoint docs: https://www.compshare.cn/docs/gpus/image/describecompshareimages),
    and an account's instances can also exceed 100 — answering "does X exist" from one page misjudges by construction (that is how a custom image was missed
    and "image not found" was concluded). So only two terminating conditions are accepted here:
      * this page holds fewer than page records (there is no next page)
      * this page brings no new id (the endpoint ignores Offset and paging does not advance)
    Any `range(10)`-style ceiling stops where it must not; never write one again.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    offset = 0
    while True:
        params = {"Limit": page, "Offset": offset}
        if region:
            params["Region"] = region
        if zone:
            params["Zone"] = zone
        params.update(extra)
        data = client.call(action, **params)
        got = data.get(key) or []
        fresh = [r for r in got if str(r.get(id_field)) not in seen]
        for r in fresh:
            seen.add(str(r.get(id_field)))
        rows.extend(fresh)
        if len(got) < page or not fresh:
            return rows
        offset += len(got)


def _targets(region: str | None, zone: str | None) -> list[tuple[str, str]]:
    """Translate --region/--zone into the (region, zone) list to query, **assuming no region**.

    omitted → every known region; region only → every known zone in it; zone only → look its region up in ZONES.
    The old default hard-coded cn-wlcb / cn-wlcb-01, deciding "north China 2A" on the user's behalf, and the moment stock ran out there
    the conclusion was misreported as "no stock anywhere".
    """
    if region and zone:
        return [(region, zone)]
    if zone:
        for r, z, _d, _k in ZONES:
            if z == zone:
                return [(r, z)]
        return [(region or ZONES[0][0], zone)]
    if region:
        hit = [(r, z) for r, z, _d, _k in ZONES if r == region]
        return hit or [(region, "")]
    return [(r, z) for r, z, _d, _k in ZONES]


def cmd_images(args) -> int:
    """List images. By default **no region is assumed**: without --region, every known region is walked and each is fully paginated."""
    targets = [(r, z, "", "") for r, z in _targets(args.region, args.zone)]
    total = 0
    for region, zone, desc, _kind in targets:
        try:
            rows = _paged("DescribeCompShareImages", "ImageSet", id_field="CompShareImageId",
                          region=region, zone=args.zone or zone)
        except ApiError as exc:
            err(f"error: {region}/{zone} {exc.code} {exc.message}")
            continue
        if args.raw and rows:
            out(json.dumps(rows, ensure_ascii=False, indent=1))
            return 0
        for img in rows:
            name = img.get("Name") or img.get("ImageName") or ""
            if args.grep and args.grep.lower() not in name.lower():
                continue
            out(f"{region}/{zone} {img.get('CompShareImageId') or img.get('ImageId')} "
                f"{img.get('ImageType','')} {name}")
            total += 1
    if total == 0:
        err("error: 0 image matched (try every region and keyword; do not conclude \"none\")")
        return RC_OK
    return 0


def cmd_types(args) -> int:
    data = client.call("DescribeAvailableCompShareInstanceTypes",
                       Region=args.region, Zone=args.zone, GpuType=args.gpu)
    # Shape: AvailableInstanceTypes[].MachineSizes[] = {Gpu, Collection[{Cpu, Memory[GB...]}]}
    seen = set()
    for family in data.get("AvailableInstanceTypes") or []:
        for size in family.get("MachineSizes") or []:
            for combo in size.get("Collection") or []:
                for mem in combo.get("Memory") or []:
                    row = (args.zone, args.gpu, size.get("Gpu"), combo.get("Cpu"), mem)
                    if row in seen:
                        continue
                    seen.add(row)
                    out(" ".join(str(x) for x in row))
    return 0


# ---------- stock and price ----------

def _disk_type(region: str, zone: str) -> str:
    """VM regions use an SSD cloud disk; container regions use a local disk, and passing CLOUD_SSD at creation is rejected — so the two are distinguished here."""
    for r, z, _, kind in ZONES:
        if r == region and z == zone:
            return "CLOUD_SSD" if kind == "VM" else "LOCAL"
    return "CLOUD_SSD"


def _disks(region: str, zone: str, size: int) -> dict:
    """Disks must use UCloud's Disks.0.* indexed form.

    A JSON string makes the service answer 200 with an empty body (not an error), which is expensive to diagnose,
    so the indexed form is fixed here; do not change it back.
    """
    return {"Disks.0.IsBoot": "true", "Disks.0.Type": _disk_type(region, zone),
            "Disks.0.Size": str(size)}


def check_zone(region: str, zone: str, gpu: str, image: str, charge: str,
               disk_size: int, cpu_platform: str = "Auto") -> list[dict]:
    data = client.call(
        "CheckCompShareResourceCapacity",
        Region=region, Zone=zone, GpuType=gpu, MachineType="G",
        MinimalCpuPlatform=cpu_platform, CompShareImageId=image, ChargeType=charge,
        **_disks(region, zone, disk_size),
    )
    rows = []
    for s in data.get("Specs") or []:
        rows.append({
            "region": region, "zone": zone, "gpu": gpu,
            "cards": s.get("Gpu"), "cpu": s.get("Cpu"), "mem_gb": s.get("Mem"),
            "enough": bool(s.get("ResourceEnough")),
        })
    return rows


def cmd_stock(args) -> int:
    if not args.image:
        err("stock needs --image <compShareImageId>; run `compshare images --grep PyTorch` first")
        return 2
    for region, zone in _targets(args.region, args.zone):
        desc = next((d for r, z, d, _k in ZONES if r == region and z == zone), zone)
        try:
            rows = check_zone(region, zone, args.gpu, args.image, args.charge, args.disk_size)
        except ApiError as exc:
            if "machine type not configured" in exc.message:
                # this region does not sell that card. With --all it is stated explicitly, otherwise a missing region gets read as
                # "that region has no stock", and the two conclusions are not the same.
                if getattr(args, "all", False):
                    out(f"{region} {zone} {desc} {args.gpu} n/a not-configured")
                continue
            err(f"error: {zone} {exc.code} {exc.message}")
            continue
        for r in rows:
            if args.cards and r["cards"] != args.cards:
                continue
            if not r["enough"] and not args.all:
                continue
            # with the default Postpay nothing is appended to the line, keeping the existing format (panel/serve.py parses by column);
            # only spot-pool queries append a charge marker, otherwise one yes/no line cannot say which pool it describes.
            tag = "" if (args.charge or "Postpay") == "Postpay" else f" {args.charge.lower()}"
            out(f"{r['region']} {r['zone']} {desc} {args.gpu} {r['cards']} "
                f"{r['cpu']} {r['mem_gb']} {'yes' if r['enough'] else 'no'}{tag}")
    return 0


def cmd_quote(args) -> int:
    data = client.call(
        "GetCompShareInstancePrice",
        Region=args.region, Zone=args.zone, GpuType=args.gpu, Gpu=args.cards,
        Cpu=args.cpu, Memory=args.mem_gb * 1024, ChargeType=args.charge,
        CompShareImageId=args.image,
        **_disks(args.region, args.zone, args.disk_size),
    )
    for label, key in (("pay", "PriceDetails"), ("original", "OriginalPriceDetails")):
        for p in data.get(key) or []:
            out(f"{label} {p.get('Instance')} {p.get('SystemDisks')} {p.get('Disks')}")
    return 0


# ---------- instances ----------

def _list_hosts() -> list[dict]:
    """Every instance on the account, fully paginated.

    No "Running only" filter and no origin filter — list everything, then let a human narrow it.
    No page ceiling either: `Limit=100` is only the first page, and instance 101 would be silently dropped by "stop everything".
    """
    return _paged("DescribeCompShareInstance", "UHostSet", id_field="UHostId")


def cmd_ls(args) -> int:
    hosts = _list_hosts()
    if args.running:
        hosts = [r for r in hosts if (r.get("State") or "") == "Running"]
    if args.ids_only:
        for r in hosts:
            out(str(r.get("UHostId")))
        return 0
    if getattr(args, "json", False):
        _json_out([{"id": r.get("UHostId"), "state": r.get("State"),
                    "mode": _mode_label(r), "region": r.get("Region"), "zone": r.get("Zone"),
                    "gpu": r.get("GpuType"), "cards": _gpu_count(r), "name": r.get("Name")}
                   for r in hosts])
        return 0
    for r in hosts:
        out(f"{r.get('UHostId')} {_state_label(r)} {_mode_label(r)} "
            f"{r.get('Region')}/{r.get('Zone')} {r.get('GpuType','')} "
            f"{r.get('GPU', 0)} {r.get('Name','')}")
    return 0


def _gpu_count(record) -> int:
    try:
        return int(record.get("GPU") or 0)
    except (TypeError, ValueError):
        return 0


def _state_label(record) -> str:
    """Normalise the raw State into one of three readable values (anything else is returned as is).

    Stopped / Running / transitional. Whether a Running instance actually has a card is answered by _mode_label.
    """
    state = (record.get("State") or "").strip() or "Unknown"
    return state


def _mode_label(record) -> str:
    """Billing tier: cardless (no card, 0.15 CNY/h) / gpu (card attached) / - (powered off).

    The old output printed a bare number, so `4090 0` could mean either "card type known but no card attached" or "powered off";
    the reader had to know the column semantics first. The tier is now stated directly.
    """
    state = (_state_label(record) or "").lower()
    if state != "running":
        return "-"
    return "gpu" if _gpu_count(record) > 0 else "cardless"


def cmd_kill(args) -> int:
    """Force stop: no idle check, no work check, no disk deletion. Equivalent to "stop billing now".

    How the three verbs differ:
      stop   one machine, clean shutdown (also keeps disks), but one at a time — you write the loop;
      settle one machine, checks whether work is running and stops only when idle — for wrapping up;
      kill   several machines or --all, unconditional — for stopping the meter right now.
    """
    ids: list[str] = list(args.uhost_id or [])
    if args.all:
        ids = [r["UHostId"] for r in _list_hosts() if (r.get("State") or "") == "Running"]
    if not ids:
        out("none")
        return 0
    failed = 0
    for uhost_id in ids:
        if args.dry_run:
            out(f"plan kill {uhost_id}")
            continue
        try:
            region, zone = _locate(uhost_id)
            if watchdog.status(uhost_id):
                watchdog.stop(uhost_id)
            client.call("StopCompShareInstance", Region=region, Zone=zone, UHostId=uhost_id)
            out(f"kill {uhost_id} ok")
        except ApiError as exc:
            failed += 1
            err(f"error: {uhost_id} {exc}")
    return 4 if failed else 0


def _locate(uhost_id: str) -> tuple[str, str]:
    # UHostIds also takes the indexed form; a JSON string yields 230 Params [UHostIDs] not available.
    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    for r in data.get("UHostSet") or []:
        if r.get("UHostId") == uhost_id:
            return r.get("Region"), r.get("Zone")
    raise ApiError(-1, f"instance {uhost_id} not found", "DescribeCompShareInstance")


# StartCompShareInstance can answer 226604 "no resource for this card type" while, at the same moment,
# CheckCompShareResourceCapacity still says yes for that region and spec — that is a scheduler-side transient rejection,
# not a real shortage. So retry with a short backoff first; when it still fails, re-query the official stock (https://www.compshare.cn/docs/gpus/instance/checkcompshareresourcecapacity)
# and write out whether the "sold out" answer was true,
# rather than reporting a retryable transient error as "no stock", which sends people off to change region or wait for nothing.
# 226604 is a scheduler-side transient rejection; 226619 means "calls too frequent", usually triggered by our own retry pace.
# Both need backoff, but 226619 needs a long one, otherwise retrying keeps widening the rate-limit window.
_RETRY_BACKOFF = {226604: 6.0, 226619: 20.0}
_RETRY_CODES = set(_RETRY_BACKOFF)
_START_TRIES = 3


def _instance_spec(uhost_id: str) -> dict:
    """Read the instance's **carded** spec, for re-querying stock.

    The current values from DescribeCompShareInstance cannot be used directly: in cardless mode it returns
    8c16G with GPU=0, and feeding that to CheckCompShareResourceCapacity only yields unsupported,
    turning "cardless right now" into "that spec does not exist". So the original spec from the local record wins,
    and the live values are used only when the record is missing.
    """
    rec = _instance_record(uhost_id) or {}
    if rec.get("gpu"):
        gpu = str(rec["gpu"]).split()[0]            # "4090 x1" -> "4090"
        img = str(rec.get("image") or "").split()[0]  # "img (cuda...)" -> "img"
        if gpu and rec.get("cpu") and rec.get("mem_gb"):
            return {"gpu": gpu, "cards": 1, "cpu": rec.get("cpu"),
                    "mem_gb": rec.get("mem_gb"), "image": img or None}

    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    for r in data.get("UHostSet") or []:
        if r.get("UHostId") != uhost_id:
            continue
        mem = r.get("Memory")
        mem_gb = None
        if isinstance(mem, (int, float)) and mem > 0:
            # create sends Memory=mem_gb*1024 and the response is very likely MB as well; cover the GB case.
            mem_gb = int(mem) // 1024 if mem >= 1024 else int(mem)
        return {"gpu": r.get("GpuType") or r.get("GPUType"),
                "cards": r.get("GPU"), "cpu": r.get("CPU"),
                "mem_gb": mem_gb, "image": r.get("CompShareImageId")}
    return {}


def _stock_verdict(region: str, zone: str, uhost_id: str) -> str:
    """Re-query official stock and state in one line whether the earlier "sold out" was true (official docs:
    https://www.compshare.cn/docs/gpus/instance/checkcompshareresourcecapacity）。


    stock endpoint docs: https://www.compshare.cn/docs/gpus/instance/checkcompshareresourcecapacity

    The return value is concatenated into stderr, so keep it short: `<zone> <gpu> <cpu>c<mem>G sold_out`.
    """
    spec = _instance_spec(uhost_id)
    gpu, cpu, mem_gb, image = (spec.get("gpu"), spec.get("cpu"),
                               spec.get("mem_gb"), spec.get("image"))
    if not (gpu and cpu and mem_gb and image):
        return "stock_unknown"
    try:
        rows = check_zone(region, zone, gpu, image, "Postpay", 100)
    except ApiError:
        return "stock_unknown"
    hit = [r for r in rows if r["cpu"] == int(cpu) and r["mem_gb"] == int(mem_gb)]
    if not hit:
        return f"{zone} {gpu} {cpu}c{mem_gb}G unsupported"
    if any(r["enough"] for r in hit):
        # stock exists but boot fails: the start-side rejection is unrelated to stock (usually reclaiming or a concurrency lock)
        return f"{zone} {gpu} {cpu}c{mem_gb}G in_stock"
    return f"{zone} {gpu} {cpu}c{mem_gb}G sold_out"


def cmd_rename(args) -> int:
    # Names can only be wk-NN: the worker number is assigned by the algorithm, humans do not name machines (use --aux to tell them apart).
    if not __import__("re").fullmatch(r"wk-\d{2}", args.name):
        err(f"error: name must be wk-NN (got {args.name}); use `card <id> --aux` for notes")
        return 2
    """Rename. Naming is always `wk-NN`: no machine is special, only numbered.

    The name is the only stable identifier when scheduling, so the rule is uniform: `wk-01`..`wk-NN`, never host /
    master / gpu style purpose names — purposes change, numbers do not. Renaming only affects display, not
    the instance id, the disks or billing.
    """
    region, zone = _locate(args.uhost_id)
    client.call("ModifyCompShareInstanceName", Region=region, Zone=zone,
                UHostId=args.uhost_id, Name=args.name)
    out(f"renamed {args.uhost_id} {args.name}")
    return RC_OK


def cmd_states(args) -> int:
    """List every State value with its billing verdict; anything the vendor does not state is written unknown, never guessed."""
    for name, (billed, why, src) in STATES.items():
        label = "billed" if billed is True else ("free" if billed is False else "unknown")
        out(f"{name or '(empty)':13s} {label:8s} {why}\n              src={src}")
    if getattr(args, "urls", False):
        out("")
        for key, url in REFS.items():
            out(f"{key:6s} {url}")
    return RC_OK


def cmd_gauges(args) -> int:
    """Print the definition table. Any outward-facing number must appear here, or it may not be written into a conclusion."""
    for name, src, meaning, misuse in GAUGES:
        out(f"{name:9s} src={src:26s} {meaning:16s} misuse={misuse}")

    # Self-check: every field name that status actually emits must be in the table. Absent means an unregistered definition,
    # which is exactly how one number gets three readings — so this exits non-zero instead of relying on memory.
    from src import ops
    fake_host = {"UsageSeconds": 3600, "State": "Running"}
    fake_rec = {"price_cny_per_hour": 2.0}
    emitted = [tok.split("=", 1)[0] for tok in ops.billing(fake_host, fake_rec, 600).split()]
    known = {g[0] for g in GAUGES}
    stray = [t for t in emitted if t not in known]
    if stray:
        err(f"error: status emits unregistered gauge {stray}")
        return 1
    return RC_OK


def cmd_show(args) -> int:
    """Print the API record for one instance verbatim: **no fields dropped, nothing truncated, no reordering**.

    Why it exists: when a single number was needed, the raw JSON used to be read and paraphrased, and paraphrasing drifts.
    Now this one command is the only way to look at the raw record; nobody paraphrases it.
    """
    host = _host(args.uhost_id) or {}
    print(json.dumps(host, ensure_ascii=False, indent=1, sort_keys=True))
    return RC_OK


def cmd_correct(args) -> int:
    """Record a definition correction; without arguments, list the whole history.

    A corrected wording has to leave a trace: `old` is what I said at the time, `new` is how the tool defines it now,
    `why` is the field it rests on. Without that record, "changing the definition" is just erasing the sentence and restating it.
    """
    path = client.SKILL_DIR / "data" / "corrections.jsonl"
    if not args.new:
        if not path.exists():
            err("error: no correction recorded")
            return RC_OK
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            out(f"{time.strftime('%m-%d %H:%M', time.localtime(rec['at']))} {rec['old']} -> {rec['new']} ({rec['why']})")
        return RC_OK
    if not args.old:
        err("error: <old> <new> required: the old wording and the new definition")
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": time.time(), "old": args.old, "new": args.new, "why": args.why or ""}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out(f"correct {args.old} -> {args.new}")
    return RC_OK


def cmd_start(args) -> int:
    """Start: cardless by default. Why, when to switch, and the three pitfalls are all in the `BILLING` comment above.

    Only two things specific to this action are kept here:
      * after start the IP (and sometimes the port) changes, while exec reads the old IP from `data/instance-<id>.json`,
        so run `ssh-setup` once after every start;
      * `--wait-ready N` waits for this machine only and returns at once when not asked to wait — it never switches machines for you.
    """
    region, zone = _locate(args.uhost_id)

    # Read the ledger before starting. The only purpose of this check: **never let "start a dead machine again" become the default action**.
    # The factual base: once a machine is stuck in Initializing, start returns success every time while the container never comes up;
    # retrying only repeats the same failure and burns two more minutes each round. The tool does not switch machines for you,
    # but it should not replay that loop either — hence the default refusal, and --force to send it anyway.
    blocked = _start_blocked(args.uhost_id)
    if blocked and not getattr(args, "force", False):
        broken, ago = blocked
        out(f"start-blocked {args.uhost_id} broken={broken} last={ago:.1f}h")
        err("action: reboot | reinstall | release | --force")
        err("note: reinstall wipes=system_disk, release drops instance")
        return RC_UNAVAILABLE

    params = {"Region": region, "Zone": zone, "UHostId": args.uhost_id}
    # Cardless by default. A card requires an explicit --gpu.
    # Reason: cardless is 0.15 CNY/h and carded 1.7 CNY/h, an 11× difference; while downloading, installing, transferring
    # or editing code, GPU utilisation is 0 and per-machine billing gives no discount. On 2026-10-30 a 30G weight download was started carded
    # and the GPU idled throughout.
    cardless = None if args.gpu else (args.cardless or "A")
    if cardless:
        params["WithoutGpuSpec"] = cardless

    # Success prints one `started` line; the retry process is not echoed line by line, so "retrying" is never read as a result.
    # Failure also prints one line: the code plus the true stock state, so "temporarily unavailable" and "spec does not exist" are distinguishable at a glance.
    last = None
    for attempt in range(1, _START_TRIES + 1):
        try:
            client.call("StartCompShareInstance", **params)
            out(f"started {args.uhost_id}" + (f" (retry {attempt - 1})" if attempt > 1 else ""))
            _state_reset(args.uhost_id)
            if args.watch:
                pid = watchdog.spawn(args.uhost_id)
                out(f"watchdog {pid if pid else 'running'}")
            # --wait-ready N: one machine, bounded, one verdict. Without it only `started` is printed and the call returns,
            # never deciding here whether to switch machines.
            if getattr(args, "wait_ready", 0):
                return _report_ready(args.uhost_id,
                                     _await_ready(args.uhost_id, args.wait_ready,
                                                  getattr(args, "init_grace", 300.0)),
                                     getattr(args, "init_grace", 300.0))
            return 0
        except ApiError as exc:
            last = exc
            if (exc.code not in _RETRY_CODES
                    and "out of resources" not in (exc.message or "").lower()):
                raise
            if attempt < _START_TRIES:
                time.sleep(_RETRY_BACKOFF.get(exc.code, 6.0))
    err(f"error: start failed: {last.code} {_stock_verdict(region, zone, args.uhost_id)}")
    return 1


# ---------- bootcheck: three chances to boot ----------
#
# Purpose: decide whether a machine "can boot". The probe starts cardless (the card is not involved yet, so a failure is always in the container layer),
# at 0.15 CNY/h, an order of magnitude cheaper than one carded attempt.
#
# Why three attempts: a single failure may be one bad scheduling draw on the host, or may be this machine really being broken.
# Any one success in three makes it healthy; only three failures record a failure — so "healthy" is not killed by one wobble.
#
# Parameters (user-specified, not improvised):
#   * each start is allowed 120 seconds;
#   * 60 seconds between attempts 1 and 2, 180 seconds between 2 and 3 (increasing gaps, giving the platform time to heal).
#
# Hard constraint: stop the machine to Stopped before every attempt. Otherwise the previous Install Fail /
# Initializing is inherited by the next start, and all three attempts measure the same state.
BOOTCHECK_TIMEOUT = 120.0
BOOTCHECK_GAP1 = 60.0
BOOTCHECK_GAP2 = 180.0
BOOTCHECK_TRIES = 3


def _await_state(uhost_id: str, target: str, timeout: float) -> bool:
    """Wait until the instance reaches a state; False on timeout. Used to stop the machine cleanly between attempts."""
    end = time.time() + timeout
    while time.time() < end:
        if (_state(uhost_id) or "") == target:
            return True
        time.sleep(4.0)
    return False


def _stop_soft(region: str, zone: str, uhost_id: str) -> str:
    """Stop, tolerating 8903 (already stopping or stopped). Returns '', 'ok', 'already' or 'err:<code>'."""
    state = _state(uhost_id) or ""
    if state == "Stopped":
        return "already"
    try:
        client.call("StopCompShareInstance", Region=region, Zone=zone, UHostId=uhost_id)
        return "ok"
    except ApiError as exc:
        if exc.code == 8903:      # state does not allow it: usually Stopping, so just wait
            return "already"
        return f"err:{exc.code}"


def _bootcheck_one(uid: str, args) -> tuple[str, bool, str, list[str]]:
    """Check one machine, returning (id, healthy, boot_kind, buffered_lines).

    Output is buffered rather than printed so that concurrent machines never interleave: a machine's
    attempt lines stay contiguous even when six of them run at once.
    """
    lines: list[str] = []
    region, zone = _locate(uid)
    if not region:
        lines.append(f"{uid} unknown no-region")
        return uid, False, "", lines

    ok = False
    boot_kind = ""
    results = []
    for attempt in range(1, BOOTCHECK_TRIES + 1):
        if attempt == 2:
            time.sleep(args.gap1)
        elif attempt == 3:
            time.sleep(args.gap2)

        stopped = _stop_soft(region, zone, uid)
        if stopped.startswith("err:"):
            results.append(f"stop-err {stopped[4:]}")
            lines.append(f"{uid} try{attempt} stop-err {stopped[4:]}")
            continue
        if not _await_state(uid, "Stopped", args.stop_wait):
            results.append("stop-timeout")
            lines.append(f"{uid} try{attempt} stop-timeout {args.stop_wait:.0f}s")
            continue

        try:
            client.call("StartCompShareInstance", Region=region, Zone=zone,
                        UHostId=uid, WithoutGpuSpec=args.cardless)
        except ApiError as exc:
            results.append(f"start-err {exc.code}")
            lines.append(f"{uid} try{attempt} start-err {exc.code}")
            continue

        verdict, _state_now, _why, spent = _await_ready(
            uid, args.allow, args.allow, quiet=True)
        results.append(f"{verdict} {spent:.0f}s")
        lines.append(f"{uid} try{attempt} {verdict} {spent:.0f}s")
        # The question is whether the container comes up, not whether ssh lets you in. `jupyter` means the container is alive and
        # only sshd is missing (8888 still works), which counts as a successful boot and must not be judged a bad card.
        if verdict in ("ready", "jupyter"):
            ok = True
            boot_kind = verdict
            break
        _stop_soft(region, zone, uid)   # Initializing bills, so stop at once on failure

    if ok:
        _verdict_write(uid, "ready", "bootcheck ok")
        lines.append(f"{uid} healthy {len(results)}/{BOOTCHECK_TRIES} {boot_kind}")
    else:
        _verdict_write(uid, "init-stuck", "bootcheck fail: " + "; ".join(results))
        lines.append(f"{uid} unhealthy {len(results)}/{BOOTCHECK_TRIES}")

    if not args.keep:
        _stop_soft(region, zone, uid)
        # Stopping cannot count as done when the command is merely sent: Initializing bills, and without the state settling the meter keeps running.
        if _await_state(uid, "Stopped", args.stop_wait):
            lines.append(f"{uid} stopped")
        else:
            lines.append(f"{uid} stop-pending {args.stop_wait:.0f}s")
    return uid, ok, boot_kind, lines


def cmd_bootcheck(args) -> int:
    """Boot check: three chances (120s each by default, gaps of 60s and 180s); any success makes it healthy.

    Machines are independent jobs, so they run concurrently (--parallel, default 6): per-machine time is
    platform boot latency, and a one-process sweep of a fleet spends it all in sleep().

    Output convention (stdout: one line per attempt + one per machine + one summary):

        <id> try1 init-stuck 14s          # verdict + actual elapsed time
        <id> try2 stop-err 8903           # failed already at the stop stage
        <id> try3 init-stuck 14s
        <id> unhealthy 3/3                # or healthy 2/3
        summary healthy=0 unhealthy=1 total=1

    Progress lines such as `wait ... Starting 0s` are gone: the check cares about the three results, not the process.
    """
    healthy, unhealthy = [], []
    uids = args.uhost_ids
    width = max(1, min(args.parallel, len(uids)))
    with ThreadPoolExecutor(max_workers=width) as pool:
        futures = [pool.submit(_bootcheck_one, uid, args) for uid in uids]
        for fut in futures:
            try:
                uid, ok, _kind, lines = fut.result()
            except Exception as exc:  # noqa: BLE001 - one machine must not take the sweep down
                out(f"{uids[futures.index(fut)]} error {type(exc).__name__}")
                unhealthy.append("error")
                continue
            for line in lines:
                out(line)
            (healthy if ok else unhealthy).append(uid)

        # Closing check: print how many machines are still not stopped, so "everything is off" is a verifiable conclusion rather than my assertion.
        def _left_of(uid: str) -> str | None:
            try:
                if (_state(uid) or "") not in ("Stopped", ""):
                    return uid
            except ApiError:
                return f"{uid}:unknown"
            return None

        left = [r for r in pool.map(_left_of, uids) if r]

    out(f"summary healthy={len(healthy)} unhealthy={len(unhealthy)} "
        f"total={len(uids)} left_running={len(left)}")
    if left:
        out("left " + " ".join(left))
    return 0 if not unhealthy else 1


def cmd_stop(args) -> int:
    region, zone = _locate(args.uhost_id)
    if watchdog.status(args.uhost_id):
        watchdog.stop(args.uhost_id)
    client.call("StopCompShareInstance", Region=region, Zone=zone, UHostId=args.uhost_id)
    out(f"stop {args.uhost_id}")
    return 0


def _state(uhost_id: str) -> str | None:
    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    for r in data.get("UHostSet") or []:
        if r.get("UHostId") == uhost_id:
            return r.get("State")
    return None


def cmd_release(args) -> int:
    """Destroy an instance: TerminateCompShareInstance.

    Irreversible. System-disk data is wiped, and the data disk goes with the instance: a returned machine that keeps a
    disk keeps billing for it, and an orphaned disk cannot be listed or deleted through this API, so "returned" means both
    disks are gone. `--keep-udisk` is the only way to keep the data disk, and it says so in the plan.
    The vendor restricts deletion to Stopped instances (source: https://www.compshare.cn/docs/gpus/instance/terminatecompshareinstance),
    so a running instance only gets one Stop here and returns 4,
    letting the caller see "still stopping, run it again" instead of doing the delete in the same call —
    that delete would land on an unknown state.
    """
    state = _state(args.uhost_id)
    region, zone = _locate(args.uhost_id)
    if state is None:
        err(f"error: instance {args.uhost_id} not found")
        return 1
    if state != "Stopped":
        if watchdog.status(args.uhost_id):
            watchdog.stop(args.uhost_id)
        client.call("StopCompShareInstance", Region=region, Zone=zone, UHostId=args.uhost_id)
        out(f"release-blocked {args.uhost_id} {state}")
        err("action: wait --state Stopped && release")
        return 4
    if not getattr(args, "yes", False):
        out(f"plan release {args.uhost_id} state={state} "
            f"wipes={'system_disk keeps=data_disk (--keep-udisk)' if args.keep_udisk else 'system_disk+data_disk'}")
        err("dry-run: add --yes")
        return RC_OK
    params = {"Region": region, "Zone": zone, "UHostId": args.uhost_id}
    if not args.keep_udisk:
        # the endpoint wants a lowercase string; urlencode turns a Python bool into "True".
        # Deleting the data disk is the default: a disk left behind keeps billing by capacity and this API cannot
        # list or delete it afterwards, so "returned" has to mean nothing is left to pay for.
        params["ReleaseUDisk"] = "true"
    data = client.call("TerminateCompShareInstance", **params)
    uid = data.get("UHostId") or args.uhost_id
    out(f"release {uid} recycle={data.get('InRecycle') or '?'}")
    # The instance is gone: clear the ledger, the state timer and the instance record, otherwise the next round of `verdicts`/`pick`
    # keeps listing a machine that no longer exists.
    for pattern in (f"verdict-{uid}.json", f"state-{uid}.json", f"instance-{uid}.json",
                    f"health-{uid}.json"):
        (client.SKILL_DIR / "data" / pattern).unlink(missing_ok=True)
    return 0


def cmd_image(args) -> int:
    """Custom images: list them, or build one from an instance's system disk.

    This is how to move across regions: `pull`/`push` measures about 1 MB/s, so a 40G system disk would take seven or eight hours;
    built into an image, a new instance in another region is created from the same CompShareImageId and the data travels with it.
    Building and storing bill at 0.008 CNY/GB/day (source: https://www.compshare.cn/docs/gpus/image/describecompshareimages).
    Note the documentation states that an image from this region can only create machines in this region, and cross-region use needs a ticket to enable regional permission
    (source: https://www.compshare.cn/docs/gpus/instance/createcompshareinstance) — so this command only builds the image;
    whether it can be used elsewhere is judged by the actual response of `create` in the target region.
    """
    if args.image_action == "ls":
        # list custom images only by default: there are 70+ platform images, and `images` with a name filter suits those better.
        rows = _paged("DescribeCompShareImages", "ImageSet", id_field="CompShareImageId",
                      region=args.region)
        for it in rows:
            kind = it.get("ImageType") or ""
            if not args.all and kind.lower() != "custom":
                continue
            out(f"{it.get('CompShareImageId')} {kind} {it.get('Name')}")
        return 0

    if not args.uhost_id or not args.name:
        err(f"error: image create needs <uhost_id> --name <name>")
        return 2
    region, zone = _locate(args.uhost_id)
    data = client.call("CreateCompShareCustomImage", Region=region, Zone=zone,
                       UHostId=args.uhost_id, Name=args.name)
    out(f"image {data.get('CompShareImageId')}")
    return 0


def _create_instance(region: str, zone: str, gpu: str, image: str, cards: int,
                     cpu: int, mem_gb: int, name: str, password: str,
                     charge: str = "Postpay", disk_size: int = 100) -> list[str]:
    """Create one instance, returning the id list. cmd_create and pool grab share this request builder."""
    data = client.call(
        "CreateCompShareInstance",
        Region=region, Zone=zone, GpuType=gpu, GPU=cards,
        CPU=cpu, Memory=mem_gb * 1024, MachineType="G",
        CompShareImageId=image, ChargeType=charge, Name=name,
        LoginMode="Password",
        Password=base64.b64encode(password.encode()).decode(),  # the endpoint wants base64
        **_disks(region, zone, disk_size),
    )
    ids = data.get("UHostIds") or []
    for uid in ids:
        # The record must carry the password: `_ssh_once` falls back to password auth when the key is refused, and without it login fails;
        # it also lets `show` / `status` read region/zone without re-querying the API.
        _instance_write(uid, {
            "uhost_id": uid, "name": name, "region": region, "zone": zone,
            "gpu": gpu, "cards": cards, "cpu": cpu, "mem_gb": mem_gb,
            "image": image, "charge": charge, "password": password,
            "ssh_port": 23, "login_user": "root",
        })
    return ids


def cmd_create(args) -> int:
    """Create one instance.

    At the quota ceiling (`MAX_INSTANCES`) it fails locally, returns 3 and prints `quota` without sending a create request —
    the 16th machine is rejected by the platform with `226608`, and waiting until then only takes a longer route to the same error.
    """
    if _quota_blocked(1):
        err(f"error quota={MAX_INSTANCES} reached; release an instance first "
            f"(platform returns 226608 beyond this)")
        return 3
    rows = check_zone(args.region, args.zone, args.gpu, args.image, args.charge, args.disk_size)
    if not any(r["enough"] and r["cards"] == args.cards and r["cpu"] == args.cpu
               and r["mem_gb"] == args.mem_gb for r in rows):
        err(f"error: {args.zone} {args.gpu} {args.cards} {args.cpu} {args.mem_gb} "
            f"not ResourceEnough; run `compshare stock` first")
        return 3
    ids = _create_instance(args.region, args.zone, args.gpu, args.image, args.cards,
                           args.cpu, args.mem_gb, args.name,
                           args.password or DEFAULT_PASSWORD,
                           args.charge, args.disk_size)
    out("created " + (" ".join(ids) if ids else "-"))
    return 0


# ---------- card pool: keep N usable cards ----------
#
# Background: 4090 stock fluctuates by the minute, so starting one when it is needed often fails; broken machines do not fix themselves.
# So grabbing and cleaning are one command, and the goal is "keep N usable", not "keep N powered on".
#
# Three principles (all learned the hard way):
#   * grabbing is bounded: one sweep by default, polling only with `--for seconds`, never an unbounded wait;
#   * releasing is irreversible: candidates are listed by default, `--yes` actually deletes;
#   * naming uses numbers only: `wk-NN` takes the next free number, so no machine ever becomes "that special one".
POOL_DEFAULT_TARGET = 10


def _next_name(hosts: list[dict]) -> str:
    used = set()
    for h in hosts:
        name = h.get("Name") or ""
        if name.startswith("wk-") and name[3:].isdigit():
            used.add(int(name[3:]))
    n = 1
    while n in used:
        n += 1
    return f"wk-{n:02d}"


def _card_path(uhost_id: str):
    return client.SKILL_DIR / "data" / f"card-{uhost_id}.json"


def card_record(uhost_id: str) -> dict:
    try:
        return json.loads(_card_path(uhost_id).read_text())
    except Exception:  # noqa: BLE001
        return {}


def _card_write(uhost_id: str, **fields) -> dict:
    rec = card_record(uhost_id)
    rec.update({k: v for k, v in fields.items() if v is not None})
    rec["at"] = time.time()
    _card_path(uhost_id).write_text(json.dumps(rec, ensure_ascii=False))
    return rec


def cmd_card(args) -> int:
    """Record whether a machine is usable: is kolors configured, has the smoke test passed.

    A usable card is not "currently Running" — Running bills by the hour, and 10 of them are 20 CNY/h.
    A usable card is one that works when wanted: historically stable, kolors in place, and a real smoke run passed.
    The machine will never say any of this, so it has to be recorded; otherwise every round re-probes and re-downloads.
    """
    rec = card_record(args.uhost_id)
    if args.inventory:
        out(json.dumps(rec, ensure_ascii=False, indent=1) if rec else f"{args.uhost_id} no-record")
        return RC_OK
    if args.kolors is None and args.smoke is None and args.aux is None:
        out(json.dumps(rec, ensure_ascii=False, indent=1) if rec else f"{args.uhost_id} no-record")
        return RC_OK
    fields = {"kolors": args.kolors, "aux": args.aux}
    if args.smoke:
        fields["smoke"] = args.smoke
        fields["smoke_at"] = time.time()
    rec = _card_write(args.uhost_id, **fields)
    out(f"card {args.uhost_id} kolors={rec.get('kolors') or '-'} "
        f"smoke={rec.get('smoke') or '-'} aux={rec.get('aux') or '-'}")
    return RC_OK


def _broken(host: dict) -> bool:
    """Ledger verdict: broken >= 3 times and the latest verdict is not ready. A broken machine counts as no resource in any pool."""
    path = _verdict_path(host.get("UHostId") or "")
    try:
        rec = json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        rec = {}
    if rec.get("verdict") == "ready":
        return False
    return int(rec.get("broken_count") or 0) >= START_BLOCK_AFTER


def _held(host: dict) -> bool:
    """Actually holds a card: Running with a GPU.

    Why the GPU count matters: the moment an instance is Stopped the API reports `GPU` as 0 (the card goes back to the platform;
    shutdown does not hold it). So a "Stopped, GpuType=4090" machine is not a resource in hand — it is "can boot, but the card
    must be grabbed again". Counting it as usable is lying to yourself about the pool being sufficient.
    """
    return (host.get("State") or "") == "Running" and int(host.get("GPU") or 0) >= 1


def cmd_pool(args) -> int:
    action = args.pool_action
    hosts = _list_hosts()

    if action == "status":
        rows = []
        for h in hosts:
            uid = h.get("UHostId") or ""
            c = card_record(uid)
            stable = not _broken(h)
            kolors_ok = (c.get("kolors") == "ready")
            smoke_ok = (c.get("smoke") == "ok")
            effective = stable and kolors_ok and smoke_ok
            if not stable:
                tag = "broken"
            elif effective:
                tag = "effective"
            elif c.get("kolors") is None and not c:
                tag = "unknown"
            else:
                tag = "pending"
            rows.append((h, c, tag))
        eff = [r for r in rows if r[2] == "effective"]
        pend = [r for r in rows if r[2] == "pending"]
        unk = [r for r in rows if r[2] == "unknown"]
        broken = [r for r in rows if r[2] == "broken"]
        target = args.target or POOL_DEFAULT_TARGET
        for h, c, tag in sorted(rows, key=lambda r: ("effective pending unknown broken".index(r[2]), r[0].get("Name") or "")):
            out(f"{h.get('Name') or '-':7s} {h.get('UHostId')} {h.get('State'):12s} "
                f"{tag:9s} kolors={c.get('kolors') or '-':7s} smoke={c.get('smoke') or '-':4s} "
                f"broken={int((json.loads(_verdict_path(h.get('UHostId') or '').read_text()) if _verdict_path(h.get('UHostId') or '').exists() else {}).get('broken_count') or 0)}"
                + (f" aux={c['aux']}" if c.get("aux") else ""))
        out(f"total={len(rows)} effective={len(eff)} pending={len(pend)} unknown={len(unk)} "
            f"broken={len(broken)} target={target} gap={max(0, target - len(eff))}")
        return RC_OK

    if action == "grab":
        image = args.image
        if not image:
            err("error: grab needs --image <CompShareImageId>")
            return 2

        target = args.target or POOL_DEFAULT_TARGET
        have = len([h for h in hosts if _held(h)])
        need = max(0, min(int(args.count or target), target - have))
        # Remaining quota decides how many can be created this round; at the ceiling it exits locally without sending a request.
        room = MAX_INSTANCES - len(hosts)
        if need and room <= 0:
            err(f"error quota={MAX_INSTANCES} reached ({len(hosts)} instances); "
                f"platform returns 226608 beyond this")
            return 3
        if need > room:
            out(f"grab capped need={need}->{room} quota={MAX_INSTANCES}")
            need = room
        if need == 0:
            out(f"pool held={have} target={target} need=0")
            return RC_OK
        deadline = time.time() + float(args.for_seconds or 0)
        created: list[str] = []
        scan = 0
        while len(created) < need:
            scan += 1
            for region, zone in _targets(args.region, args.zone):
                try:
                    rows = check_zone(region, zone, args.gpu, image, args.charge, args.disk_size)
                except ApiError as exc:
                    if "machine type not configured" not in exc.message:
                        err(f"error: {zone} {exc.code} {exc.message}")
                    continue
                free = [r for r in rows if r["enough"] and r["cards"] == (args.cards or 1)]
                if not free:
                    continue
                r = sorted(free, key=lambda x: (x["mem_gb"], x["cpu"]))[0]
                # hosts is a snapshot taken before creation and does not refresh as machines are created; the new name must be recorded,
                # otherwise _next_name keeps computing the same free number (measured: four machines grabbed in one go were all wk-09).
                name = _next_name(hosts)
                try:
                    ids = _create_instance(region, zone, args.gpu, image, r["cards"],
                                           r["cpu"], r["mem_gb"], name,
                                           args.password or DEFAULT_PASSWORD,
                                           args.charge, args.disk_size)
                except ApiError as exc:
                    out(f"grab {name} {zone} failed={exc.code}")
                    continue
                out(f"grab {name} {ids[0] if ids else '-'} {zone} "
                    f"{r['cards']}x{r['cpu']}c{r['mem_gb']}g")
                hosts.append({"Name": name})
                created.extend(ids)
                if not args.keep_gpu:
                    # Stopped by default: grabbing exists to hold a slot in the pool, not to idle at 2 CNY/h.
                    # Add --keep-gpu when it is needed right away.
                    for uid in ids:
                        try:
                            client.call("StopCompShareInstance", Region=region,
                                        Zone=zone, UHostId=uid)
                        except ApiError:
                            pass
                    out(f"stop {ids[0] if ids else '-'}")
                if len(created) >= need:
                    break
            if len(created) >= need:
                break
            if time.time() >= deadline:
                out(f"grab scan={scan} created={len(created)}/{need} no-stock")
                break
            time.sleep(float(args.interval or 10))
        out(f"grab total={len(created)} need={need} scan={scan}")
        return RC_OK if created else 3

    if action == "fill":
        target = args.target or POOL_DEFAULT_TARGET
        rows = []
        for h in hosts:
            uid = h.get("UHostId") or ""
            c = card_record(uid)
            stable = not _broken(h)
            effective = stable and c.get("kolors") == "ready" and c.get("smoke") == "ok"
            rows.append((h, c, stable, effective))
        eff = [r for r in rows if r[3]]
        upgradable = [r for r in rows if r[2] and not r[3]]
        # Upgrade existing machines before renting new ones: renting one costs one more full price, while an idle machine merely lacks kolors.
        rent = max(0, target - len(eff) - len(upgradable))
        if rent:
            out(f"plan rent={rent} gpu={args.gpu} image={args.image or '<image>'}")
        for h, c, stable, effective in rows:
            uid = h.get("UHostId") or ""
            if not stable:
                out(f"plan release {uid} {h.get('State')} broken")
                continue
            if effective:
                continue
            if not c:
                # no record does not mean no kolors: probe first, then judge — never read "not recorded" as "not there".
                out(f"plan probe {uid} kolors=unknown")
                continue
            if c.get("kolors") != "ready":
                out(f"plan configure {uid} kolors={c.get('kolors')}")
            if c.get("smoke") != "ok":
                out(f"plan verify {uid} smoke=0.1")
        out(f"fill effective={len(eff)} upgradable={len(upgradable)} rent={rent} "
            f"target={target} gap={max(0, target - len(eff))}")
        return RC_OK

    if action == "release-broken":
        cands = [h for h in hosts if (h.get("State") or "") != "Running" and _broken(h)]
        if not cands:
            out("release-broken none")
            return RC_OK
        for h in cands:
            out(f"plan release {h.get('Name') or '-'} {h.get('UHostId')} {h.get('State')}")
        if not args.yes:
            out(f"release-broken candidates={len(cands)} dry-run=yes add --yes")
            return RC_OK
        for h in cands:
            uid = h.get("UHostId")
            region, zone = _locate(uid)
            data = client.call("TerminateCompShareInstance", Region=region, Zone=zone, UHostId=uid)
            for pattern in (f"verdict-{uid}.json", f"state-{uid}.json",
                            f"instance-{uid}.json", f"health-{uid}.json"):
                (client.SKILL_DIR / "data" / pattern).unlink(missing_ok=True)
            out(f"release {uid} recycle={data.get('InRecycle') or '?'}")
        return RC_OK

    err("error: pool action must be status|grab|release-broken")
    return 2


def _open(url: str) -> None:
    try:
        subprocess.run(["open", url], check=False, timeout=10)
        err(f"opened {url}")
    except (OSError, subprocess.SubprocessError) as exc:
        err(f"could not open browser ({exc})")


def cmd_watch(args) -> int:
    if not args.image:
        err("watch needs --image <compShareImageId>")
        return 2
    seen: set[str] = set()
    deadline = time.monotonic() + args.minutes * 60
    out(f"watching {args.gpu} {args.cards} {args.charge} {args.minutes}m {args.interval}s "
        f"console={CONSOLE_URL}")
    while time.monotonic() < deadline:
        for region, zone, desc, kind in ZONES:
            try:
                rows = check_zone(region, zone, args.gpu, args.image, args.charge, args.disk_size)
            except ApiError as exc:
                err(f"{zone}: {exc}")
                continue
            for r in rows:
                if not r["enough"] or r["cards"] != (args.cards or 1):
                    continue
                key = f"{zone}-{r['cards']}-{r['cpu']}-{r['mem_gb']}"
                if key in seen:
                    continue
                seen.add(key)
                out(f"appear {desc} {zone} {args.gpu} {r['cards']} {r['cpu']} {r['mem_gb']}")
                if args.open:
                    _open(url)
        left = int(deadline - time.monotonic())
        if left <= 0:
            break
        err(f"{time.strftime('%H:%M:%S')} {len(seen)} seen {left // 60}m")
        time.sleep(args.interval)
    return 0


def _default_gpu() -> str | None:
    """The default card type comes from the record of the most recently touched instance, never a hard-coded model.

    Changing cards is routine: a hard-coded model makes `stock` / `quote` silently query the wrong one after a change while still looking like "it has data".
    With no instance record it returns None, and the caller must explicitly ask for --gpu.
    """
    files = sorted((client.SKILL_DIR / "data").glob("instance-*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        try:
            gpu = (json.loads(f.read_text()).get("gpu") or "").strip()
        except (OSError, ValueError):
            continue
        if gpu:
            return gpu.split()[0]          # the record holds shapes such as "<card> x1"
    return None


def _instance_count() -> int:
    """Total instances on the account (fully paginated, never truncated)."""
    return len(_paged("DescribeCompShareInstance", "UHostSet", id_field="UHostId"))


def _quota_blocked(need: int = 1) -> bool:
    """Whether the quota is exhausted: on True the caller must back off without sending a create request.

    Ground: `226608` was measured at the 16th machine (see the MAX_INSTANCES comment). The official error table does not list it,
    （https://www.compshare.cn/docs/gpus/compshareerrorcode），
    so it can only be caught locally: better a local `quota` line than a string of incomprehensible platform errors.
    """
    return _instance_count() + need > MAX_INSTANCES


def _ensure_record(uhost_id: str, host: dict | None = None,
                   password: str | None = None) -> dict:
    """Backfill data/instance-<id>.json.

    Why it exists: instances created by `pool grab` before this had no record file, so `ssh-setup` failed with
    `no ssh record` and every later exec / upload failed in a chain. The record must be generated from API facts,
    never depend on whether a file happened to be written at creation time. Password: explicit > existing record > DEFAULT_PASSWORD.
    """
    rec = _instance_record(uhost_id)
    host = host if host is not None else (_host(uhost_id) or {})
    ip = next((x.get("IP") for x in host.get("IPSet") or []
               if x.get("Type") in ("BGP", "International")), None)
    fresh = {
        "uhost_id": uhost_id,
        "name": host.get("Name"),
        "region": host.get("Region"),
        "zone": host.get("Zone"),
        "gpu": host.get("GpuType"),
        "cards": host.get("GPU"),
        "cpu": host.get("CPU"),
        "mem_gb": int(host.get("Memory") or 0) // 1024 or None,
        "public_ip": ip,
        "ssh_port": int(rec.get("ssh_port") or 23),
        "login_user": rec.get("login_user") or "root",
        "password": password or rec.get("password") or DEFAULT_PASSWORD,
    }
    _instance_write(uhost_id, fresh)
    return _instance_record(uhost_id)


def _instance_write(uhost_id: str, fields: dict) -> None:
    """Write data/instance-<id>.json (password and spec, at creation time)."""
    path = client.SKILL_DIR / "data" / f"instance-{uhost_id}.json"
    rec = json.loads(path.read_text()) if path.exists() else {}
    rec.update({k: v for k, v in fields.items() if v is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False))


def _instance_record(uhost_id: str) -> dict:
    path = client.SKILL_DIR / "data" / f"instance-{uhost_id}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _ssh_once(uhost_id: str, command: str, record: dict | None = None, timeout: int = 25):
    """Run one command on the instance, returning a CompletedProcess.

    The key installed by ssh-setup is preferred (no password, no sshpass); only a refused key falls back to
    the password, so a remote key rotation or a first run before setup still works.
    """
    import shutil as _shutil

    # A non-zero exit from the remote command is normal and is not an auth failure; only Permission denied triggers the fallback.
    if record is None and sshsetup.KEY_PATH.exists():
        try:
            proc = subprocess.run(sshsetup.ssh_argv(uhost_id, command),
                                  capture_output=True, text=True, errors="replace", timeout=timeout)
            if "Permission denied" not in (proc.stderr or ""):
                return proc
        except subprocess.SubprocessError:
            pass

    rec = record if record is not None else _instance_record(uhost_id)
    if not rec:
        raise ApiError(-1, f"no instance record for {uhost_id}", "ssh")
    sshpass = _shutil.which("sshpass")
    if not sshpass:
        raise ApiError(-1, "sshpass not found (brew install sshpass)", "ssh")
    argv = [sshpass, "-p", rec["password"], "ssh", "-n", "-p", str(rec.get("ssh_port") or 23),
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR",
            # try one password only: sshpass retries several times by default, which is self-inflicted host-side rate limiting.
            "-o", "NumberOfPasswordPrompts=1", "-o", "PubkeyAuthentication=no",
            f"{rec.get('login_user') or 'root'}@{rec['public_ip']}", command]
    # Measured: the first hop after an idle period is often refused (Permission denied), and the same password works immediately after.
    # Retry the "first" attempt exactly once, so a genuinely wrong password is not hidden behind a slow path.
    proc = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout)
    if proc.returncode != 0 and "Permission denied" in (proc.stderr or ""):
        time.sleep(1)
        proc = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout)
    return proc


# These are "cannot connect", not "the command is wrong". Right after start, sshd is not listening yet,
# and a user who just saw Started should not immediately get a Connection timed out.
_SSH_CONNECT_FAILURES = (
    "connection timed out", "connection refused", "operation timed out",
    "no route to host", "network is unreachable", "connection closed by",
    "kex_exchange_identification", "banner exchange", "connection reset",
)
_SSH_RETRY_INTERVAL = 4.0
_SSH_HINT_EVERY = 30.0


def _ssh_connect_failed(stderr: str) -> bool:
    s = (stderr or "").lower()
    return any(k in s for k in _SSH_CONNECT_FAILURES)


def _aborted(proc, code: int):
    """Silence ssh's own error when giving up: the verdict has been printed, and adding the raw Connection timed out
    makes it look like there is another fault."""
    proc.stderr = ""
    proc.stdout = ""
    proc.returncode = code
    return proc


def _ssh(uhost_id: str, command: str, record: dict | None = None,
         timeout: int = 25, wait: float = 0.0, init_grace: float = 300.0):
    """Wait a while when the connection fails, until sshd comes up or wait seconds elapse.

    Only connection-layer failures are retried: auth failure and a non-zero remote exit return immediately,
    otherwise "wrong password" gets slowed down into "slow".

    While waiting, the instance state is checked, and two cases **stop at once** instead of burning the full budget:
    * the state is already terminal, such as Install Fail / Stopped — waiting cannot change it;
    * it sits in Initializing beyond init_grace (default 90s; the official wording is "after 5 minutes contact the platform",
      source: https://www.compshare.cn/docs/operation/gpufaq
      ) — this is not slowness, it is a broken container.

    Four things not to do:
      1. do not start/stop repeatedly to "see what happens" — official FAQ 1.1 (https://www.compshare.cn/docs/operation/gpufaq)
         names "the container environment being destroyed in use" as exactly the shape such operations
         can trigger; cycling only repeats one failure and bills one more initialisation each time;
      2. do not raise --wait on a refused port — defaults are 120s, --init-grace 300s; past that it should be judged dead;
      3. do not queue work on a broken machine — get a `health` verdict first, then decide whether to repair that one;
      4. do not read Initializing as "almost there" — Starting is not billed, Initializing is (0.15 CNY/h cardless).
    """
    if wait <= 0:
        return _ssh_once(uhost_id, command, record, timeout)

    t0 = time.monotonic()
    deadline = t0 + wait
    grace_deadline = t0 + init_grace
    next_hint = t0
    attempt = 0
    proc = None
    while True:
        attempt += 1
        proc = _ssh_once(uhost_id, command, record, timeout)
        if not _ssh_connect_failed(proc.stderr):
            waited = time.monotonic() - t0
            if attempt > 1:
                err(f"ssh-up {uhost_id} {waited:.0f}s")
            return proc
        now = time.monotonic()

        # probe the state every 3 attempts: whether a failed connection means "not up yet" or "came up broken" can only be answered by the state API.
        if attempt == 1 or attempt % 3 == 0:
            try:
                _h = _host(uhost_id)
                code, why = _verdict(_h, init_grace=init_grace,
                                     age=_track_state(uhost_id, _h.get("State") or ""))
            except ApiError:
                code, why = "unknown", "state unavailable"
            if code == "init-stuck":
                # One line only: why it stopped, and what the official wording (https://www.compshare.cn/docs/operation/gpufaq) says the next step is.
                err(f"abort {uhost_id} {why}")
                err("action: reboot | reinstall | contact-platform")
                return _aborted(proc, RC_UNAVAILABLE)
            if code == "not-running":
                err(f"abort {uhost_id} {why}")
                err("action: start")
                return _aborted(proc, RC_STOPPED)

        if now >= deadline:
            err(f"abort {uhost_id} ssh-unreachable {wait:.0f}s")
            err("action: health")
            return _aborted(proc, RC_UNAVAILABLE)
        if now >= grace_deadline:
            err(f"abort {uhost_id} stuck {now - t0:.0f}s")
            err("action: reboot | reinstall | contact-platform")
            return _aborted(proc, RC_UNAVAILABLE)
        if now >= next_hint:
            err(f"wait {uhost_id} ssh {int(now - t0)}s/{int(wait)}s")
            next_hint = now + _SSH_HINT_EVERY
        time.sleep(min(_SSH_RETRY_INTERVAL, max(0.0, deadline - now)))


def _host(uhost_id: str) -> dict:
    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    for u in data.get("UHostSet") or []:
        if u.get("UHostId") == uhost_id:
            return u
    # An unknown instance is a wrong id, not a network fault: give it its own exit code so it is never read as 10.
    raise ApiError(2404, f"{uhost_id} not found", "DescribeCompShareInstance")


# ---------------------------------------------------------------- availability verdict
#
# Official FAQ 1.1 (https://www.compshare.cn/docs/operation/gpufaq): an instance stuck initialising or starting
# means "the container failed to start, or its environment was destroyed in use", and the only remedy is to contact the platform. So
# "keep waiting" never heals these states; it has to exit early, and that is not a retry.

# These states never become Running by themselves; waiting only bills.
_DEAD_STATES = {
    "Install Fail", "Create Fail", "Delete Fail", "Reboot Fail",
    "Stopping", "Stopped", "Terminated", "Released", "Expired",
}
# These states mean "still installing / still coming up"; once past the grace window they must be judged dead.
_INIT_STATES = {"Initializing", "Installing", "Starting", "Rebooting"}


def _public_ip(host: dict) -> str:
    for x in host.get("IPSet") or []:
        if x.get("Type") in ("BGP", "International"):
            return x.get("IP") or ""
    return ""


def _probe_tcp(ip: str, port: int, timeout: float = 3.0) -> str:
    """Probe one port and answer only four things, without retrying.

    **Port facts** (measured, not guessed): this App image is `root` + **23**; `ubuntu` + 22 belongs to system images (VMs).
    On a container instance's public IP, **22 is the host node's shared sshd** and stays open even when your container never started, so
    `22 open / 23 refused` only means "the node is alive, your container is not" — not a network or firewall problem;
    a Permission denied when connecting a local key to 22 is also normal (it is someone else's sshd).

    open      something is listening (sshd is up inside the container)
    refused   RST: the peer is alive but nothing listens. On a container instance this means "the container's sshd is not up"
              or "the container is not running at all" — the host's 22 usually still answers; do not read that as the machine being fine.
    timeout   no response: network, firewall, or the instance is not up — one of the three
    noroute   resolution or routing failed
    """
    if not ip:
        return "noroute"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        return "open"
    except ConnectionRefusedError:
        return "refused"
    except (socket.timeout, TimeoutError):
        return "timeout"
    except OSError:
        return "noroute"
    finally:
        sock.close()


# Boot budget: measured 2026-11-06 across eight machines, successful "ready" took 45/46/50/51/51/52/57/58 seconds;
# `Install Fail` comes back within a second; once `Initializing` passes ~90s no retry in this round ever recovered
# (wk-09/wk-10 were tried to 164s and stayed stuck). So the budget is 90s: covers every success sample with +50% margin,
# and is 3× faster than "wait five minutes" — a refill strategy needs fast abandonment and the next machine, not time spent waiting.
INIT_GRACE = 90.0

# Shared development password: new instances always use it, so the command line need not pass --password.
# To change it, edit this one line; never type it on the command line (it lands in history and logs).
DEFAULT_PASSWORD = "Compshare2026"

# Account instance quota ceiling (**a measured value, not the one in the official table**).
# The official create documentation says "Level 2 = 20 machines" (https://www.compshare.cn/docs/gpus/instance/createcompshareinstance),
# but with 15 machines already on this account, the 16th in three separate regions
# each returned `226608` (the official error table stops at 226606:
# https://www.compshare.cn/docs/gpus/compshareerrorcode). So the real ceiling is treated as 15:
# at the limit, exit locally instead of hitting the API and wasting a create/rollback round. Change this line when the quota changes.
MAX_INSTANCES = 15



def _state_reset(uhost_id: str) -> None:
    """Clear the state timer.

    Must be called after every **successful start**: the state file records when "this state" began,
    and a Starting from last round on the same machine is a different Starting from this round. Measured consequence of skipping it:
    `--wait-ready 150` reported `Starting stuck` 13 seconds after boot (the timer came from a record 33 minutes old).
    """
    try:
        (client.SKILL_DIR / "data" / f"state-{uhost_id}.json").unlink(missing_ok=True)
    except OSError:
        pass


def _track_state(uhost_id: str, state: str) -> float:
    """Record locally when "this state" began, returning the seconds elapsed.

    The API's `StartTime` is not used (it does not refresh during Initializing), and neither is caller-side timing (repeated calls would reset
    "already stuck for 20 minutes" into "just started waiting"). The timer resets as soon as the state changes.
    """
    path = client.SKILL_DIR / "data" / f"state-{uhost_id}.json"
    now = time.time()
    prev: dict = {}
    try:
        prev = json.loads(path.read_text())
    except Exception:  # noqa: BLE001 - a missing or corrupt file counts as absent
        prev = {}
    if prev.get("since") and now - float(prev["since"]) > 6 * 3600:
        prev = {}                      # records older than 6 hours are no longer trusted (the machine may have been cycled since)
    if prev.get("state") != state:
        prev = {"state": state, "since": now}
        try:
            path.write_text(json.dumps(prev))
        except OSError:
            pass
        return 0.0
    return max(0.0, now - float(prev.get("since") or now))


JUPYTER_PORT = 8888


def _channels(host: dict, *, timeout: float = 3.0) -> dict:
    """Probe the channels that answer "can it work", instead of guessing from state strings.

    Measured baseline (a healthy cardless instance): 22 open, 23 open (container sshd), 8888 open (Jupyter, HTTP 302).
    The two broken ones: 22 open, 23 refused, 8888 refused — 22 is the host's shared sshd and does not count.

    So the criterion is two independent channels:
      ssh      the login port (sshd inside the container)
      jupyter  8888 (Jupyter inside the container)
    Both refused ⇒ the container is not running; only jupyter alive ⇒ the container is up without sshd — work possible, web only.
    """
    rec = _instance_record(host.get("UHostId") or "") or {}
    ip = _public_ip(host)
    ssh_port = int(rec.get("ssh_port") or 23)
    return {
        "ssh": _probe_tcp(ip, ssh_port, timeout),
        "jupyter": _probe_tcp(ip, JUPYTER_PORT, timeout),
    }


def _public_ip(host: dict) -> str:
    """Return the public address, or an empty string. Private entries have Type=Private and take no part in the verdict."""
    for ip in host.get("IPSet") or []:
        if (ip.get("Type") or "").lower() == "private":
            continue
        if ip.get("IP"):
            return ip["IP"]
    return ""


def _verdict(host: dict, *, probe: bool = True, init_grace: float = INIT_GRACE,
             age: float | None = None) -> tuple[str, str]:
    """Return (code, one-line reason). The criterion is "can it work", not the state string.

    Official FAQ 1.1 verbatim (https://www.compshare.cn/docs/operation/gpufaq):
      "Instance stuck initialising or starting: a failed container start, or the container environment being destroyed in use, causes an instance to stick
         in initialising or starting; to resolve, join the group and contact the owner."
    FAQ 2.2 adds (same page https://www.compshare.cn/docs/operation/gpufaq): stuck initialising past 5 minutes, and the charges it causes,
    are resolved by joining the group and contacting the owner.

    Hence only four verdict rows:

    | State / observation | Meaning | Action |
    |---|---|---|
    | `Running` + port open | usable | `exec` |
    | `Initializing` briefly | container starting | `ready` short wait (default 180s) |
    | `Initializing` past grace / port refused | container failed to start, platform side | judged dead: reinstall or contact the platform, **do not cycle it** |
    | `Install Fail` | failed in the install stage | as above; schedule nothing until fixed |

    The state string has only six official values (Running/Stopped/Starting/Stopping/Install/Rebooting;
    source: https://www.compshare.cn/docs/gpus/instance/describecompshareinstance; the complete enum is at https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance),
    and `Initializing` and `Install Fail` are not among them, so the verdict rests on the two channels instead.

    ready        ssh works, exec is possible
    jupyter      container alive (8888 open) but no sshd: work possible, web only
    init-wait    still coming up (ports silent), a short wait may succeed
    init-stuck   both channels refused / terminal state / past grace: the container is not running
    not-running  powered off

    Outside Running, the state string only decides "is waiting still worthwhile"; while Running the channels decide,
    because both "State=Running with every channel refused" and "State=Initializing with 8888 open" really occur.
    """
    state = host.get("State") or ""
    uid = host.get("UHostId") or ""
    if state in ("Running", "Initializing", "Starting"):
        if not _public_ip(host):
            # container-region instances may get no public IP (measured wk-12: Running with a private address only);
            # then ssh and jupyter are both noroute and no timeout will ever connect, so judge it dead at once.
            return "no-eip", "no public ip"
    if state == "Running":
        if not probe:
            return "ready", "state Running (not probed)"
        ch = _channels(host)
        if ch["ssh"] == "open":
            return "ready", "ssh-open"
        if ch["jupyter"] == "open":
            return "jupyter", "jupyter-open ssh-down"
        if ch["ssh"] == "refused" and ch["jupyter"] == "refused":
            return "init-stuck", "ports-refused"
        return "init-wait", f"ssh-{ch['ssh']} jupyter-{ch['jupyter']}"
    if state in _INIT_STATES:
        waited = age or 0.0
        if probe:
            ch = _channels(host)
            if ch["jupyter"] == "open" or ch["ssh"] == "open":
                # the state has not settled, but the channels are already alive — the "stuck yet usable" case,
                # which must not be called unusable because of a state string.
                return "jupyter", f"ssh-{ch['ssh']} jupyter-{ch['jupyter']}"
        if waited > init_grace:
            return "init-stuck", f"{waited:.0f}s>{init_grace:.0f}s"
        return "init-wait", f"{waited:.0f}s"
    if state == "Stopped":
        return "not-running", "stopped"
    return "init-stuck", "state-unknown"


def cmd_health(args) -> int:
    """Probe both channels in 3 seconds and answer "can this machine work right now", with no retry and no waiting."""
    host = _host(args.uhost_id)
    state = host.get("State") or ""
    code, why = _verdict(host, probe=not args.no_probe, age=_track_state(args.uhost_id, state))
    ip = _public_ip(host) or "-"
    _verdict_write(args.uhost_id, code, why)
    if getattr(args, "json", False):
        _json_out({"id": args.uhost_id, "state": state, "ip": ip,
                   "verdict": code, "why": why})
    else:
        out(f"{args.uhost_id} {state} {ip} {code} {why}")
    if code == "ready":
        return RC_OK
    if code == "jupyter":
        return RC_JUPYTER
    if code == "not-running":
        return 31
    return 30


def _await_ready(uhost_id: str, timeout: float, init_grace: float, quiet: bool = False):
    """Wait for one machine to become ready, bounded, returning (verdict, state, reason, elapsed).

    Only five verdicts, all produced here: ready / jupyter / init-stuck / not-running / timeout.
    The budget is guarded on two lines: once the remaining time is under "measured latency of one fetch + 1s" no new request is sent and the cached state decides;
    progress prints only on a state change or every 30 seconds. One Describe measures 20–40s on this account,
    so the pattern "check once at the deadline" alone turns a 70s budget into 100s or more.
    """
    t0 = time.monotonic()
    deadline = t0 + timeout
    grace_deadline = t0 + (init_grace or 0)
    last_state, last_hint = "", 0.0
    host: dict | None = None
    latency = 0.0
    while True:
        remaining = deadline - time.monotonic()
        if host is not None and remaining < max(latency + 1.0, 5.0):
            state = host.get("State") or ""
            age = _track_state(uhost_id, state)
            return "timeout", state, "budget", time.monotonic() - t0
        t_call = time.monotonic()
        host = _host(uhost_id)
        latency = time.monotonic() - t_call
        state = host.get("State") or ""
        age = _track_state(uhost_id, state)
        if init_grace:
            grace_deadline = min(grace_deadline, t0 + max(0.0, init_grace - age))
        code, why = _verdict(host, init_grace=init_grace, age=age)
        spent = time.monotonic() - t0
        if code in ("ready", "jupyter", "not-running", "init-stuck", "no-eip"):
            return code, state, why, spent
        now = time.monotonic()
        if not quiet and (state != last_state or now - last_hint >= 30.0):
            err(f"wait {uhost_id} {state} {age:.0f}s")
            last_state, last_hint = state, now
        if now >= deadline:
            return "timeout", state, why, spent
        if now >= grace_deadline:
            return "init-stuck", state, f"{age:.0f}s so far (grace {init_grace:.0f}s)", spent
        time.sleep(min(5.0, max(0.0, deadline - now)))


def _report_ready(uhost_id: str, result, init_grace: float = INIT_GRACE) -> int:
    """One record line to stdout, and an action line to stderr when needed.

    Record format (space-separated, no sentences):
      ready     <id> <secs>s
      not-ready <id> <state> <reason> [<secs>s]
    action only says what to type next, with no explanation.
    """
    verdict, state, why, spent = result
    if verdict == "ready":
        out(f"ready {uhost_id} {spent:.0f}s")
        _verdict_write(uhost_id, "ready", why)
        return RC_OK
    if verdict == "jupyter":
        out(f"ready {uhost_id} {spent:.0f}s jupyter-only")
        err("action: jupyter|reboot")
        _verdict_write(uhost_id, "jupyter", why)
        return RC_JUPYTER
    if verdict == "not-running":
        out(f"not-ready {uhost_id} {state}")
        err("action: start")
        _verdict_write(uhost_id, "not-running", why)
        return RC_STOPPED
    if verdict == "timeout":
        out(f"not-ready {uhost_id} {state} timeout {spent:.0f}s")
        _verdict_write(uhost_id, "timeout", why)
        return RC_UNAVAILABLE
    if verdict == "no-eip":
        out(f"not-ready {uhost_id} {state} no-eip {spent:.0f}s")
        err("action: release | reinstall")
        _verdict_write(uhost_id, "no-eip", why)
        return RC_UNAVAILABLE
    out(f"not-ready {uhost_id} {state} stuck {spent:.0f}s")
    err("action: reboot | reinstall | contact-platform")
    _verdict_write(uhost_id, "init-stuck", why)
    return RC_UNAVAILABLE


def cmd_ready(args) -> int:
    """Wait for one machine to become usable; exit immediately on a death verdict. One line of output."""
    return _report_ready(args.uhost_id,
                         _await_ready(args.uhost_id, args.timeout, args.init_grace),
                         args.init_grace)


def _verdict_path(uhost_id: str):
    return client.SKILL_DIR / "data" / f"verdict-{uhost_id}.json"



# ---------- gauge table: one number, one reading ----------
#
# Why it exists: one "how long has it been up" had three different sources, and on the same day it was read three different ways
# (5.15h this run / 37.8h cumulative / 0.3h since the last verdict), each time excused as "changing the definition".
# As long as the definition lives in my mouth it keeps changing. So it becomes data: every number that appears outward
# must be registered here with the API field it comes from, its unit, and "what a misread would wrongly conclude".
# `compshare gauges` prints this table; the field names emitted by `status` must match it.
GAUGES = [
    ("up", "/proc/uptime", "uptime of this boot (h)", "read as total use -> understates cost"),
    ("usage", "UsageSeconds", "cumulative use (h)", "read as continuous uptime -> overstates risk"),
    ("age_h", "at in verdict-<id>.json", "hours since the last verdict", "read as uptime -> meaningless"),
    ("cost_now", "price x /proc/uptime", "cost of this boot (cny)", "read as total cost -> understates"),
    ("cost_all", "price x UsageSeconds", "cumulative cost (cny)", "read as this boot -> overstates"),
    ("disk", "df -h /root", "system disk used/total", "read as free space -> wrong planning"),
]

# ---------- references: every conclusion must trace to a source ----------
#
# The easiest thing to hand-wave in a document is "officially it says". So sources become constants (REFS below, e.g.
# the billing FAQ: https://www.compshare.cn/docs/operation/gpufaq):
# the code cites **codes**, and SKILL.md maps code -> URL. Changing a conclusion means changing both places.
REFS = {
    "FAQ":   "https://www.compshare.cn/docs/operation/gpufaq",
    "BILL":  "https://www.compshare.cn/docs/operation/charge/billdescribe",
    "API":   "https://www.compshare.cn/docs/gpus/instance/describecompshareinstance",
    "UAPI":  "https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance",
    "DISK":  "https://www.compshare.cn/docs/operation/gpu/disk",
    "SPOT":  "https://www.compshare.cn/docs/operation/gpuspot/gpuspot",
    "AGREE": "https://www.compshare.cn/docs/overview/serviceagreement/frame",
}

# ---------- state table: State values, whether they bill, and the source ----------
#
# Why a table is needed: the two official documents disagree — compshare's own API documentation (https://www.compshare.cn/docs/gpus/instance/describecompshareinstance)
# lists `State` as
#   Running / Stopped / Starting / Stopping / Install / Rebooting，
# **no Initializing at all**; while the underlying UCloud documentation has Initializing / Install Fail / Resizing / empty.
# Measured: the API returns both kinds (today's records hold 50+ raw Initializing and several Starting values).
# So "which state costs money" cannot come from me paraphrasing docs; it comes from this table plus an explicit source.
# Billing column: True=billed, False=not billed, None=the vendor does not say (sources https://www.compshare.cn/docs/operation/gpufaq and https://www.compshare.cn/docs/operation/charge/billdescribe;
# anything unstated must not be treated as False, and must not be guessed).
# The third column is a REFS code pointing at the exact document.
STATES = {
    "Running":      (True,  "only a running instance is in normal use, billed hourly",
                     "https://www.compshare.cn/docs/operation/gpufaq https://www.compshare.cn/docs/operation/charge/billdescribe"),
    "Initializing": (True,  "billing caused by a long card-init can be raised with the group owner (billing admitted)",
                     "https://www.compshare.cn/docs/operation/gpufaq"),
    "Starting":     (False, "starting does not bill (the host is not powered on yet)",
                     "https://www.compshare.cn/docs/operation/gpufaq"),
    "Stopping":     (None,  "not stated in the documentation", "https://www.compshare.cn/docs/gpus/instance/describecompshareinstance"),
    "Stopped":      (False, "pay-as-you-go shutdown reclaims CPU/GPU/memory and stops charging; disks keep charging",
                     "https://www.compshare.cn/docs/operation/gpufaq https://www.compshare.cn/docs/operation/charge/billdescribe"),
    "Rebooting":    (None,  "not stated in the documentation", "https://www.compshare.cn/docs/gpus/instance/describecompshareinstance"),
    "Install":      (None,  "not stated in the documentation", "https://www.compshare.cn/docs/gpus/instance/describecompshareinstance"),
    "Install Fail": (None,  "not stated in the documentation", "https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance"),
    "Resizing":     (None,  "not stated in the documentation", "https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance"),
    "":             (None,  "empty string = the state read timed out or failed", "https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance"),
}

BROKEN_VERDICTS = ("init-stuck", "timeout")
START_BLOCK_AFTER = 3        # after the third failure it is no longer retried by default
START_BLOCK_WINDOW_H = 24.0  # and the latest failure is within 24 hours


def _verdict_write(uhost_id: str, verdict: str, why: str) -> None:
    """Record this verdict and accumulate "how often it broke".

    Keeping only the last verdict loses a key fact: after a machine hangs three times and is then stopped, the last verdict becomes
    `not-running`, so "it broke" disappears and the next round tries it again as if it were new.
    Hence `broken_count` / `last_broken_at`, once written, are never cleared by a non-failure verdict.
    """
    now = time.time()
    prev = {}
    try:
        prev = json.loads(_verdict_path(uhost_id).read_text())
    except Exception:  # noqa: BLE001 - missing or corrupt counts as absent
        prev = {}
    rec = {
        "verdict": verdict,
        "why": why,
        "at": now,
        "broken_count": int(prev.get("broken_count") or 0),
        "last_broken_at": float(prev.get("last_broken_at") or 0),
    }
    if verdict in BROKEN_VERDICTS:
        rec["broken_count"] += 1
        rec["last_broken_at"] = now
    try:
        _verdict_path(uhost_id).write_text(json.dumps(rec, ensure_ascii=False))
    except OSError:
        pass


def _start_blocked(uhost_id: str) -> tuple[int, float] | None:
    """Whether this start should be refused. Returns (failures, hours since the last failure), or None when it should not block.

    It blocks only when the machine has failed enough times and is still failing recently; a machine that failed once a week ago starts normally,
    otherwise this rule degrades into "never allowed to boot".
    """
    try:
        rec = json.loads(_verdict_path(uhost_id).read_text())
    except Exception:  # noqa: BLE001
        return None
    if rec.get("verdict") == "ready":
        return None          # the latest measurement was good, so old failures must not block it
    broken = int(rec.get("broken_count") or 0)
    last = float(rec.get("last_broken_at") or 0)
    if broken < START_BLOCK_AFTER or not last:
        return None
    ago = (time.time() - last) / 3600
    if ago > START_BLOCK_WINDOW_H:
        return None
    return broken, ago


def cmd_verdicts(args) -> int:
    """List every machine's **latest verdict**, one line each.

    Why it exists: verdicts were always written to `data/verdict-<id>.json`, but no command ever read them back.
    So "this one has been judged dead three times" sat on disk while the agent started from zero on the same machine every round.
    This is not automated decision-making, only bringing known facts into view — whether to try to rescue it stays a human decision.

    Ordering: dead machines first, the rest newest first.
    """
    rows = []
    for path in (client.SKILL_DIR / "data").glob("verdict-*.json"):
        uid = path.stem.replace("verdict-", "")
        try:
            rec = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        rec["id"] = uid
        rows.append(rec)

    def rank(rec):
        verdict = rec.get("verdict") or ""
        bad = 0 if verdict in ("init-stuck", "timeout") else 1
        return (bad, -float(rec.get("at") or 0))

    rows.sort(key=rank)
    if not rows:
        err("error: no verdict recorded yet")
        return RC_OK
    now = time.time()
    for r in rows:
        r["broken_at"] = float(r.get("last_broken_at") or 0) or (
            float(r.get("at") or 0) if r.get("verdict") in BROKEN_VERDICTS else 0.0)
    stale = float(getattr(args, "stale", 0) or 0)
    if stale:
        # a return candidate is "has failed, and the latest failure is older than stale hours":
        # a machine that just failed may simply have had an unlucky round, so it is not hurried back.
        rows = [r for r in rows if r.get("verdict") in BROKEN_VERDICTS
                and r["broken_at"] and (now - r["broken_at"]) / 3600 >= stale]
    for rec in rows:
        uid = rec["id"]
        name = (_instance_record(uid) or {}).get("name") or "-"
        age = (time.time() - float(rec.get("at") or 0)) / 3600
        verdict = rec.get("verdict") or "?"
        why = rec.get("why") or ""
        broken = int(rec.get("broken_count") or 0)
        if getattr(args, "json", False):
            print(json.dumps({"id": uid, "name": name, "verdict": verdict, "why": why,
                              "age_h": round(age, 1), "broken_count": broken},
                             ensure_ascii=False))
        else:
            out(f"{name} {uid} {verdict} {why} age_h={age:.1f} broken={broken}")
    # "Dead" means the LATEST verdict is bad. A machine that failed yesterday and booted today still carries
    # last_broken_at, so keying on that field alone reports a healthy machine as unusable.
    dead = [r for r in rows if r.get("verdict") in BROKEN_VERDICTS]
    if dead and not stale:
        err(f"{len(dead)} machines have an unusable latest verdict. Consider returning those dead for more than 24h (--stale 24) "
            "instead of keeping them occupying a seat")
    if stale and dead:
        # exit 33 when there are candidates: the caller (human or script) must deal with it rather than reading one line and moving on.
        err(f"{len(dead)} machines have been dead for more than {stale:g}h and are return candidates: "
            "confirm the disk holds nothing unique, then compshare release <id> (prints the plan by default)")
        return RC_RELEASABLE
    return RC_OK


def cmd_pick(args) -> int:
    """Read-only: one listing for all instances, then probe channels per machine. No start, no wait, no skipping.

    Exactly one data call (`DescribeCompShareInstance`, paginated) — not one per machine —
    because a single call measures 20–40s and 13 separate calls turn a read-only command into minutes.
    """
    hosts = _list_hosts()
    if args.ids:
        want = set(args.ids)
        hosts = [h for h in hosts if h.get("UHostId") in want]
    if not hosts:
        err("error: no instance")
        return RC_STOPPED
    rows, ready = [], []
    for host in hosts:
        uid = host.get("UHostId") or ""
        state = host.get("State") or ""
        code, why = _verdict(host, age=_track_state(uid, state))
        _verdict_write(uid, code, why)
        row = {"id": uid, "state": state, "ip": _public_ip(host),
               "verdict": code, "why": why, "name": host.get("Name") or ""}
        rows.append(row)
        if code == "ready":
            ready.append(uid)
        if not args.json:
            out(f"pick {uid} {state} {row['ip'] or '-'} {code} {why}")
    if args.json:
        _json_out({"ok": bool(ready), "ready": ready, "rows": rows})
        return RC_OK if ready else RC_STOPPED
    if not ready:
        err("action: start")
        return RC_STOPPED
    return RC_OK


def cmd_info(args) -> int:
    host = _host(args.uhost_id)
    ip = next((x.get("IP") for x in host.get("IPSet") or []
               if x.get("Type") in ("BGP", "International")), "-")
    # the billing mode trails the line: a Spot instance can be reclaimed at any moment and cannot be stopped manually,
    # which is handled quite differently from a Postpay instance, so it must be visible on the first line.
    charge = host.get("ChargeType") or ""
    spot = " spot" if (charge == "Spot" or host.get("IsSpot")) else ""
    out(f"{host.get('UHostId')} {host.get('State')} {host.get('Region')}/{host.get('Zone')} "
        f"{host.get('GpuType','')} {host.get('GPU')} {host.get('CPU')} "
        f"{int(host.get('Memory') or 0) // 1024}{spot}")
    rec = _instance_record(args.uhost_id)
    out(f"ip {ip} login {rec.get('login_user') or 'root'}:{rec.get('ssh_port') or 23}")
    if not rec:
        out("record missing")
        return 0
    if (host.get("State") or "") != "Running":
        out("ssh skipped (not running)")
    else:
        for attempt in (1, 2):                       # right after boot the first hop often fails while sshd is not ready
            try:
                proc = _ssh(args.uhost_id, "true", rec, timeout=20)
                out("ssh ok" if proc.returncode == 0 else "ssh denied")
                break
            except subprocess.TimeoutExpired:
                if attempt == 2:
                    out("ssh timeout")
            except Exception as exc:  # noqa: BLE001
                out(f"ssh error {exc}")
                break
    st = watchdog.status(args.uhost_id)
    out(f"watchdog {st['pid'] if st and st.get('alive') else 'none'}")
    return 0


def cmd_exec(args) -> int:
    """Run one command on the instance.

    Do not judge a finished download by directory size: the directory may already hold other data, so a threshold misfires;
    and a missing sub-component (`text_encoder/` with configs but no `.safetensors`) does not affect the total.
    Check against the file listing; every weight must have size>0:

        R=/root/data/models/kolors-diffusers
        for f in model_index.json unet/config.json vae/config.json; do
          test -s "$R/$f" || echo "MISSING $f"
        done
        find \"$R\" -name '*.safetensors' -size -1M -print   # any "weight" under 1M is fake
    """
    cmd = args.command
    if getattr(args, "pipefail", False):
        cmd = f"set -o pipefail; {cmd}"     # otherwise `| tail -3` lets tail's 0 hide the real exit code
    proc = _ssh(args.uhost_id, cmd, timeout=args.timeout, wait=args.wait,
                init_grace=getattr(args, "init_grace", 300.0))
    if proc.stdout:
        sys.stdout.write(proc.stdout if proc.stdout.endswith("\n") else proc.stdout + "\n")
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def _xfer_prep(uhost_id: str) -> int:
    """Make ssh usable before a transfer: the alias may be stale (the IP/port change after a restart)."""
    rec = _instance_record(uhost_id)
    host = _host(uhost_id)
    if not rec or not host:
        err(f"error: no instance record for {uhost_id}")
        return 22
    if (host.get("State") or "") != "Running":
        err(f"error: {uhost_id} state={host.get('State')} not Running; transfer needs it up")
        return 31
    ip = next((x.get("IP") for x in host.get("IPSet") or []
               if x.get("Type") in ("BGP", "International")), None)
    if ip and ip != rec.get("public_ip"):
        rec["public_ip"] = ip
        _instance_write(uhost_id, {"public_ip": ip})
    sshsetup.write_alias(uhost_id, ip or rec["public_ip"], int(rec.get("ssh_port") or 23),
                         rec.get("login_user") or "root")
    return 0


def _spawn_job(job_id: str, stop: bool = False) -> int | None:
    """Hand the job to a detached process; the parent returns at once."""
    entry = Path(__file__).resolve()
    argv = [sys.executable, str(entry), "xfer", "run", job_id] + (["--stop"] if stop else [])
    proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    return proc.pid


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}T"


def cmd_xfer(args) -> int:
    """Transfer jobs: run (internal) / status / resume / log."""
    action = args.xfer_action

    if action == "run":
        # `xfer run <job_id>`: job_id lands on the positional, args.job is only set with --job
        job_id = args.job or args.uhost_id
        # no shutdown by default: a job only transfers, shutting down is a separate act. Defaulting to shutdown is how,
        # today, a small three-file job stopped a machine in the middle of a 17G download.
        job = transfer.run_upload_job(job_id, stop_when_done=args.stop)
        out(f"xfer {job['job']} {job['state']} "
            f"{sum(1 for m in job['files'].values() if m.get('done'))}/{len(job['files'])}f")
        return 0 if job["state"] == "done" else 1

    if action == "status":
        jobs = transfer.jobs_for(args.uhost_id)
        if not jobs:
            out(f"xfer {args.uhost_id} none")
            return 0
        for job in jobs:
            st = transfer.job_status(job)
            out(f"{st['job']} {st['state']} {st['done']}/{st['total']}f "
                f"{_fmt_bytes(st['done_bytes'])}/{_fmt_bytes(st['total_bytes'])} "
                f"{_fmt_bytes(st['rate_bps'])}/s {st['dir']}"
                + (f" err={st['error']}" if st["error"] else ""))
            if st["bad"]:
                out(f"  bad {' '.join(st['bad'])}")
        return 0

    if action == "resume":
        jobs = [j for j in transfer.jobs_for(args.uhost_id)
                if args.job in (None, j["job"])]
        if not jobs:
            out(f"xfer {args.uhost_id} none")
            return 0
        for job in jobs:
            if job["state"] == "done":
                out(f"{job['job']} already done")
                continue
            for meta in job["files"].values():
                meta["err"] = None
            pid = _spawn_job(job["job"])
            out(f"{job['job']} resumed pid={pid}")
        return 0

    if action == "log":
        job = transfer._job_read(args.job or args.uhost_id)
        for rel, meta in job["files"].items():
            flag = "ok" if meta.get("done") and not meta.get("err") else "fail"
            out(f"{flag} {meta['size']}B try={meta.get('tries', 0)} {rel}"
                + (f" err={meta['err']}" if meta.get("err") else ""))
        return 0

    err("error: xfer action must be run|status|resume|log")
    return 2


def _push_query(args) -> int:
    """The three query switches of upload: --status / --resume / --log."""
    jobs = transfer.jobs_for(args.uhost_id)
    if args.job:
        jobs = [j for j in jobs if j["job"] == args.job]
    if not jobs:
        out(f"up {args.uhost_id} none")
        return 0
    if args.log:
        for job in jobs:
            for rel, meta in job["files"].items():
                flag = "ok" if meta.get("done") and not meta.get("err") else "fail"
                out(f"{flag} {meta['size']}B try={meta.get('tries', 0)} {rel}"
                    + (f" err={meta['err']}" if meta.get("err") else ""))
        return 0
    if args.resume:
        for job in jobs:
            if job["state"] == "done":
                out(f"{job['job']} done")
                continue
            for meta in job["files"].values():
                meta["err"] = None
            pid = _spawn_job(job["job"], stop=args.stop)
            out(f"{job['job']} resume pid={pid}")
        return 0
    for job in jobs:
        st = transfer.job_status(job)
        bad = f" bad={len(st['bad'])}" if st["bad"] else ""
        out(f"{st['job']} {st['state']} {st['done']}/{st['total']}f "
            f"{_fmt_bytes(st['done_bytes'])}/{_fmt_bytes(st['total_bytes'])} "
            f"{_fmt_bytes(st['rate_bps'])}/s {st['dir']}{bad}")
    return 0


def cmd_push(args) -> int:
    """Upload. One output line: direction, id, bytes, files, verification method, verdict, directory.

    The destination cannot be chosen: `/root/uploaded/<timestamp>-<content hash 8 chars>[-name]/`.
    """
    if args.status or args.resume or args.log:
        return _push_query(args)
    if not args.paths:
        err("error: upload needs paths (or --status / --resume / --log)")
        return 2
    rc = _xfer_prep(args.uhost_id)
    if rc:
        return rc
    if args.bg:
        for p in args.paths:
            if not Path(p).expanduser().exists():
                err(f"error: xfer local path not found: {p}")
                return 2
        job = transfer.plan_upload(args.uhost_id, args.paths, name=args.name)
        pid = _spawn_job(job["job"])
        out(f"up {args.uhost_id} {job['total_bytes']}B {job['total_files']}f bg "
            f"{job['dir']} job={job['job']} pid={pid}")
        return 0
    res = transfer.push(args.uhost_id, args.paths, name=args.name,
                        retries=args.retries, dry_run=args.dry_run,
                        do_hash=not args.no_hash)
    verdict = "ok" if res["verify"] in ("ok", "dry-run") else "mismatch"
    extra = "" if res.get("attempts", 1) <= 1 else f" try={res['attempts']}"
    out(f"up {args.uhost_id} {res['bytes']}B {res['files']}f "
        f"{res.get('method', '-').replace('size+count', 'nohash')} {verdict} "
        f"{res['dir']}{extra}")
    if res.get("bad"):
        out(f"bad {args.uhost_id} {' '.join(res['bad'][:20])}")
    if res.get("extra"):
        out(f"extra {args.uhost_id} {' '.join(res['extra'])}")
    return 0 if verdict == "ok" else 1


def cmd_pull(args) -> int:
    """Download. Same output as upload: direction, id, bytes, files, verification method, verdict, directory."""
    rc = _xfer_prep(args.uhost_id)
    if rc:
        return rc
    res = transfer.pull(args.uhost_id, args.remote_path, dest=args.dest,
                        name=args.name, dry_run=args.dry_run)
    verdict = "ok" if res["verify"] in ("ok", "dry-run") else "mismatch"
    out(f"down {args.uhost_id} {res.get('bytes', 0)}B {res.get('files', 0)}f "
        f"{res.get('method', '-').replace('size+count', 'nohash')} {verdict} {res['dir']}")
    if res.get("bad"):
        out(f"bad {args.uhost_id} {' '.join(res['bad'][:20])}")
    return 0 if verdict == "ok" else 1


def cmd_xcheck(args) -> int:
    """Final state check. One line by default; --files lists every file."""
    res = transfer.check(args.uhost_id, args.remote_dir, local_dir=args.local)
    verdict = res.get("verify") or "listed"
    out(f"chk {args.uhost_id} {res['bytes']}B {res['files']}f {verdict} {res['dir']}")
    if args.files:
        for rel, (size, _sha) in res["files_meta"]:
            out(f"  {size}B {rel}")
    if res.get("bad"):
        out(f"bad {args.uhost_id} {' '.join(res['bad'][:20])}")
    return 0 if verdict in ("listed", "ok") else 1


def cmd_ssh_setup(args) -> int:
    """Turn an instance into something ssh-able in one step: generate a key → authorise it remotely → write ~/.ssh/config."""
    host = _host(args.uhost_id)
    ip = next((x.get("IP") for x in host.get("IPSet") or []
               if x.get("Type") in ("BGP", "International")), None)
    rec = _ensure_record(args.uhost_id, host, getattr(args, "password", None))
    if not ip:
        err(f"error: {args.uhost_id} has no public ip")
        return 22
    if not rec.get("public_ip"):
        rec["public_ip"] = ip
    port = int(rec.get("ssh_port") or 23)
    user = rec.get("login_user") or "root"

    key, pub = sshsetup.ensure_key()
    out(f"key {key}")
    if rec.get("password"):
        ok, detail = sshsetup.authorize(pub, lambda cmd: _ssh(args.uhost_id, cmd, rec, timeout=25))
        out(f"authorize {'ok' if ok else 'failed'} {detail}")
        if not ok:
            return 23
    cfg = sshsetup.write_alias(args.uhost_id, ip, port, user)
    out(f"alias {sshsetup.alias_for(args.uhost_id)} -> {user}@{ip}:{port}  ({cfg})")
    ok, detail = sshsetup.probe(args.uhost_id)
    out(f"probe {'ok' if ok else 'failed'} {detail}")
    return 0 if ok else 24


def cmd_ssh(args) -> int:
    """A stand-in for ssh. With a command it runs it and passes the exit code back; without one it opens an interactive shell."""
    argv = sshsetup.ssh_argv(args.uhost_id, " ".join(args.command) or None,
                            interactive=not args.command)
    proc = subprocess.run(argv)
    return proc.returncode


def cmd_tail(args) -> int:
    """Show a section of a remote log. The agent uses this instead of stringing together grep/cat."""
    import shlex
    cmd = f"tail -n {args.lines} {shlex.quote(args.path)}"
    if args.grep:
        cmd += f" | grep -E {shlex.quote(args.grep)}"
    if args.exclude:
        cmd += f" | grep -vE {shlex.quote(args.exclude)}"
    proc = _ssh(args.uhost_id, f"{cmd} | tail -n {args.lines}", timeout=args.timeout)
    sys.stdout.write(proc.stdout)
    if proc.returncode not in (0, 1):        # 1 = grep found nothing, which is not an error
        sys.stderr.write(proc.stderr)
    return 0


def cmd_watchdog(args) -> int:
    if args.status:
        st = watchdog.status(args.uhost_id)
        out(f"{st['uhost_id']} pid={st['pid']} alive={st['alive']}" if st else "none")
        return 0
    if args.off:
        return watchdog.stop(args.uhost_id)
    if args.foreground:
        return watchdog.run(args.uhost_id, watchdog.settings())
    pid = watchdog.spawn(args.uhost_id)
    out(str(pid) if pid else "running")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="compshare",
                                description="Compshare GPU instances: stock, quote, power, create")
    p.add_argument("--public-key", help="api PublicKey (default: credentials.json)")
    p.add_argument("--private-key", help="api PrivateKey")
    p.add_argument("--no-open", action="store_true",
                   help="do not open the create page when the key is missing (it opens by default)")
    subs = p.add_subparsers(dest="cmd", required=True)

    s = subs.add_parser("zones", help="list regions"); s.set_defaults(func=cmd_zones)

    s = subs.add_parser("images", help="platform images (walks every known region and pages fully by default)")
    s.add_argument("--region", help="query only this region; omitted = every known region")
    s.add_argument("--zone", help="query only this zone")
    s.add_argument("--grep", help="filter by name, e.g. PyTorch")
    s.add_argument("--raw", action="store_true", help="print one raw record to inspect field names")
    s.set_defaults(func=cmd_images)

    s = subs.add_parser("types", help="legal CPU/memory combinations (walks every known region by default)")
    s.add_argument("--region"); s.add_argument("--zone")
    s.add_argument("--gpu", help="card type; omitted = the card type in the most recent instance record")
    s.set_defaults(func=cmd_types, needs_gpu=True)

    s = subs.add_parser("stock", help="query stock (the only trustworthy sellable check)")
    s.add_argument("--gpu", help="card type; omitted = the card type in the most recent instance record")
    s.add_argument("--image", help="CompShareImageId, required")
    s.add_argument("--charge", default="Postpay", help="Postpay/Dynamic/Day/Month/Spot")
    s.add_argument("--region", help="omitted = walk every known region")
    s.add_argument("--zone", help="omitted = every known zone in that region")
    s.add_argument("--disk-size", type=int, default=100)
    s.add_argument("--cards", type=int, help="show only combinations with N cards")
    s.add_argument("--all", action="store_true", help="also print combinations with no stock")
    s.set_defaults(func=cmd_stock, needs_gpu=True)

    s = subs.add_parser("quote", help="price a configuration")
    s.add_argument("--region", default="cn-wlcb"); s.add_argument("--zone", default="cn-wlcb-01")
    s.add_argument("--gpu", help="card type; omitted = the card type in the most recent instance record")
    s.add_argument("--cards", type=int, default=1)
    s.add_argument("--cpu", type=int, default=16); s.add_argument("--mem-gb", type=int, default=64)
    s.add_argument("--charge", default="Postpay"); s.add_argument("--image")
    s.add_argument("--disk-size", type=int, default=100)
    s.set_defaults(func=cmd_quote, needs_gpu=True)

    s = subs.add_parser("ls", help="instance list (complete, paginated)")
    s.add_argument("--running", action="store_true", help="only Running instances (the ones being billed)")
    s.add_argument("--ids", dest="ids_only", action="store_true", help="print ids only, for pipes")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_ls)

    s = subs.add_parser("kill", help="force stop: one/many ids, or --all for every Running instance")
    s.add_argument("uhost_id", nargs="*", help="one or more uhost ids")
    s.add_argument("--all", action="store_true", help="stop every Running instance on the account")
    s.add_argument("--dry-run", action="store_true", help="list what would be stopped, send nothing")
    s.set_defaults(func=cmd_kill)

    s = subs.add_parser("card", help="record/inspect a machine's kolors configuration and smoke status (the usable-card criteria)")
    s.add_argument("uhost_id")
    s.add_argument("--kolors", choices=["absent", "partial", "ready"], help="whether the kolors weights are in place")
    s.add_argument("--smoke", choices=["ok", "fail"], help="result of the 0.1 smoke check")
    s.add_argument("--aux", "--note", dest="aux", help="note (names are assigned by the algorithm; humans only attach notes)")
    s.add_argument("--inventory", action="store_true", help="print the current record only")
    s.set_defaults(func=cmd_card)

    s = subs.add_parser("pool", help="card pool: status for usable cards / grab to take one / release-broken to clear dead machines")
    s.add_argument("pool_action", choices=["status", "grab", "fill", "release-broken"])
    s.add_argument("--target", type=int, default=POOL_DEFAULT_TARGET, help="target number of usable cards (default 10)")
    s.add_argument("--count", type=int, help="how many to grab this round (default: top up to target)")
    s.add_argument("--gpu", default="4090")
    s.add_argument("--image", help="required for grab")
    s.add_argument("--password", default=DEFAULT_PASSWORD,
                   help=f"password for new instances, default {DEFAULT_PASSWORD}")
    s.add_argument("--cards", type=int, default=1)
    s.add_argument("--charge", default="Postpay")
    s.add_argument("--disk-size", type=int, default=100)
    s.add_argument("--region"); s.add_argument("--zone")
    s.add_argument("--for", dest="for_seconds", type=float, default=0.0,
                   help="polling seconds; 0 (default) = one sweep only")
    s.add_argument("--interval", type=float, default=10.0, help="polling interval in seconds")

    s.add_argument("--keep-gpu", action="store_true",
                   help="keep it Running after grabbing (default stops at once to avoid idle billing)")
    s.add_argument("--yes", action="store_true", help="actually delete on release-broken")
    s.set_defaults(func=cmd_pool)

    s = subs.add_parser("rename", help="rename (always wk-NN; no machine is special)")
    s.add_argument("uhost_id")
    s.add_argument("name")
    s.set_defaults(func=cmd_rename)

    s = subs.add_parser("states", help="State values / whether they bill / source (the two official documents disagree: API https://www.compshare.cn/docs/gpus/instance/describecompshareinstance and UCloud https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance)")
    s.add_argument("--urls", action="store_true", help="append the document URL behind each entry")
    s.set_defaults(func=cmd_states)

    s = subs.add_parser("gauges", help="definition table: which field each number comes from and what a misread would conclude")
    s.set_defaults(func=cmd_gauges)

    s = subs.add_parser("show", help="print one instance's API record verbatim (no truncation, no reordering)")
    s.add_argument("uhost_id")
    s.set_defaults(func=cmd_show)

    s = subs.add_parser("correct", help="record/list definition corrections (changing a definition without a trace erases what was said)")
    s.add_argument("old", nargs="?", default="", help="what I said at the time")
    s.add_argument("new", nargs="?", default="", help="how the tool defines it now")
    s.add_argument("--why", default="", help="the field it rests on")
    s.set_defaults(func=cmd_correct)

    s = subs.add_parser("start", help="power on (cardless by default)")
    s.add_argument("uhost_id")
    s.add_argument("--cardless", choices=["A", "B"], default=None,
                   help="cardless mode: A = 2 cores/4G (default), B = 8 cores/16G")
    s.add_argument("--gpu", action="store_true",
                   help=f"carded mode (about 1.7 CNY/h). Only for actually running training or inference;"
                        f" downloading, installing, transferring and editing default to cardless ({BILLING['cardless_cny_per_hour']} CNY/h)")
    s.add_argument("--no-watch", dest="watch", action="store_false",
                   help="do not attach a watchdog for this boot (attached by default)")
    s.add_argument("--wait-ready", type=float, default=0.0,
                   help="after boot, wait at most this many seconds and then give one verdict (ready / not-ready);"
                        "0 = print started and return. Waits for this machine only, never switches")
    s.add_argument("--init-grace", type=float, default=90.0,
                   help="init grace: judge dead once the state persists longer than this (default 90; official wording is >5 minutes https://www.compshare.cn/docs/operation/gpufaq)")
    s.add_argument("--force", action="store_true",
                   help="start anyway when the ledger says this machine has failed three or more times")
    s.set_defaults(func=cmd_start)

    s = subs.add_parser("bootcheck", help="boot check: three chances (120s x3, gaps 60s/180s); any success means healthy")
    s.add_argument("uhost_ids", nargs="+")
    s.add_argument("--allow", type=float, default=BOOTCHECK_TIMEOUT, help="seconds allowed per boot (default 120)")
    s.add_argument("--gap1", type=float, default=BOOTCHECK_GAP1, help="gap between attempts 1 and 2 (default 60)")
    s.add_argument("--gap2", type=float, default=BOOTCHECK_GAP2, help="gap between attempts 2 and 3 (default 180)")
    s.add_argument("--stop-wait", type=float, default=90.0, help="cap on waiting for Stopped before each attempt")
    s.add_argument("--cardless", default="A", help="cardless tier (default A)")
    s.add_argument("--keep", action="store_true", help="do not stop the machine when the check passes")
    s.add_argument("--parallel", type=int, default=6,
                   help="machines checked concurrently (default 6; each in-flight machine bills cardless, and the API rate-limits past ~6)")
    s.set_defaults(func=cmd_bootcheck)

    s = subs.add_parser("stop", help="power off (GPU billing stops, disks keep billing)")
    s.add_argument("uhost_id"); s.set_defaults(func=cmd_stop)

    s = subs.add_parser("image", help="custom images: ls to list / create to build from an instance")
    s.add_argument("image_action", choices=["ls", "create"])
    s.add_argument("uhost_id", nargs="?", help="source instance for create")
    s.add_argument("--name", default="", help="image name for create (unique within the account)")
    s.add_argument("--all", action="store_true", help="include platform images when listing")
    s.add_argument("--region", help="omitted = walk every known region")
    s.set_defaults(func=cmd_image)

    s = subs.add_parser("release", help="destroy an instance (irreversible, system disk wiped)")
    s.add_argument("uhost_id")
    s.add_argument("--keep-udisk", action="store_true",
                   help="keep the data disk (the default deletes it with the instance). A kept disk keeps billing and cannot be deleted through this API")
    s.add_argument("--release-udisk", action="store_true", help=argparse.SUPPRESS)
    s.add_argument("--yes", action="store_true",
                   help="confirm the return (without it the plan is printed). Irreversible: instance and system disk both disappear")
    s.set_defaults(func=cmd_release)

    s = subs.add_parser("create", help="create an instance (stock check first)")
    s.add_argument("--region", default="cn-wlcb"); s.add_argument("--zone", default="cn-wlcb-01")
    s.add_argument("--gpu", help="card type; omitted = the card type in the most recent instance record")
    s.add_argument("--cards", type=int, default=1)
    s.add_argument("--cpu", type=int, default=16); s.add_argument("--mem-gb", type=int, default=64)
    s.add_argument("--charge", default="Postpay")
    s.add_argument("--image", required=True); s.add_argument("--name", default="")
    s.add_argument("--password", default=DEFAULT_PASSWORD,
                   help=f"login password, default {DEFAULT_PASSWORD} (base64 is handled here)")
    s.add_argument("--disk-size", type=int, default=100)
    s.set_defaults(func=cmd_create, needs_gpu=True)

    s = subs.add_parser("watch", help="poll stock and shout when there is some")
    s.add_argument("--gpu", help="card type; omitted = the card type in the most recent instance record")
    s.add_argument("--cards", type=int, default=1)
    s.add_argument("--image", help="CompShareImageId, required")
    s.add_argument("--charge", default="Postpay")
    s.add_argument("--disk-size", type=int, default=100)
    s.add_argument("--minutes", type=int, default=30)
    s.add_argument("--interval", type=int, default=20)
    s.add_argument("--open", action="store_true", help="open the create page when stock appears")
    s.set_defaults(func=cmd_watch, needs_gpu=True)
    s = subs.add_parser("info", help="current state: spec, IP, whether ssh works, watchdog")
    s.add_argument("uhost_id"); s.set_defaults(func=cmd_info)

    s = subs.add_parser("exec", help="run one command on the instance, returning stdout/stderr and the remote exit code")
    s.add_argument("uhost_id"); s.add_argument("command")
    s.add_argument("--timeout", type=int, default=25)
    s.add_argument("--wait", type=float, default=0.0,
                   help="how long to wait when the connection fails (for the window after boot when sshd is not up; 0 = do not wait)")
    s.add_argument("--init-grace", type=float, default=90.0,
                   help="judge it stuck in card init and exit at once once Initializing lasts longer than this"
                        "(default 90; official wording is >5 minutes, contact the platform https://www.compshare.cn/docs/operation/gpufaq)")
    s.set_defaults(func=cmd_exec)
    s.add_argument("--pipefail", action="store_true",
                   help="prepend set -o pipefail remotely so a pipe cannot swallow the real exit code")

    s = subs.add_parser("health", help="3-second verdict on whether this machine works now (no retry, no wait)")
    s.add_argument("uhost_id")
    s.add_argument("--no-probe", action="store_true", help="state only, do not probe ports")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_health)

    s = subs.add_parser("ready", help="check once whether it is usable (no wait by default; pass --timeout to wait)")
    s.add_argument("uhost_id")
    s.add_argument("--timeout", type=float, default=0.0,
                   help="how long to wait at most; 0 (default) = check once and return, never block")
    s.add_argument("--init-grace", type=float, default=90.0,
                   help="init grace; past it the machine is judged dead (default 90; official wording 300s https://www.compshare.cn/docs/operation/gpufaq)")
    s.set_defaults(func=cmd_ready)

    s = subs.add_parser("verdicts", help="read-only: one line per machine with its latest verdict (dead machines included)")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.add_argument("--stale", type=float, default=0.0, metavar="HOURS",
                   help="show only machines dead for more than HOURS (return candidates), e.g. --stale 24")
    s.set_defaults(func=cmd_verdicts)

    s = subs.add_parser("pick", help="read-only: one line per machine so a human can choose")
    s.add_argument("ids", nargs="*", help="candidate instance ids; omitted = the whole account")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_pick)

    s = subs.add_parser("status", help="one line: uptime, spend, and whether work is running")
    s.add_argument("uhost_id"); s.set_defaults(func=ops.cmd_status)

    s = subs.add_parser("doctor", help="ask the machine: python/torch/nvcc/rasterizer/rsync/disk")
    s.add_argument("uhost_id"); s.add_argument("--timeout", type=int, default=60)
    s.set_defaults(func=ops.cmd_doctor)

    s = subs.add_parser("settle", help="wrap up: report an ETA while work runs, stop when idle")
    s.add_argument("uhost_id")
    s.add_argument("--dry-run", action="store_true", help="print the verdict only, do not stop")
    s.add_argument("--force-stop", action="store_true", help="stop even with work running")
    s.set_defaults(func=ops.cmd_settle)

    s = subs.add_parser("push", help="scp upload (no rsync needed on the remote)")
    s.add_argument("uhost_id"); s.add_argument("src"); s.add_argument("dst")
    s.add_argument("-q", "--quiet", action="store_true")
    s.set_defaults(func=ops.cmd_copy, direction="push")

    s = subs.add_parser("pull", help="scp download")
    s.add_argument("uhost_id"); s.add_argument("src"); s.add_argument("dst")
    s.add_argument("-q", "--quiet", action="store_true")
    s.set_defaults(func=ops.cmd_copy, direction="pull")

    s = subs.add_parser("xfer", help="transfer jobs: status for progress / resume to continue / log per file")
    s.add_argument("xfer_action", choices=["run", "status", "resume", "log"])
    s.add_argument("uhost_id", nargs="?")
    s.add_argument("--job")
    s.add_argument("--stop", action="store_true", help="run: stop the machine when finished (default keeps it)")
    s.set_defaults(func=cmd_xfer)

    s = subs.add_parser("upload", help="upload into /root/uploaded/<hash>/; --status/--resume/--log query the same job")
    s.add_argument("uhost_id")
    s.add_argument("paths", nargs="*")
    s.add_argument("--name", help="directory suffix note (e.g. kolors-weights)")
    s.add_argument("--retries", type=int, default=2, help="on a verification mismatch only bad files are re-sent, at most this many times")
    s.add_argument("--no-hash", action="store_true", help="skip sha256, compare size+count only")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--bg", action="store_true", help="background job, returns job=… immediately")
    s.add_argument("--status", action="store_true", help="list this machine's upload jobs and their progress")
    s.add_argument("--resume", action="store_true", help="resume unfinished files")
    s.add_argument("--log", action="store_true", help="per-file ok/fail")
    s.add_argument("--stop", action="store_true", help="stop the machine when the background job finishes")
    s.add_argument("--job", help="apply to one job only (default: every job on this machine)")
    s.set_defaults(func=cmd_push)

    s = subs.add_parser("download", help="download into downloaded/<timestamp>-<hash>/ (verified after transfer)")
    s.add_argument("uhost_id")
    s.add_argument("remote_path")
    s.add_argument("--dest")
    s.add_argument("--name")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_pull)

    s = subs.add_parser("xcheck", help="final state check: remote directory listing plus an optional comparison with the local side")
    s.add_argument("uhost_id")
    s.add_argument("remote_dir")
    s.add_argument("--local")
    s.add_argument("--files", action="store_true", help="list every file (one line by default)")
    s.set_defaults(func=cmd_xcheck)

    s = subs.add_parser("ssh-setup", help="make the instance ssh-able: install the key, write ~/.ssh/config")
    s.add_argument("uhost_id")
    s.add_argument("--password", help="override the recorded password (older instances may not use the default)")
    s.set_defaults(func=cmd_ssh_setup)

    s = subs.add_parser("ssh", help="a stand-in for ssh (aliased, no password needed)")
    s.add_argument("uhost_id")
    s.add_argument("command", nargs=argparse.REMAINDER, help="command to run; empty opens an interactive shell")
    s.set_defaults(func=cmd_ssh)

    s = subs.add_parser("tail", help="read a remote log (optionally grepped) instead of stringing together cat/grep")
    s.add_argument("uhost_id"); s.add_argument("path")
    s.add_argument("-n", "--lines", type=int, default=20)
    s.add_argument("--grep"); s.add_argument("--exclude")
    s.add_argument("--timeout", type=int, default=40)
    s.set_defaults(func=cmd_tail)

    s = subs.add_parser("reboot", help="reboot one machine (disks kept); for a broken sshd while the instance still exists")
    s.add_argument("uhost_id")
    s.set_defaults(func=lifecycle.cmd_reboot)

    s = subs.add_parser("reinstall", help="reinstall the system image (system disk wiped; prints the plan by default)")
    s.add_argument("uhost_id")
    s.add_argument("--image", help="image id to reinstall from; omitted = the instance record / current image")
    s.add_argument("--yes", action="store_true", help="confirm execution (without it only the plan is printed)")
    s.set_defaults(func=lifecycle.cmd_reinstall)

    s = subs.add_parser("wait", help="check State once (no wait by default; pass --timeout to wait)")
    s.add_argument("uhost_id")
    s.add_argument("--state", nargs="+", default=["Running"],
                   help="target state, several allowed: --state Running Stopped")
    s.add_argument("--timeout", type=float, default=0.0,
                   help="0 (default) = check once; pass seconds explicitly to wait")
    s.set_defaults(func=lifecycle.cmd_wait)

    s = subs.add_parser("watchdog", help="background watchdog: stop the machine after consecutive idle verdicts")
    s.add_argument("uhost_id")
    s.add_argument("--foreground", action="store_true", help="run the loop in the foreground")
    s.add_argument("--status", action="store_true")
    s.add_argument("--off", action="store_true")
    s.set_defaults(func=cmd_watchdog)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # pipes such as `compshare stock | head` close stdout early; exit quietly, as shells expect.
    try:
        return _dispatch(args)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


def _dispatch(args) -> int:
    if getattr(args, "json", False):
        pass
    if getattr(args, "needs_gpu", False) and not args.gpu:
        args.gpu = _default_gpu()
        if not args.gpu:
            err(f"error: --gpu is required (no instance record to borrow a card type from)")
            return 2
    if args.public_key and args.private_key:
        client.credentials = lambda: (args.public_key, args.private_key)
    try:
        return args.func(args)
    except NoCredentials as exc:
        err(f"error: {exc}")
        if not args.no_open and client.open_cred_page():
            err(f"opened {client.CRED_URL}")
        return 20
    except ApiError as exc:
        err(f"error: {exc}")
        if exc.code == 2404:
            return RC_USAGE
        return RC_API if exc.code != -1 else RC_NET
    except KeyboardInterrupt:
        return 130


ops.bind(sys.modules[__name__])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
