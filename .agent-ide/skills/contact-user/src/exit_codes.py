"""Exit codes, grouped by what the caller should do about them.

2 is argparse's own "malformed invocation" and is reused for refusals this tool
makes itself, so a caller only has to know one "your flags were wrong" code.
"""
from __future__ import annotations


class Exit:
    OK = 0

    class Input:
        MISSING_CONTACT = 10
        MISSING_COMMIT = 11
        EMPTY_CONTACT = 12
        EMPTY_COMMIT = 13

    class Runtime:
        MISSING_ID = 3
        GUI_ABORTED = 4
        CONTEXT_REQUIRED = 7

    class Merge:
        MISSING_TARGET = 20
        MISSING_SOURCES = 21

    class Git:
        CHECKPOINT_FAILED = 40
