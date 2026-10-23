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
import html
import os

from src import identity, kaggle_exec, paths
from src.chrome.browser import launch_browser
from src.exit_codes import OK
from src.kaggle_exec import failure_output
from src.notebook import observe
from src.notebook.refs import resolve_notebook_args

RUNNING_STATES = {"RUNNING", "QUEUED", "AWAITING_GPU_SELECTION"}

_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>stop {ref}</title>
<style>
  html, body {{ height: 100%; margin: 0; }}
  body {{
    display: flex; flex-direction: column; gap: 32px;
    align-items: center; justify-content: center; text-align: center;
    background: #101112; color: #f2f2f2;
    font: 20px/1.6 -apple-system, "PingFang SC", "Helvetica Neue", sans-serif;
  }}
  h1 {{ font-size: 30px; font-weight: 600; margin: 0; max-width: 24ch; }}
  a {{
    background: #f5c518; color: #101112; text-decoration: none;
    font-weight: 600; padding: 14px 30px; border-radius: 8px;
  }}
  a:hover {{ background: #ffd84d; }}
</style>
<h1>请杀死 {ref} 正在运行的任务</h1>
<a href="{url}">打开 kernel 页面 → Stop Session</a>
"""


def _kernel_url(notebook: str) -> str:
    owner, _, slug = notebook.partition("/")
    return f"https://www.kaggle.com/code/{owner}/{slug}"


def _write_page(notebook: str) -> str:
    """Write the one-sentence page under the agent's runtime dir; return its path."""
    ctx = paths.require_ctx()
    os.makedirs(ctx.runtime_dir, exist_ok=True)
    target = os.path.join(ctx.runtime_dir, f"stop_{notebook.replace('/', '__')}.html")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(
            _PAGE.format(ref=html.escape(notebook), url=html.escape(_kernel_url(notebook)))
        )
    return target


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

    page = _write_page(notebook)
    opened = True
    if getattr(args, "open_page", True):
        try:
            launch_browser(f"file://{page}", account=username)
        except identity.IdentityError as exc:
            opened = False
            print(f"[WARN] could not open Chrome: {exc}", file=__import__("sys").stderr)

    clock = observe._kernel_started_local(notebook, username, token)[0]
    stamp = f" (started {clock:%H:%M:%S})" if clock is not None else ""
    print(f"{notebook}: {status}{stamp}")
    print(f"page:   {page}")
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
