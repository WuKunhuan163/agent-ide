"""``notebook`` group: parse registration + dispatch.

The verbs are spread over their own modules (``observe`` for status/logs/monitor,
``pull`` for pull/edit, ``push`` for the deploy pipeline, ``openpage`` for the
browser page) and each module owns its own ``register_*``, so this file only knows
the group's surface: it registers every verb and branches once per verb.
"""
from __future__ import annotations

import argparse

from src import identity
from src.exit_codes import INPUT_USAGE
from src.notebook import interact, observe, openpage, pull, push, stop, stream


def register_notebook(groups) -> None:
    notebook = groups.add_parser("notebook", help="Kaggle notebooks (code kernels)")
    verbs = notebook.add_subparsers(dest="nb_cmd", metavar="<cmd>")

    observe.register_observe(verbs)
    stream.register_stream(verbs)
    stop.register_stop(verbs)
    interact.register_interact(verbs)
    pull.register_pull(verbs)
    push.register_push(verbs)

    open_parser = verbs.add_parser(
        "open", help="open the notebook page: read-only view by default, editor with --edit"
    )
    open_parser.add_argument(
        "notebook", metavar="<slug>", help="slug | user:slug | user/slug | local folder"
    )
    open_parser.add_argument(
        "--edit",
        action="store_true",
        help="open the editor instead of the view page (only useful when a human must "
        "pick the accelerator or press Run All)",
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
    if verb == "interact":
        return interact.cmd_notebook_interact(args)
    if verb == "stop":
        return stop.cmd_notebook_stop(args)
    if verb == "pull":
        return pull.cmd_notebook_pull(args)
    if verb == "edit":
        return pull.cmd_notebook_edit(args)
    if verb == "push":
        return push.cmd_notebook_push(args)
    if verb == "open":
        return openpage.cmd_notebook_open(args)
    raise identity.IdentityError(
        INPUT_USAGE,
        "notebook: pick a subcommand (status / logs / stream / monitor / pull / edit / push / open).",
    )
