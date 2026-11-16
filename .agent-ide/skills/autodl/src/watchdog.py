"""Background watchdog: shut the instance down when nothing is running on it.

It is **not** "power off on a dropped connection". Three facts force that difference:

1. A container cannot power itself off -- `poweroff` stops processes and billing keeps running;
2. A dropped SSH connection is invisible inside the container, where everything looks fine;
3. A `nohup` job is supposed to survive a disconnect -- powering off on disconnect would kill long jobs at the first network hiccup.

The situation actually worth guarding against: my side stopped (session ended, the Mac slept) while the machine stays up. So the test is
"is any job running", not "is any connection open".

**Process names are not consulted.** The earlier probe was `pgrep` for `run.py|train.py`, which amounts to maintaining a name list: rename the script,
wrap it in `torchrun`, run it on a GPU-less machine and it all reads as "idle".
The test is now three physical quantities: compute process count and peak utilisation from `nvidia-smi`, the one-minute load from `/proc/loadavg`,
and the write time of `/root/autodl-tmp`. Nothing to do with what the script is called, and it holds on a CPU-only machine too.

Only `rounds` consecutive idle verdicts actually trigger `stop`, so a normal gap between two epochs is not a shutdown.
When the network is unreachable the count is **not advanced**: better to pay for an extra hour than to kill a half-finished job.

**Arm it at boot, start counting once the machine is really up.** After `power_on` the instance goes through
`starting`/`booting` before `running`; the earlier implementation exited the moment it saw anything else,
so the watchdog died before it ever began tracking. It now waits (`boot_grace_seconds`) and enters the counting loop
only once the machine is up; the run ends only when an instance that was running turns into shutdown.

Configuration lives entirely in the `watchdog` section of `data/config.json`; no environment variables are read.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import client  # noqa: E402
from src.client import AUTH, NET, NO_TOKEN, OK, SSH, USAGE, CliError  # noqa: E402

DEFAULTS = {
    "interval_seconds": 60,      # once a minute after the machine is up
    "idle_minutes": 1,           # any write within that minute counts as in use
    "rounds": 30,                # 30 idle verdicts in a row before shutdown (60s x 30 = 30 min)
    "boot_grace_seconds": 900,   # upper bound on waiting for shutdown -> running
    "gpu_util_min": 10,          # peak card utilisation at or above this counts as in use (%)
    "cpu_load_min": 1,           # one-minute load at or above this counts as in use (the CPU-mode test)
}
PROBE_MARK = "---AUTODL---"
PROBE_TIMEOUT = 60
BOOT_POLL_SECONDS = 15          # poll harder before it is up; use interval afterwards
# Retrying a dead token is pointless, but one failure may be a blip: give up only after this many in a row.
MAX_BLIND_TICKS = 12


# --------------------------------------------------------------------------- config and state

def state_file() -> str:
    return os.path.join(client.data_dir(), "watchdog.json")


def log_file() -> str:
    return os.path.join(client.data_dir(), "watchdog.log")


def settings() -> dict:
    """The watchdog section of `data/config.json`, missing keys filled from the defaults."""
    merged = dict(DEFAULTS)
    try:
        with open(client.config_file(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = {}
    section = raw.get("watchdog") if isinstance(raw, dict) else None
    if isinstance(section, dict):
        for key in DEFAULTS:
            if isinstance(section.get(key), int) and section[key] > 0:
                merged[key] = section[key]
    return merged


def read_state() -> dict | None:
    try:
        with open(state_file(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_state(state: dict) -> None:
    path = state_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def drop_state() -> None:
    try:
        os.remove(state_file())
    except OSError:
        pass


def alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def log(line: str) -> None:
    path = log_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")


# --------------------------------------------------------------------------- the test (pure functions)

@dataclass(frozen=True)
class Decision:
    action: str  # exit | hold | idle | stop
    streak: int
    reason: str


@dataclass(frozen=True)
class Usage:
    """Usage seen by one probe. None of the three depends on a process name, so a renamed script, a torchrun wrapper or a CPU-only box all work."""
    load: float      # the one-minute value from /proc/loadavg
    apps: int        # compute processes holding a card, per nvidia-smi
    util: float      # peak utilisation across all cards (%)
    touched: bool    # a new file appeared under /root/autodl-tmp within the idle window


def busy(usage: Usage, *, util_min: int, load_min: int) -> str | None:
    """Return the reason it is in use, or None when idle."""
    if usage.apps:
        return f"{usage.apps} process(es) on the GPU"
    if usage.util >= util_min:
        return f"GPU at {usage.util:.0f}%"
    if usage.load >= load_min:
        return f"load {usage.load:.2f}"
    if usage.touched:
        return "files written inside the idle window"
    return None


def decide(usage: Usage, *, streak: int, rounds: int, util_min: int, load_min: int) -> Decision:
    """What to do after one probe round. No network, so it is testable. streak is the number of idle verdicts so far."""
    why = busy(usage, util_min=util_min, load_min=load_min)
    if why:
        return Decision("idle", 0, why)
    streak += 1
    if streak >= rounds:
        return Decision("stop", streak, f"idle on {streak} consecutive checks")
    return Decision("idle", streak, f"idle {streak}/{rounds}")


def parse_probe(text: str) -> Usage:
    """Parse probe output: three `key value` lines, then the write hit after PROBE_MARK.

    Without nvidia-smi (a CPU-only machine) apps/util stay 0 and the test falls through to load and writes.
    """
    head, _, tail = text.partition(PROBE_MARK)
    load, apps, util = 0.0, 0, 0.0
    for line in head.splitlines():
        key, _, value = line.strip().partition(" ")
        value = value.strip().replace(" ", "")
        try:
            if key == "load":
                load = float(value or 0)
            elif key == "apps":
                apps = int(value or 0)
            elif key == "util":
                for part in value.split(","):
                    util = max(util, float(part))  # values like [N/A] are skipped by the except below
        except ValueError:
            continue
    return Usage(load=load, apps=apps, util=util, touched=bool(tail.strip()))


def probe_command(idle_minutes: int) -> str:
    return (
        'bash -lc \''
        'echo "load $(cut -d" " -f1 /proc/loadavg)"; '
        'echo "apps $(nvidia-smi --query-compute-apps=pid --format=csv,noheader '
        '2>/dev/null | grep -c "[0-9]")"; '
        'echo "util $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits '
        '2>/dev/null | tr -d " " | paste -sd, -)"; '
        f"echo {PROBE_MARK}; "
        f"find /root/autodl-tmp -maxdepth 4 -type f -mmin -{idle_minutes} "
        "2>/dev/null | head -3'"
    )


# --------------------------------------------------------------------------- remote

def remote_exec(uuid: str, command: str, api: "client.Client") -> tuple[int, str]:
    """Run one remote command, return (exit code, output). Code 255 means ssh itself failed."""
    data = api.call("GET", client.SNAPSHOT, {"instance_uuid": uuid})
    if not isinstance(data, dict):
        raise CliError(client.API, f"snapshot for {uuid} came back empty")
    host, port, password = data.get("proxy_host"), data.get("ssh_port"), data.get("root_password")
    if not host or not port or not password:
        raise CliError(client.API, f"snapshot for {uuid} carried no ssh endpoint")
    sshpass = shutil.which("sshpass")
    if not sshpass:
        raise CliError(SSH, "no non-interactive ssh: install sshpass, or let the box idle off by hand")
    argv = [sshpass, "-p", str(password), "ssh", "-p", str(port),
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15",
            f"root@{host}", command]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return 255, ""
    return done.returncode, (done.stdout or "") + (done.stderr or "")


# --------------------------------------------------------------------------- one round

def wait_for_running(uuid: str, api: "client.Client", grace: int) -> str | None:
    """Wait until the instance really reaches running. None means it is up; otherwise the reason for giving up.

    `power_on` accepted != already running: starting/booting come in between. The earlier tick treated
    "not running" as the end, so a watchdog attached by start immediately exited on its own.
    """
    start = time.time()
    while True:
        try:
            state = str(api.call("GET", client.STATUS, {"instance_uuid": uuid})).strip()
        except CliError as exc:
            log(f"waiting for {uuid}: {exc}")
            state = ""
        if state == "running":
            return None
        if state == "shutdown" and time.time() - start > 60:
            # Still shutdown a minute after power-on: the boot was probably cancelled or failed -- do not wait idly
            return f"still {state} one minute after power_on"
        if time.time() >= start + grace:
            # Ask before declaring a timeout: the last poll should not be thrown away
            return f"not running within {grace}s"
        time.sleep(BOOT_POLL_SECONDS)


def tick(uuid: str, cfg: dict, streak: int, api: "client.Client") -> Decision:
    state = api.call("GET", client.STATUS, {"instance_uuid": uuid})
    if str(state).strip() != "running":
        return Decision("exit", streak, f"instance is {state}")

    code, text = remote_exec(uuid, probe_command(cfg["idle_minutes"]), api)
    if code != 0:
        return Decision("hold", streak, f"probe failed (ssh exit {code}); not counting this round")

    return decide(parse_probe(text), streak=streak, rounds=cfg["rounds"],
                  util_min=cfg["gpu_util_min"], load_min=cfg["cpu_load_min"])


def run_foreground(uuid: str, cfg: dict) -> int:
    try:
        api = client.Client(client.load()["tokens"])   # one slot per host: instances all live on the Pro cloud
    except CliError as exc:
        log(f"cannot start: {exc}")
        return getattr(exc, "code", client.FAILED)
    streak, blind = 0, 0
    write_state({"uuid": uuid, "pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "phase": "booting", **cfg})
    log(f"start uuid={uuid} interval={cfg['interval_seconds']}s "
        f"idle={cfg['idle_minutes']}min rounds={cfg['rounds']} "
        f"util>={cfg['gpu_util_min']}% load>={cfg['cpu_load_min']}")

    def _bye(signum, _frame):
        log(f"signal {signum}: stopping the watchdog, not the instance")
        drop_state()
        raise SystemExit(OK)

    signal.signal(signal.SIGTERM, _bye)
    signal.signal(signal.SIGINT, _bye)

    try:
        reason = wait_for_running(uuid, api, cfg["boot_grace_seconds"])
        if reason:
            log(f"exit before watching: {reason}")
            return OK
        log("running; watching usage")
        write_state({"uuid": uuid, "pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "phase": "watching", **cfg})

        while True:
            try:
                verdict = tick(uuid, cfg, streak, api)
            except CliError as exc:
                code = getattr(exc, "code", client.FAILED)
                if code == NET:
                    blind += 1
                    log(f"network down (attempt {blind}): will retry, streak stays at {streak}")
                    time.sleep(cfg["interval_seconds"])
                    continue
                if code == SSH:
                    log(f"no way to probe the box ({exc}); it can never see a job, exiting")
                    return code
                if code in (AUTH, NO_TOKEN):
                    log(f"cannot authenticate ({exc}); the watchdog cannot stop anything, exiting")
                    return code
                blind += 1
                log(f"tick failed ({exc}); attempt {blind}")
                if blind >= MAX_BLIND_TICKS:
                    log("too many failures in a row, exiting without stopping the instance")
                    return client.FAILED
                time.sleep(cfg["interval_seconds"])
                continue

            blind = 0
            if verdict.action == "exit":
                log(f"exit: {verdict.reason}")
                return OK
            if verdict.action == "stop":
                log(f"stop: {verdict.reason}; calling power_off")
                api.call("POST", client.POWER_OFF, {"instance_uuid": uuid})
                log("stopped; billing ends here")
                return OK

            log(f"tick {verdict.reason}")
            streak = verdict.streak
            time.sleep(cfg["interval_seconds"])
    finally:
        drop_state()


# --------------------------------------------------------------------------- foreground and background

def spawn_in_background(uuid: str, cfg: dict | None = None) -> int:
    """Spawn a watchdog detached from this session; do nothing if one is already running. Returns the pid, 0 if not started."""
    current = read_state()
    if current and current.get("uuid") == uuid and alive(int(current.get("pid", 0))):
        return int(current["pid"])
    if current and alive(int(current.get("pid", 0))):
        return 0  # another instance's watchdog is running; under single-container discipline this should not happen

    cfg = {**DEFAULTS, **(cfg or settings())}
    os.makedirs(client.data_dir(), exist_ok=True)
    with open(log_file(), "a", encoding="utf-8") as sink:
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), uuid, "--foreground",
             "--interval", str(cfg["interval_seconds"]),
             "--idle", str(cfg["idle_minutes"]),
             "--rounds", str(cfg["rounds"])],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=sink, stderr=sink,
            start_new_session=True, close_fds=True,
        )
    return proc.pid


def status_line() -> str:
    current = read_state()
    if not current:
        return "stopped"
    if not alive(int(current.get("pid", 0))):
        return f"stale pid={current.get('pid')} uuid={current.get('uuid')}"
    return (f"running pid={current.get('pid')} uuid={current.get('uuid')} "
            f"since={current.get('started')} idle={current.get('idle_minutes')}min "
            f"rounds={current.get('rounds')}")


def stop_watchdog() -> int:
    current = read_state()
    if not current or not alive(int(current.get("pid", 0))):
        drop_state()
        return 0
    pid = int(current["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    for _ in range(20):
        if not alive(pid):
            break
        time.sleep(0.1)
    drop_state()
    log(f"watchdog pid={pid} stopped by request")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print('usage: watchdog <uuid> [--foreground] | --status | --off', file=sys.stderr)
        return USAGE
    if argv[0] == "--status":
        print(status_line())
        return OK
    if argv[0] == "--off":
        return stop_watchdog()

    uuid = argv[0]
    cfg = settings()
    flags = {"--interval": "interval_seconds", "--idle": "idle_minutes", "--rounds": "rounds"}
    for i, token in enumerate(argv[:-1]):
        key = flags.get(token)
        if key and argv[i + 1].isdigit() and int(argv[i + 1]) > 0:
            cfg[key] = int(argv[i + 1])

    if "--foreground" in argv[1:]:
        return run_foreground(uuid, cfg)
    pid = spawn_in_background(uuid, cfg)
    print(pid if pid else "already running")
    return OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
