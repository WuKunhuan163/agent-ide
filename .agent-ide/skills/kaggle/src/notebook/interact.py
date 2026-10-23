"""``notebook interact``: put one instruction in front of the human, with a button.

Why this exists
---------------
Some steps cannot be automated and are not failures: authorising Chrome to save
several files at once, accepting a licence, picking an accelerator, confirming a
download. Until now the agent had no way to say "I am waiting on you for *this*
specific thing" — it either guessed, or went quiet and assumed the artifact did
not exist.

``interact`` turns that into an explicit object: a page showing the sentence the
caller passed in, the kernel it belongs to, and one button to get there. The
agent states the instruction; the human performs it; both sides can point at the
same page afterwards.

    ... notebook interact <slug> --text "Allow multiple downloads in Chrome"

The page is not a substitute for doing the work — it is the receipt that says
who was asked, and for what.
"""
from __future__ import annotations

import argparse
import sys

from src import identity
from src.chrome.browser import launch_browser
from src.exit_codes import INPUT_USAGE, OK
from src.notebook import page
from src.notebook.refs import resolve_notebook_args


def cmd_notebook_interact(args: argparse.Namespace) -> int:
    text = (args.text or "").strip()
    if not text:
        raise identity.IdentityError(
            INPUT_USAGE, "interact: --text is required (the sentence the human reads)."
        )

    _username, _slug, notebook = resolve_notebook_args(args.notebook)
    url = args.url or page.kernel_url(notebook)
    target = page.write_page(
        kind="interact",
        ref=notebook,
        headline=text,
        url=url,
        button=args.button or f"Open {notebook.split('/')[-1]}",
    )

    opened = True
    if getattr(args, "open_page", True):
        try:
            launch_browser(f"file://{target}", account=_username)
        except identity.IdentityError as exc:
            opened = False
            print(f"[WARN] could not open Chrome: {exc}", file=sys.stderr)

    print(f"{notebook}: INTERACT")
    print(f"text:   {text}")
    print(f"page:   {target}")
    if opened:
        print("action: perform the instruction in the page, then press the button")
    else:
        print("action: open the page yourself (Chrome did not start)")
    print("wait:   blocked until the instruction is done")
    return OK


def register_interact(verbs) -> None:
    interact = verbs.add_parser(
        "interact",
        help="ask the human to do one thing on a page (download auth, licence, GPU pick)",
    )
    interact.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    interact.add_argument(
        "--text",
        required=True,
        metavar="<sentence>",
        help="the one instruction the human reads on the page",
    )
    interact.add_argument("--url", metavar="<url>", help="target of the button (default: kernel editor)")
    interact.add_argument("--button", metavar="<label>", help="button label (default: Open <slug>)")
    interact.add_argument(
        "--no-open",
        dest="open_page",
        action="store_false",
        help="write the page but do not launch Chrome (for scripted calls)",
    )
