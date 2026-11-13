"""Instance lifecycle actions: reboot, reinstall, wait for a state.

These three are the whole toolkit for "the box is broken and I do not want to open
the console". Official docs:
  RebootCompShareInstance     reboot, disks untouched      https://www.compshare.cn/docs/gpus/instance/rebootcompshareinstance
  ReinstallCompShareInstance  reinstall the system image (**system disk wiped**, data disk untouched)  https://www.compshare.cn/docs/gpus/instance/reinstallcompshareinstance
  DescribeCompShareInstance   state lookup, used by wait  https://www.compshare.cn/docs/gpus/instance/describecompshareinstance

Shared constraints, all from the official docs:
* Reinstall is accepted only while Stopped: https://www.compshare.cn/docs/gpus/instance/reinstallcompshareinstance
* Reboot and state lookup: https://www.compshare.cn/docs/gpus/instance/rebootcompshareinstance / https://www.compshare.cn/docs/gpus/instance/describecompshareinstance
* Full state enum (the two docs disagree; the lower layer wins): https://docs.ucloud.cn/api/ucompshare-api/describe_comp_share_instance

Details:
* Reinstall needs `Stopped`; a running instance must be stopped first.
* A 10-minute per-instance lock answers repeated calls with
  `InstanceOperationInProgress` -- wait for the lock to expire, do not hammer. It
  is a return code, not a state; it cannot be inferred, only accepted.
* Reinstall keeps the existing password by default; moving from a plain host image
  to a container image regenerates it.
* This zone (cn-wlcb-01, container instances) does not support
  `UpdateCompShareInstancePorts` (measured: 230 "only supported for pod
  instances"), so ports never need refilling after a reinstall.

Reinstall is irreversible: this module only prints a plan by default and needs an
explicit `--yes` before it sends the request.
"""

from __future__ import annotations

import time

from . import client
from .client import ApiError

RC_OK = 0
RC_API = 1
RC_USAGE = 2
RC_UNAVAILABLE = 30
RC_STOPPED = 31


def _out(line: str = "") -> None:
    print(line, flush=True)


def _err(line: str) -> None:
    print(line, file=__import__("sys").stderr, flush=True)


def _host(uhost_id: str) -> dict:
    data = client.call("DescribeCompShareInstance", Limit=100, **{"UHostIds.0": uhost_id})
    for u in data.get("UHostSet") or []:
        if u.get("UHostId") == uhost_id:
            return u
    raise ApiError(-1, f"{uhost_id} not found", "DescribeCompShareInstance")


def _from_record(uhost_id: str, key: str, default=None):
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "data" / f"instance-{uhost_id}.json"
    try:
        return json.loads(p.read_text()).get(key) or default
    except Exception:  # noqa: BLE001
        return default


def cmd_reboot(args) -> int:
    """Reboot one instance. Disks and config untouched; this is the sshd fix when
    every channel is refused but the instance is still up."""
    host = _host(args.uhost_id)
    if (host.get("State") or "") == "Stopped":
        _out(f"reboot {args.uhost_id} skip=stopped")
        return RC_STOPPED
    client.call("RebootCompShareInstance", Region=host.get("Region"),
                Zone=host.get("Zone"), UHostId=args.uhost_id)
    _out(f"reboot {args.uhost_id} {host.get('State')}")
    return RC_OK


def cmd_reinstall(args) -> int:
    """Reinstall the system image. Prints a plan by default; `--yes` runs it.

    Wiping the system disk is the only irreversible part, so the plan has to show
    the target image, the current state, the disk size and what is lost. The caller
    (cli) appends what currently sits on the disk.
    """
    host = _host(args.uhost_id)
    state = host.get("State") or ""
    # Prefer the live image: the local instance-*.json was written at creation time and
    # may be long stale (one record said pytorch_2.5.0 while the box actually ran
    # cuda128_torch291, so reinstalling from the record would swap the environment).
    image = args.image or host.get("CompShareImageId") or _from_record(args.uhost_id, "image")
    if not image:
        _err("error: no image id (use --image)")
        return RC_USAGE
    plan = {
        "id": args.uhost_id,
        "state": state,
        "image": image,
        "system_disk_gb": host.get("TotalDiskSpace"),
        "wipes": "system", "keeps": "data",
    }
    _out("plan " + " ".join(f"{k}={v}" for k, v in plan.items()))
    if state != "Stopped":
        _err(f"error: reinstall needs Stopped, now {state}")
        return RC_STOPPED if state == "Stopped" else RC_UNAVAILABLE
    if not args.yes:
        _err("dry-run: add --yes to wipe system disk")
        return RC_OK
    client.call("ReinstallCompShareInstance", Region=host.get("Region"), Zone=host.get("Zone"),
                UHostId=args.uhost_id, CompShareImageId=image)
    _out(f"reinstall {args.uhost_id} image={image}")
    return RC_OK


def cmd_wait(args) -> int:
    """Wait until the instance reaches a given State. State only, not channels; use
    `ready` when the question is whether work can start.

    Split with `ready`: `wait --state Running` answers "did the state machine finish",
    `ready` answers "can I exec". The two can disagree -- Running with every port
    refusing has actually happened.
    """
    want = set(args.state)
    t0 = time.monotonic()
    deadline = t0 + args.timeout
    last = ""
    latency = 0.0
    while True:
        if time.monotonic() > deadline:
            _out(f"wait {args.uhost_id} {last or '-'} timeout")
            return RC_UNAVAILABLE
        tick = time.monotonic()
        host = _host(args.uhost_id)
        latency = time.monotonic() - tick
        state = host.get("State") or ""
        if state != last:
            _err(f"wait {args.uhost_id} {state} {time.monotonic() - t0:.0f}s")
            last = state
        if state in want:
            _out(f"wait-ok {args.uhost_id} {state} {time.monotonic() - t0:.0f}s")
            return RC_OK
        if state in ("Install Fail", "Stopped") and state not in want:
            _out(f"wait-failed {args.uhost_id} {state}")
            return RC_UNAVAILABLE
        # Stop when the remaining budget cannot cover one more poll, so a final
        # check at the deadline does not push past it
        if deadline - time.monotonic() < latency + 1.0:
            _out(f"wait-timeout {args.uhost_id} {state} budget")
            return RC_UNAVAILABLE
        time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
