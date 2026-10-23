"""``notebook`` group: parse registration + dispatch.

The verbs are spread over their own modules (``observe`` for status/logs/monitor,
``pull`` for pull/edit, ``push`` for the deploy pipeline) and each module owns its
own ``register_*`` so this file only knows the group's surface: it registers every
verb and branches once per verb. ``open`` stays here — it is the only verb that
touches the browser and has no data layer.
"""
from __future__ import annotations

import argparse

from src import identity
from src.chrome.browser import launch_browser, preflight_chrome_open
from src.exit_codes import INPUT_USAGE, OK
from src.notebook import observe, pull, push, stream
from src.notebook.refs import resolve_open_target


def register_notebook(groups) -> None:
    notebook = groups.add_parser("notebook", help="Kaggle notebooks (code kernels)")
    verbs = notebook.add_subparsers(dest="nb_cmd", metavar="<cmd>")

    observe.register_observe(verbs)
    stream.register_stream(verbs)
    pull.register_pull(verbs)
    push.register_push(verbs)

    open_parser = verbs.add_parser("open", help="open the notebook in Chrome (browser edit/run)")
    open_parser.add_argument(
        "notebook", metavar="<slug>", help="slug | user:slug | user/slug | local folder"
    )


def cmd_notebook(args: argparse.Namespace) -> int:
    verb = getattr(args, "nb_cmd", None)
    if verb == "status":
        return observe.cmd_notebook_status(args)
    if verb == "logs":
        return observe.cmd_notebook_logs(args)
    if verb == "stream":
        return stream.cmd_notebook_stream(args)
    if verb == "monitor":
        return observe.cmd_notebook_monitor(args)
    if verb == "pull":
        return pull.cmd_notebook_pull(args)
    if verb == "edit":
        return pull.cmd_notebook_edit(args)
    if verb == "push":
        return push.cmd_notebook_push(args)
    if verb == "open":
        return cmd_notebook_open(args)
    raise identity.IdentityError(
        INPUT_USAGE,
        "notebook: pick a subcommand (status / logs / stream / monitor / pull / edit / push / open).",
    )


def cmd_notebook_open(args: argparse.Namespace) -> int:
    """Open the browser editor for a notebook, healing the Chrome profile first."""
    username, slug = resolve_open_target(args.notebook)
    preflight_chrome_open(username)

    url = f"https://www.kaggle.com/code/{username}/{slug}/edit"
    print(f"Opening browser to: {url}")
    print(
        "[INFO] Accelerator: Settings -> GPU T4 x2 -> wait for restart -> Run All. "
        "Do NOT select P100 (API push uses enable_gpu=false to avoid P100 auto-assign)."
    )
    launch_browser(url, account=username)
    return OK
