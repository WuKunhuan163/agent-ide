"""Dataset size guard: reject folders above Kaggle's upload ceiling.

Kept out of ``cmds.py`` on purpose (domain helper, no CLI surface), mirroring the
``config`` package's split between persistence and command layer.
"""
from __future__ import annotations

import os

from src import identity
from src.exit_codes import DATASET_TOO_LARGE

LIMIT_BYTES = 100 * 1024 * 1024 * 1024  # 100 GiB


def dataset_size(folder: str) -> int:
    """Sum of regular-file sizes under ``folder`` (symlinks skipped)."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(folder):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if not os.path.islink(path):
                total += os.path.getsize(path)
    return total


def check_dataset_size(folder: str) -> None:
    """Application-layer gate: oversized folders must be chunked by the human.

    Raises IdentityError(DATASET_TOO_LARGE) rather than exiting in place, so the
    router stays the only place that decides the process exit code.
    """
    total = dataset_size(folder)
    if total > LIMIT_BYTES:
        raise identity.IdentityError(
            DATASET_TOO_LARGE,
            f"Dataset folder is {total / (1024 ** 3):.2f} GB, above the 100 GB ceiling:\n"
            f"  {folder}\n"
            "  Chunk it into smaller datasets to avoid the automatic-multipart upload path.",
        )
