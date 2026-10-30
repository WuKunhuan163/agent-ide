#!/usr/bin/env python3
"""Thin entry: ``python3 .agent-ide/skills/autodl/autodl.py <command> [args]``.

Everything else is in ``src/cli.py`` (verbs) and ``src/client.py`` (token,
request, envelope). No state is kept between calls except the token a human
pasted into ``data/credentials.json``.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli import main  # noqa: E402  (path must be set first)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
