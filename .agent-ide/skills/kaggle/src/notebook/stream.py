"""Live kernel log streaming.

`kaggle kernels logs` reads the *finished* session log: while a kernel is still
RUNNING it returns an empty body, so the CLI cannot answer "how far along is it".
Kaggle exposes a separate midtier endpoint for that case:

    GET https://www.kaggle.com/api/v1/kernels/logs/stream/{owner}/{slug}

It answers `text/event-stream` and, per the CLI's own source, proxies the live
session feed while the kernel runs. Each event is one JSON object:

    data: {"stream_name": "stdout"|"stderr", "time": 11.45, "data": "line\\n"}

Two properties matter for how this command is used:

* **It replays from the session start.** A second call re-sends everything, so
  the command is "read the log so far", not "resume where I stopped". Callers
  poll it; they do not keep one connection open for an hour.
* **Silence is normal.** A notebook that prints only at arm boundaries looks
  idle for minutes. The command therefore always ends with an explicit line
  saying how long it listened and how many events arrived, so "nothing new"
  cannot be mistaken for "stream broken".

Basic auth with the account's kaggle.json is enough; no OAuth needed.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

from src import identity
from src.exit_codes import AUTH_REJECTED, EXEC_FAILED, OK
from src.notebook.refs import resolve_notebook_args

STREAM_URL = "https://www.kaggle.com/api/v1/kernels/logs/stream/{owner}/{slug}"
PENDING_NOTE = (
    "kernel not registered yet or has no session; the stream appears once the "
    "run starts"
)


def _ssl_context() -> ssl.SSLContext | None:
    """Prefer certifi's bundle: the system python on this machine ships no CA file,
    and the bare launcher interpreter does. Returning None means "use urllib's
    default", which is the same thing on a working install."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:                     # no certifi, or a broken bundle
        return None


def _auth_header(creds: dict) -> str:
    raw = f"{creds['username']}:{creds['key']}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _events(response):
    """Yield the `data` payload of each SSE event."""
    for raw in response:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line.startswith("data:"):
            continue                      # blank separators and `event:`/`id:` lines
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            yield json.loads(payload).get("data", "")
        except json.JSONDecodeError:
            yield payload + "\n"


def cmd_notebook_stream(args: argparse.Namespace) -> int:
    username, _slug, notebook = resolve_notebook_args(args.notebook)
    owner, slug = notebook.split("/", 1)
    creds = identity.read_token(username)

    req = urllib.request.Request(
        STREAM_URL.format(owner=owner, slug=slug),
        headers={"Authorization": _auth_header(creds), "Accept": "text/event-stream"},
    )
    grep = re.compile(args.grep) if args.grep else None

    started = time.monotonic()
    deadline = started + float(args.timeout)
    events = shown = 0
    tail: list[str] = []

    try:
        with urllib.request.urlopen(
            req, timeout=float(args.timeout), context=_ssl_context()
        ) as resp:
            for chunk in _events(resp):
                events += 1
                for line in chunk.splitlines():
                    if not line:
                        continue
                    if grep and not grep.search(line):
                        continue
                    shown += 1
                    if args.tail:
                        tail.append(line)
                        if len(tail) > args.tail:
                            tail.pop(0)
                    else:
                        print(line, flush=True)
                if time.monotonic() > deadline:
                    break
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[INFO] {PENDING_NOTE}", file=sys.stderr)
            return OK
        if e.code == 401:
            raise identity.IdentityError(
                AUTH_REJECTED, identity.auth_rejected_message(username, "HTTP 401")
            ) from None
        if e.code == 403:
            # Kaggle answers 403 for a slug that does not exist as well as for a
            # token that cannot see it, so this is not evidence of a bad token.
            print(
                f"[ERROR] HTTP 403 for {notebook}: the kernel may not exist, may be "
                f"private to another account, or the {username} token may be stale. "
                "Check with `config --verify`, and `notebook status <slug>` for existence.",
                file=sys.stderr,
            )
            return EXEC_FAILED
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"[ERROR] HTTP {e.code} on the log stream: {body}", file=sys.stderr)
        return EXEC_FAILED
    except (socket.timeout, TimeoutError):
        pass                              # window closed with no further output
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "CERTIFICATE_VERIFY_FAILED" in reason:
            print(
                "[ERROR] TLS trust store missing in this interpreter. "
                f"Run the command through {identity.entry_hint()} "
                "(its runtime carries certifi).",
                file=sys.stderr,
            )
        else:
            print(f"[ERROR] cannot reach the log stream: {reason}", file=sys.stderr)
        return EXEC_FAILED

    if args.tail:
        for line in tail:
            print(line)

    elapsed = time.monotonic() - started
    print(
        f"[INFO] listened {elapsed:.1f}s, {events} event(s), {shown} line(s) shown"
        + (f" (last {len(tail)})" if args.tail and len(tail) == args.tail else ""),
        file=sys.stderr,
    )
    print(
        "[INFO] the stream replays from the session start on every call; "
        "re-run to read further",
        file=sys.stderr,
    )
    return OK


def register_stream(verbs) -> None:
    p = verbs.add_parser(
        "stream",
        help="read the live log of a RUNNING kernel (SSE; `logs` only has it after the run ends)",
    )
    p.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    p.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        metavar="<sec>",
        help="how long to listen before returning with what arrived (default 20)",
    )
    p.add_argument("--grep", default=None, metavar="<regex>", help="only print matching lines")
    p.add_argument(
        "--tail",
        type=int,
        default=0,
        metavar="<n>",
        help="buffer and print only the last n matching lines (0 = print as they arrive)",
    )
