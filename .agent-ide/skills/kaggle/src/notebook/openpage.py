"""Open a notebook page in the isolated Chrome profile.

This lives on its own because two callers need it and neither should import the
other: the ``notebook open`` verb, and the deploy flow when a push ends in a mode
that leaves the human something to click.

The view page is the default. The editor is only opened when a human has an
action there - a manual push waiting for Run All, or an explicit ``--edit``.
Opening an editor on a background-pushed run is worse than doing nothing: it puts
a Run All button in front of a session that is already running, and pressing it
restarts the kernel.
"""
from __future__ import annotations

import argparse

from src.chrome.browser import launch_browser, preflight_chrome_open
from src.exit_codes import OK
from src.notebook.refs import resolve_open_target


def notebook_url(username: str, slug: str, page: str = "view") -> str:
    """The Kaggle URL for a notebook on a given page."""
    url = f"https://www.kaggle.com/code/{username}/{slug}"
    return url + "/edit" if page == "edit" else url


def cmd_notebook_open(args: argparse.Namespace) -> int:
    """Open the notebook page, healing the Chrome profile first."""
    username, slug = resolve_open_target(args.notebook)
    page = "edit" if (getattr(args, "edit", False) or getattr(args, "page", "") == "edit") else "view"
    preflight_chrome_open(username)

    url = notebook_url(username, slug, page)
    print(f"Opening browser to: {url}")
    if page == "view":
        print("[INFO] View page: the run is already going, nothing to click here.")
    else:
        print("[INFO] Editor: Settings -> GPU T4 x2 -> Run All, if this run is waiting on you.")
    launch_browser(url, account=username)
    return OK
