"""``notebook stop``: hand the stop action to the human, because the API has none.

Why this is a page and not an HTTP call
---------------------------------------
The ``kaggle`` client exposes no cancel/stop for a kernel run. ``kernels delete``
is the only verb that ends one, and it deletes the kernel with it — versions,
output and all — so it is not a stop, it is a demolition. For an interlock push
there is not even that: the API layer is pushed CPU-only, and the session that
burns GPU hours was started by a human pressing Run All, so the tool holds no
handle on it at all.

What is left is the pattern the rest of this skill already uses: put the decision
in front of the human, at the exact place where the action exists. Hence a
one-sentence page in the isolated Chrome profile, with a button that lands on the
kernel editor, where "Stop Session" is two centimetres from the cursor.

The agent's job is to say *which* run to kill and *why it cannot*. The human's
job is the click. Anything else either deletes work or silently keeps burning
quota.
"""
from __future__ import annotations

import argparse
import sys

from src import identity, kaggle_exec, paths
from src.chrome.browser import launch_browser
from src.exit_codes import OK
from src.kaggle_exec import failure_output
from src.notebook import observe, page
from src.notebook.refs import resolve_notebook_args

RUNNING_STATES = {"RUNNING", "QUEUED", "AWAITING_GPU_SELECTION"}

def _current_state(notebook: str, username: str, token: dict) -> str:
    """Classified state, using the same rules as ``notebook status``."""
    proc = kaggle_exec.run_kaggle(
        ["kernels", "status", notebook], username=username, token=token
    )
    api_status = observe._parse_api_kernel_status(failure_output(proc))
    log_text = observe._kernel_logs_text(notebook, username, token)
    status, _note = observe._classify_kernel_state(
        api_status,
        log_text,
        requires_user_gpu=observe.notebook_requires_user_gpu(notebook),
    )
    return status


def cmd_notebook_stop(args: argparse.Namespace) -> int:
    username, _slug, notebook = resolve_notebook_args(args.notebook)
    token = identity.read_token(username)

    status = _current_state(notebook, username, token)
    if status not in RUNNING_STATES:
        print(f'{notebook} has status "{status}" — nothing to stop.')
        return OK

    target = page.write_page(
        kind="stop",
        ref=notebook,
        headline=f"Stop the run of {notebook}",
        url=page.kernel_url(notebook),
        button="Open kernel → Stop Session",
    )
    opened = True
    if getattr(args, "open_page", True):
        try:
            launch_browser(f"file://{target}", account=username)
        except identity.IdentityError as exc:
            opened = False
            print(f"[WARN] could not open Chrome: {exc}", file=sys.stderr)

    clock = observe._kernel_started_local(notebook, username, token)[0]
    stamp = f" (started {clock:%H:%M:%S})" if clock is not None else ""
    print(f"{notebook}: {status}{stamp}")
    print(f"page:   {target}")
    if opened:
        print('action: open the page, press "Stop Session"')
    else:
        print("action: open the page yourself (Chrome did not start), press \"Stop Session\"")
    print("note:   no API cancel; `kernels delete` would drop the kernel too")
    return OK


def register_stop(verbs) -> None:
    stop = verbs.add_parser(
        "stop",
        help="terminate a running kernel — opens a page for the human, since the API cannot",
    )
    stop.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    stop.add_argument(
        "--no-open",
        dest="open_page",
        action="store_false",
        help="write the page but do not launch Chrome (for scripted calls)",
    )
