"""Logging to stderr, with a hard rule: stdout stays empty.

Everything a caller reads -- the run handle, progress, per-file results, the closing
tally -- is a line here; the exit code is the machine-readable channel, and the run
directory holds the machine-readable record. (``config list --markdown`` is the one
verb that prints to stdout, because the table it prints *is* the requested product.)

One line per event, prefixed so a log reads like a shell transcript and greps in one
piece::

    pdf-reader: submit paper_p1-6.pdf
    pdf-reader: ok paper_p1-6.pdf 6p 11.8s 4 blocks
    pdf-reader: warning: no token found; falling back to flash
    pdf-reader: error: precision mode needs a token
    pdf-reader: debug: uploaded paper_p1-6.pdf (4211337 bytes)

A level is spelled out only where it changes what the line means -- a bare
``pdf-reader:`` line is ordinary progress. No fact is printed twice, and anything that is
true of every call rather than of this one belongs to ``-v``.
"""
from __future__ import annotations

import sys


_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
_LEVEL = 20


def set_level(name: str) -> None:
    global _LEVEL
    _LEVEL = _LEVELS.get(name.lower(), 20)


def enabled(level: str) -> bool:
    return _LEVELS.get(level, 20) >= _LEVEL


_LABEL = {"debug": "debug", "info": "", "warn": "warning", "error": "error"}


def log(level: str, message: str) -> None:
    if enabled(level):
        label = _LABEL.get(level, level)
        head = f"pdf-reader: {label}: " if label else "pdf-reader: "
        print(head + message, file=sys.stderr, flush=True)


def debug(message: str) -> None:
    log("debug", message)


def info(message: str) -> None:
    log("info", message)


def warn(message: str) -> None:
    log("warn", message)


def error(message: str) -> None:
    log("error", message)


def emit_stdout(payload: str) -> None:
    """Print a piece of text that *is* the requested product, and flush it.

    Only ``config list --markdown`` reaches this: the parameter table is the thing the
    caller asked for, everything else a verb produces is narration and goes to stderr.
    """
    print(payload, file=sys.stdout, flush=True)
