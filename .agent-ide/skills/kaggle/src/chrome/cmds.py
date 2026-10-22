"""``chrome`` group: parse registration + command body.

One verb (``check``): a read-only profile verdict the agent runs before any
browser open. The router only ever branches on the top-level group, so new verbs
land here without touching it.
"""
from __future__ import annotations

import argparse

from src import identity
from src.chrome.browser import assess_chrome_profile
from src.exit_codes import BROWSER_PROFILE_CORRUPT, INPUT_USAGE, OK


def register_chrome(groups) -> None:
    chrome = groups.add_parser("chrome", help="inspect the Chrome profile used to open pages")
    verbs = chrome.add_subparsers(dest="chrome_cmd", metavar="<cmd>")

    verbs.add_parser(
        "check",
        help="report Chrome profile corruption before an open (41 = corrupt, needs a manual fix)",
    )


def cmd_chrome(args: argparse.Namespace) -> int:
    verb = getattr(args, "chrome_cmd", None)
    if verb == "check":
        return cmd_chrome_check()
    raise identity.IdentityError(INPUT_USAGE, "chrome: pick a subcommand (check).")


def cmd_chrome_check() -> int:
    """Read-only verdict: never launches Chrome and never modifies profile contents."""
    account = identity.bound_username()
    report = assess_chrome_profile(account)
    for key in (
        "verdict",
        "profile_dir",
        "corrupt",
        "healthy_prefs",
        "log_corrupt",
        "chrome_pids",
        "log_path",
        "action",
    ):
        print(f"{key + ':':<15}{report[key]}")
    return BROWSER_PROFILE_CORRUPT if report["corrupt"] else OK
