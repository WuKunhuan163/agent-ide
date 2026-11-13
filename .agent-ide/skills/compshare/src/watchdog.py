"""Watchdog: power the instance off when nothing on it is doing work.

The criterion is one physical fact -- is the box busy. One SSH call reads four
quantities:

    max GPU utilisation - processes holding the card - CPU load - loadavg1 / cores

Any one crossing its line counts as busy. **Process names are not consulted**:
renaming the script, wrapping it in torchrun, or running on CPU all still work.

Shutdown only after `rounds` consecutive idle checks, which rides out the normal
gap between two iterations.

**No usable data means force a stop.** After `blind_max` consecutive reads that
yield nothing usable (API/SSH errors, or a read that contains no numbers), stop
the instance. The reason is money: the moment the watchdog loses observability it
is no longer watching -- it is an hourly-billed machine plus a process that
believes it is watching. Stopping a running job by mistake costs a few hours;
not stopping burns without limit and nobody knows.

This is an explicit user instruction (2026-10-27), not a preference of mine. Do
not revert it to "leave the box alone".
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA = SKILL_DIR / "data"
CONFIG = DATA / "config.json"

DEFAULTS = {
    "interval_seconds": 60,
    "rounds": 20,               # 20 consecutive idle checks before shutdown (60s x 20 = 20 min)
    "gpu_util_min": 10.0,       # %
    "cpu_busy_min": 20.0,       # us+sy from top
    "load_per_core_min": 0.5,   # loadavg1 / cores
    "net_kib_per_s_min": 64,    # per-second network byte delta (KB/s); covers pip downloads and transfers
    "blind_max": 5,             # force a stop after 5 consecutive reads with no numbers
    "boot_grace_seconds": 900,  # upper bound for waiting on Stopped -> Running
    "boot_poll_seconds": 15,
}

PROBE_SCRIPT = (
    "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null; "
    "echo '---APPS---'; "
    "nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c . ; "
    "echo '---CPU---'; "
    "LC_ALL=C top -bn1 | grep -m1 '^%Cpu' ; "
    "echo '---NET---'; "
    "awk 'NR>2 && $1 !~ /lo:/ {r+=$2; t+=$10} END{print r+0, t+0}' /proc/net/dev; sleep 1; "
    "awk 'NR>2 && $1 !~ /lo:/ {r+=$2; t+=$10} END{print r+0, t+0}' /proc/net/dev; "
    "echo '---LOAD---'; cat /proc/loadavg; nproc"
)


class ProbeError(Exception):
    """No numbers came back. Callers advance the blind counter; they do not read
    busy/idle from this."""


# ---------------------------------------------------------------- config and paths

def settings() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        try:
            cfg.update((json.loads(CONFIG.read_text()) or {}).get("watchdog") or {})
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def state_path(uhost_id: str) -> Path:
    return DATA / f"watchdog-{uhost_id}.json"


def log_path(uhost_id: str) -> Path:
    return DATA / f"watchdog-{uhost_id}.log"


def _log(uhost_id: str, line: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    path = log_path(uhost_id)
    with path.open("a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    path.chmod(0o600)


# ---------------------------------------------------------------- readings

def _num(value) -> float | None:
    """'12.3%' / '12.3' / 12.3 -> 12.3. An empty string means "no number", not 0."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else None


def parse_probe(text: str) -> dict:
    """Split the probe output into five quantities. A missing section stays None
    and is never padded with 0."""
    out = {"gpu_util": None, "gpu_procs": None, "cpu_busy": None, "load1": None,
           "cores": None, "net_kib": None}
    section, gpus = "", []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("---") and line.endswith("---"):
            section = line.strip("-").lower()
            continue
        if section == "":
            n = _num(line)
            if n is not None:
                gpus.append(n)
        elif section == "apps":
            out["gpu_procs"] = int(_num(line) or 0)
        elif section == "cpu":
            nums = [float(x) for x in re.findall(r"\d+\.\d+", line)[:2]]
            if len(nums) == 2:
                out["cpu_busy"] = nums[0] + nums[1]
        elif section == "net":
            parts = line.split()
            if len(parts) == 2:
                if out.get("_net_first") is None:
                    out["_net_first"] = (float(parts[0]), float(parts[1]))
                else:
                    a, b = out["_net_first"]
                    delta = (float(parts[0]) - a) + (float(parts[1]) - b)
                    out["net_kib"] = max(0.0, delta) / 1024.0
        elif section == "load":
            if out["load1"] is None:
                parts = line.split()
                if len(parts) >= 3:
                    out["load1"] = _num(parts[0])
            else:
                out["cores"] = int(_num(line) or 0) or None
    out["gpu_util"] = max(gpus) if gpus else None
    out.pop("_net_first", None)
    return out


def ssh_probe(ip: str, user: str, password: str, port: int) -> dict:
    sshpass = shutil.which("sshpass")
    if not sshpass:
        raise ProbeError("sshpass not found (brew install sshpass)")
    argv = [sshpass, "-p", password, "ssh", "-n", "-p", str(port),
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR",
            # One password attempt only: sshpass retries by default, which trips the
            # host-side rate limit on its own.
            "-o", "NumberOfPasswordPrompts=1", "-o", "PubkeyAuthentication=no", f"{user}@{ip}", PROBE_SCRIPT]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=25)
    if proc.returncode != 0 and "Permission denied" in (proc.stderr or ""):
        time.sleep(1)                                   # the first hop after idling is refused; retry once
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=25)
    if proc.returncode != 0:
        raise ProbeError((proc.stderr or "ssh failed").strip()[:160])
    return parse_probe(proc.stdout)


def _record(uhost_id: str) -> dict:
    path = DATA / f"instance-{uhost_id}.json"
    if not path.exists():
        raise ProbeError(f"missing {path.name}: no password, cannot log in")
    return json.loads(path.read_text())


def probe(uhost_id: str) -> tuple[str, str, str, dict | None]:
    """Returns (state, region, zone, stats). stats is None when not Running."""
    from src import client

    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    host = next((u for u in data.get("UHostSet") or [] if u.get("UHostId") == uhost_id), None)
    if host is None:
        raise ProbeError(f"{uhost_id} not in instance list")
    state = host.get("State") or ""
    if state != "Running":
        return state, host.get("Region") or "", host.get("Zone") or "", None

    ip = next((x.get("IP") for x in host.get("IPSet") or []
               if x.get("Type") in ("BGP", "International")), None)
    if not ip:
        raise ProbeError("no public ip")

    rec = _record(uhost_id)
    # This App image logs in through the container: root on port 23, not ubuntu on 22.
    attempts = [(rec.get("login_user") or "root", int(rec.get("ssh_port") or 23))]
    if attempts[0] != ("ubuntu", 22):
        attempts.append(("ubuntu", 22))
    last: Exception | None = None
    for user, port in attempts:
        try:
            stats = ssh_probe(ip, user, rec["password"], port)
            if (user, port) != (rec.get("login_user"), rec.get("ssh_port")):
                _log(uhost_id, f"logged in as {user}@{port}; fix login_user/ssh_port in the record")
            return state, host.get("Region") or "", host.get("Zone") or "", stats
        except Exception as exc:  # noqa: BLE001 - try the next login method
            last = exc
    raise ProbeError(str(last))


# ---------------------------------------------------------------- main loop

def _region_zone(uhost_id: str) -> tuple[str, str]:
    from src import client

    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    host = next((u for u in data.get("UHostSet") or [] if u.get("UHostId") == uhost_id), {})
    return host.get("Region") or "cn-wlcb", host.get("Zone") or ""


def run(uhost_id: str, cfg: dict) -> int:
    from src import client

    interval = int(cfg["interval_seconds"])
    rounds = int(cfg["rounds"])
    blind_max = int(cfg["blind_max"])
    grace_end = time.monotonic() + int(cfg["boot_grace_seconds"])

    idle, busy_ticks, blind = 0, 0, 0
    seen_running = False
    try:
        region, zone = _region_zone(uhost_id)      # a forced stop needs these; fetch them up front
    except Exception as exc:  # noqa: BLE001
        _log(uhost_id, f"cannot locate instance yet: {exc}")
        region, zone = "cn-wlcb", ""
    _log(uhost_id, f"start pid={os.getpid()} rounds={rounds} interval={interval}s")

    while True:
        try:
            state, region, zone, stats = probe(uhost_id)
            usable = stats and any(stats.get(k) is not None
                                   for k in ("gpu_util", "cpu_busy", "load1", "net_kib"))
            if state == "Running" and not usable:
                raise ProbeError(f"no usable metrics (state={state})")
        except Exception as exc:  # noqa: BLE001 - any failed read only counts as blind
            blind += 1
            _log(uhost_id, f"blind {blind}/{blind_max}: {exc}")
            if blind > blind_max:
                _log(uhost_id, f"blind {blind} > {blind_max}: forcing stop, cannot observe this box")
                try:
                    client.call("StopCompShareInstance", Region=region or "cn-wlcb",
                                Zone=zone, UHostId=uhost_id)
                    _log(uhost_id, "force-stopped (no metrics)")
                    return 0
                except Exception as stop_exc:  # noqa: BLE001
                    _log(uhost_id, f"FORCE STOP FAILED: {stop_exc}; stop it by hand NOW")
                    return 3
            time.sleep(interval)
            continue

        blind = 0
        if state == "Running":
            seen_running = True
        elif state in ("Stopped", "Terminated"):
            if seen_running:
                _log(uhost_id, f"instance is {state}; watchdog exits")
                return 0
            if time.monotonic() > grace_end:
                _log(uhost_id, f"never reached Running within grace ({state}); watchdog exits")
                return 0
            time.sleep(int(cfg["boot_poll_seconds"]))
            continue
        else:                            # Starting / Stopping / Rebooting
            time.sleep(interval)
            continue

        gpu, procs = stats["gpu_util"], stats["gpu_procs"]
        cpu, load1, cores = stats["cpu_busy"], stats["load1"], stats["cores"] or 0
        net = stats.get("net_kib")
        busy = (
            (gpu is not None and gpu >= float(cfg["gpu_util_min"]))
            or bool(procs)                                       # a process holds the card, even at 0% this instant
            or (cpu is not None and cpu >= float(cfg["cpu_busy_min"]))
            or (load1 is not None and cores and load1 / cores >= float(cfg["load_per_core_min"]))
            or (net is not None and net >= float(cfg["net_kib_per_s_min"]))
        )
        brief = f"gpu={gpu} procs={procs} cpu={cpu} load={load1}/{cores} net={net}K/s"

        if busy:
            busy_ticks += 1
            if busy_ticks % 10 == 1:                             # log busy too, or the log holds only "start"
                _log(uhost_id, f"busy ({brief})")
            if idle:
                _log(uhost_id, f"busy again ({brief}); idle streak was {idle}")
            idle = 0
            time.sleep(interval)
            continue

        idle += 1
        _log(uhost_id, f"idle {idle}/{rounds} ({brief})")
        if idle >= rounds:
            try:
                client.call("StopCompShareInstance", Region=region or "cn-wlcb",
                            Zone=zone, UHostId=uhost_id)
                _log(uhost_id, f"stopped after {idle} idle checks")
                return 0
            except Exception as exc:  # noqa: BLE001
                _log(uhost_id, f"stop failed: {exc}")
                return 3
        time.sleep(interval)


# ---------------------------------------------------------------- process control

def spawn(uhost_id: str) -> int | None:
    """Start one in the background; returns None when one is already running."""
    current = status(uhost_id)
    if current and current.get("alive"):
        return None
    DATA.mkdir(parents=True, exist_ok=True)
    with log_path(uhost_id).open("a") as fh:
        proc = subprocess.Popen(
            [sys.executable, str(SKILL_DIR / "compshare.py"), "watchdog", uhost_id, "--foreground"],
            stdout=fh, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(SKILL_DIR))
    state_path(uhost_id).write_text(json.dumps(
        {"pid": proc.pid, "uhost_id": uhost_id, "started": int(time.time())}, indent=1))
    state_path(uhost_id).chmod(0o600)
    return proc.pid


def status(uhost_id: str) -> dict | None:
    path = state_path(uhost_id)
    if not path.exists():
        return None
    try:
        st = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        os.kill(st.get("pid") or 0, 0)
        st["alive"] = True
    except (ProcessLookupError, PermissionError, TypeError):
        st["alive"] = False
    return st


def stop(uhost_id: str) -> int:
    st = status(uhost_id)
    if not st or not st.get("alive"):
        print("none")
        state_path(uhost_id).unlink(missing_ok=True)
        return 0
    try:
        os.kill(st["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass
    state_path(uhost_id).unlink(missing_ok=True)
    print(f"stopped {st['pid']}")
    return 0
