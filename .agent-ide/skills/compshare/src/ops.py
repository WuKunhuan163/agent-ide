"""What a box is doing, environment truth, settling, and file transfer.

Kept in a separate module so the entry script's existing command bodies stay
untouched. The private helpers the entry owns (_ssh/_host/_instance_record/
_locate) are handed over through ``bind()`` at the end of loading, which keeps the
dependency from pointing back at the entry.
"""
from __future__ import annotations

import re
import subprocess
import sys

from . import client, sshsetup, watchdog

# Daemons on the remote side; presence alone is not work in progress.
DAEMONS = (
    "supervisord", "jupyter-lab", "jupyter-notebook", "sshd", "containerd",
    "dockerd", "cron", "dbus-daemon", "rsyslogd", "agetty", "polkitd",
    "systemd", "nvidia-persistenced", "unattended-upgrade",
    # Container plumbing added by the platform, not the user's work
    "tini", "sleep infinity", "filebrowser", "/model/other",
)


_ENTRY = None


def bind(entry) -> None:
    """Called by the entry at module end; hands its namespace over here."""
    global _ENTRY
    _ENTRY = entry


def _cli():
    if _ENTRY is None:
        raise RuntimeError("ops used before the entry script bound itself")
    return _ENTRY


def facts(uhost_id: str, timeout: int = 30) -> dict:
    """One SSH call returning every field needed to tell what this box is doing."""
    cli = _cli()
    script = (
        "echo UPTIME=$(cut -d. -f1 /proc/uptime); "
        "echo GPU=$(nvidia-smi --query-gpu=name,utilization.gpu,memory.used "
        "--format=csv,noheader | head -1); "
        "echo DISK=$(df -h /root | tail -1 | awk '{print $3\"/\"$2}'); "
        "echo PROCS; ps -eo etimes=,pcpu=,args= --no-headers"
    )
    proc = cli._ssh(uhost_id, script, timeout=timeout)
    out = {"uptime_s": 0, "gpu": "-", "disk": "-", "procs": []}
    for line in (proc.stdout or "").splitlines():
        if line.startswith("UPTIME="):
            out["uptime_s"] = int(line[7:] or 0)
        elif line.startswith("GPU="):
            out["gpu"] = line[4:].strip() or "-"
        elif line.startswith("DISK="):
            out["disk"] = line[5:].strip() or "-"
        elif re.match(r"^\s*\d+\s", line):
            parts = line.split(None, 2)
            if len(parts) == 3:
                out["procs"].append((int(parts[0]), float(parts[1]), parts[2]))
    return out


def work(f: dict) -> list[tuple[int, float, str]]:
    """Pick the processes doing real work; daemons and the probe itself do not count."""
    alive = []
    for etime, pcpu, cmd in f["procs"]:
        if any(d in cmd for d in DAEMONS):
            continue
        if "nvidia-smi --query-gpu" in cmd or cmd.strip().startswith("ps -eo"):
            continue
        alive.append((etime, pcpu, cmd))
    return alive


def billing(host: dict, rec: dict, uptime_s: int | None = None) -> str:
    """Split "what this box has cost" into three numbers instead of blending them.

    There used to be one `up=` plus one `cost=`, both derived from the container's
    `/proc/uptime`, which meant:
      * it covered only the current boot, yet read like "up for this long in total";
      * the platform's `UsageSeconds` is **cumulative** (every past boot included),
        and the two can differ tenfold (measured on wk-09: 5.15h this boot against
        37.8h cumulative). One number carrying two meanings is how a reading goes wrong.
    So the three fields name their own basis, and all come from raw API fields:
      up=      this boot (container uptime; only present while Running)
      usage=   cumulative usage (UsageSeconds)
      cost_now / cost_all = price x the two above
    """
    price = float(rec.get("price_cny_per_hour") or 0)
    usage_h = int(host.get("UsageSeconds") or 0) / 3600
    parts = [f"usage={usage_h:.1f}h"]
    if price:
        parts.append(f"cost_all={price * usage_h:.2f}cny")
    else:
        parts.append("cost_all=?cny")
    if uptime_s:
        up_h = uptime_s / 3600
        parts.append(f"up={up_h:.1f}h")
        if price:
            parts.append(f"cost_now={price * up_h:.2f}cny")
    return " ".join(parts)


def cmd_status(args) -> int:
    cli = _cli()
    host = cli._host(args.uhost_id)
    state = host.get("State") or "?"
    rec = cli._instance_record(args.uhost_id) or {}
    if state != "Running":
        # Three bases that must not be mixed:
        #   * `Starting` is not billed (the host is not up yet; FAQ 2.2: https://www.compshare.cn/docs/operation/gpufaq)
        #   * `Initializing` **is** billed (the container is already allocated; FAQ 2.2 only says "over 5 minutes, ask the group owner for a refund")
        #   * hourly/daily/monthly plans keep billing after shutdown (FAQ 2.1 on the same page; billing doc https://www.compshare.cn/docs/operation/charge/billdescribe); only pay-as-you-go stops
  
        # State -> billed or not comes only from the cli.STATES table, never from a
        # string hardcoded here. None in that table means the docs do not say (per
        # https://www.compshare.cn/docs/operation/gpufaq and https://www.compshare.cn/docs/operation/charge/billdescribe),
# in which case print unknown and never treat it as not billed.
        charge = host.get("ChargeType") or ""
        table = cli.STATES
        billed = table.get(state, (None, ""))[0]
        if charge and charge != "Postpay":
            gpu_tag = f"instance_billed charge={charge}"
        elif billed is True:
            gpu_tag = f"gpu_billed_{state.lower()}"
        elif billed is False:
            gpu_tag = "gpu_not_billed"
        else:
            gpu_tag = f"gpu_billing_unknown_{state.lower() or 'empty'}"
        cli.out(f"{args.uhost_id} {state} {gpu_tag} {billing(host, rec)} disk_still_billed")
        return 0
    f = facts(args.uhost_id)
    jobs = work(f)
    cli.out(f"{args.uhost_id} {state} {host.get('GpuType','')}x{host.get('GPU')} "
            f"{billing(host, rec, f['uptime_s'])} gpu={f['gpu']} disk={f['disk']} jobs={len(jobs)}")
    # This used to print only the first 6 jobs, so anything past the 7th read as
    # "nothing running". The list is the evidence; it is not truncated.
    for etime, pcpu, cmd in sorted(jobs, reverse=True):
        cli.out(f"job {etime // 60}m{etime % 60:02d}s cpu={pcpu:<5.1f} {cmd[:120]}")
    return 0


def cmd_doctor(args) -> int:
    """Ask the box itself, never trust the image name -- the label and the real
    environment can disagree (seen once)."""
    cli = _cli()
    script = r"""
# Training runs on a venv, not the system python: a non-interactive ssh does not
# load the venv, and asking the system python yields a false negative ("torch
# missing"). Measured on wk-01: system 3.10 had no torch, venv121 carried
# torch 2.4.1+cuda12.1.
VENV=$(ls -d /root/04/venv*/ /root/*venv*/ 2>/dev/null | head -1)
PY_BIN="python3"; [ -n "$VENV" ] && [ -x "${VENV}bin/python" ] && PY_BIN="${VENV}bin/python"
echo "venv    ${VENV:-none}"
echo "os      $(. /etc/os-release; echo $PRETTY_NAME)"
echo "python  $($PY_BIN -V 2>&1)"
echo "pip     $($PY_BIN -m pip -V 2>&1 | cut -d' ' -f1-2)"
echo "torch   $($PY_BIN -c 'import torch;print(torch.__version__, torch.version.cuda, torch.cuda.is_available())' 2>&1 | tail -1)"
echo "nvcc    $(NV=${CUDA_HOME:-/usr/local/cuda}; ($NV/bin/nvcc -V 2>/dev/null || nvcc -V 2>/dev/null) | grep -o 'release [0-9.]*' || echo missing)"
echo "raster  $($PY_BIN -c 'import diff_gaussian_rasterization as r;print(r.__file__)' 2>&1 | tail -1)"
echo "rsync   $(command -v rsync || echo missing)"
echo "scp     $(command -v scp || echo missing)"
echo "disk    $(df -h /root | tail -1 | awk '{print $3"/"$2}')"
echo "gpu     $(nvidia-smi --query-gpu=name,memory.total,utilization.gpu --format=csv,noheader)"
""".strip()
    proc = cli._ssh(args.uhost_id, script, timeout=args.timeout)
    sys.stdout.write(proc.stdout or "")
    if proc.returncode != 0:
        cli.err(f"doctor exit {proc.returncode}")
    return proc.returncode


def cmd_settle(args) -> int:
    """Run before leaving a turn: report an ETA if work is running, power off if not."""
    cli = _cli()
    host = cli._host(args.uhost_id)
    state = host.get("State") or "?"
    if state != "Running":
        cli.out(f"{args.uhost_id} {state} gpu_not_billed disk_still_billed")
        return 0
    f = facts(args.uhost_id)
    jobs = work(f)
    if jobs and not args.force_stop:
        oldest = max(j[0] for j in jobs)
        cli.out(f"keep jobs={len(jobs)} oldest={oldest // 60}m")
        for etime, pcpu, cmd in sorted(jobs, reverse=True)[:5]:
            cli.out(f"job {etime // 60}m{etime % 60:02d}s cpu={pcpu:<5.1f} {cmd[:110]}")
        return 0
    if args.dry_run:
        cli.out(f"idle gpu={f['gpu']} plan=stop")
        return 0
    region, zone = cli._locate(args.uhost_id)
    if watchdog.status(args.uhost_id):
        watchdog.stop(args.uhost_id)
    client.call("StopCompShareInstance", Region=region, Zone=zone, UHostId=args.uhost_id)
    cli.out(f"stop {args.uhost_id} uptime={f['uptime_s'] // 60}m")
    return 0


def cmd_copy(args) -> int:
    """scp both ways over the alias; works even when the remote has no rsync."""
    cli = _cli()
    alias = sshsetup.alias_for(args.uhost_id)
    if args.direction == "push":
        src, dst = args.src, f"{alias}:{args.dst}"
    else:
        src, dst = f"{alias}:{args.src}", args.dst
    argv = ["scp", "-r"] + (["-q"] if args.quiet else []) + [src, dst]
    proc = subprocess.run(argv)
    if proc.returncode != 0:
        cli.err(f"error: scp exit {proc.returncode}")
    return proc.returncode
