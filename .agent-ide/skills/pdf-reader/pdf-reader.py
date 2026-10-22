"""pdf-reader: thin entry point.

Invoked either directly (``python3 pdf-reader.py --id <agent> ...``) or through the
project launcher ``.agent-tools/pdf-reader``.  All it does is hand argv to
``src/cli.py``; keeping it this small is what lets the layers below be imported and
tested without spawning a process.
"""
from __future__ import annotations

import sys

from src.cli import main


if __name__ == "__main__":
    sys.exit(main())
