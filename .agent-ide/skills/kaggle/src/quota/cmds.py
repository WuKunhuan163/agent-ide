"""``quota`` group: parse registration + command bodies.

Pseudo-state only: Kaggle exposes no quota API, so the human reads the settings
page and records the remaining GPU/TPU minutes here. The ledger lives in the
per-agent ``state.json`` under ``state["quota"][<kaggle_user>]`` so it never
collides with the ``state["notebooks"]`` ledger.

The budget itself is **30 GPU hours per account per week**, on a rolling window
whose reset the CLI cannot see. That number belongs here because it is the one
fact a plan needs and the one thing this tool used to omit: without it, a
"session limit" gets quoted instead of a weekly budget, and a 26-minute run can
be discussed as if it were eating a 12-hour allowance.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime

from src import identity
from src.exit_codes import INPUT_USAGE, OK
from src.runtime.store import load_state, save_state


def parse_time_str(text: str | None) -> int:
    """``'29h50m'`` / ``'1790m'`` / ``'29h'`` / ``'45'`` -> minutes (0 when empty)."""
    if not text:
        return 0
    lowered = text.lower().strip()
    matches = re.findall(r"(\d+)([hm])", lowered)
    minutes = 0
    for value, unit in matches:
        minutes += int(value) * (60 if unit == "h" else 1)
    if not matches and lowered.isdigit():
        minutes = int(lowered)
    return minutes


# Kaggle's weekly GPU allowance per account. TPU has its own budget that is not
# asserted here; only the GPU figure is used for the percentage.
WEEKLY_GPU_HOURS = 30


def _fmt(minutes: int) -> str:
    return f"{int(minutes // 60)}h {int(minutes % 60)}m"


def _fmt_with_budget(minutes: int) -> str:
    """``12h 30m / 30h 0m (42%)`` — the remainder alone says nothing about margin."""
    total = WEEKLY_GPU_HOURS * 60
    pct = round(100 * minutes / total) if total else 0
    return f"{_fmt(minutes)} / {_fmt(total)} ({pct}%)"


def register_quota(groups) -> None:
    quota = groups.add_parser("quota", help="record and show each account's remaining quota")
    verbs = quota.add_subparsers(dest="quota_cmd", metavar="<cmd>")

    setter = verbs.add_parser("set", help="record an account's remaining GPU/TPU time")
    setter.add_argument("username", metavar="<kaggle_user>", help="account the numbers belong to")
    setter.add_argument(
        "--gpu",
        default="0m",
        metavar="<29h50m>",
        help=f"remaining GPU time this week (budget is {WEEKLY_GPU_HOURS}h; omitted means 0 left)",
    )
    setter.add_argument("--tpu", default="0m", metavar="<20h>", help="remaining TPU time")

    shower = verbs.add_parser("show", help="print the recorded quota (all accounts by default)")
    shower.add_argument("--username", metavar="<kaggle_user>", help="limit the report to one account")


def cmd_quota(args: argparse.Namespace) -> int:
    verb = getattr(args, "quota_cmd", None)
    if verb == "set":
        return cmd_quota_set(args)
    if verb == "show":
        return cmd_quota_show(args)
    raise identity.IdentityError(INPUT_USAGE, "quota: pick a subcommand (set / show).")


def cmd_quota_set(args: argparse.Namespace) -> int:
    state = load_state()
    accounts = state.setdefault("quota", {})
    entry = accounts.setdefault(args.username, {})
    entry["gpu_minutes"] = parse_time_str(args.gpu)
    entry["tpu_minutes"] = parse_time_str(args.tpu)
    entry["last_sync"] = datetime.now().isoformat()
    save_state(state)

    print(f"Recorded quota for {args.username}:")
    print(f"  GPU: {_fmt_with_budget(entry['gpu_minutes'])}")
    print(f"  TPU: {_fmt(entry['tpu_minutes'])}")
    return OK


def cmd_quota_show(args: argparse.Namespace) -> int:
    accounts = load_state().get("quota") or {}
    wanted = getattr(args, "username", None) or identity.bound_username()
    if wanted and wanted in accounts:
        names = [wanted]
    else:
        names = sorted(accounts)
    if not names:
        print(
            f"No quota recorded yet (weekly GPU budget is {WEEKLY_GPU_HOURS}h). "
            "Record it with: quota set <kaggle_user> --gpu 29h50m"
        )
        return OK
    for name in names:
        entry = accounts.get(name) or {}
        print(f"Account: {name}")
        print(f"  GPU Quota: {_fmt_with_budget(entry.get('gpu_minutes', 0))}")
        print(f"  TPU Quota: {_fmt(entry.get('tpu_minutes', 0))}")
        print(f"  Last Sync: {entry.get('last_sync', 'Unknown')}")
        print()
    return OK
