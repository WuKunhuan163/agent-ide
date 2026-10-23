"""The ``notebook push`` verb: argument parsing only.

The pipeline itself lives in ``deploy``, the metadata shaping in ``meta``, the
GPU guard in ``gpu_guard``, the checks in ``preflight``, the closing report in
``report``, and the difference between the two push modes in ``mode``. This file
knows none of that - it turns flags into a call.
"""
from __future__ import annotations

import argparse
import os

from src import identity
from src.notebook.deploy import run_deploy_push
from src.paths import resolve_arg


def register_push(verbs) -> None:
    push = verbs.add_parser("push", help="upload and execute a notebook from a folder")
    push.add_argument("dir", metavar="<dir>", help="folder with the notebook and kernel-metadata.json")
    push.add_argument(
        "--local-dataset",
        action="append",
        metavar="<path>",
        help="local dataset folder to upload/sync and mount (repeatable)",
    )
    push.add_argument(
        "--remote-dataset",
        action="append",
        metavar="<owner/slug>",
        help="remote dataset slug to mount (repeatable)",
    )
    push.add_argument(
        "--auto-download",
        nargs="?",
        const=os.path.expanduser("~/Downloads"),
        metavar="<dir>",
        help="wait for completion and download (skipped when the run waits for a human Run All)",
    )
    push.add_argument(
        "--no-open",
        action="store_true",
        help="force no browser tab (background mode opens none anyway; manual mode opens the editor)",
    )
    push.add_argument(
        "--force-push",
        action="store_true",
        help="push even when the notebook uses /kaggle/input but dataset_sources is empty",
    )
    push.add_argument(
        "--no-hash",
        action="store_true",
        help="NOT RECOMMENDED — skip the auto hash; reruns hit the same slug",
    )


def cmd_notebook_push(args: argparse.Namespace) -> int:
    username = identity.resolve_username()
    return run_deploy_push(
        resolve_arg(args.dir),
        username,
        push_label=f"Pushing notebook from: {args.dir}",
        assign_id=True,
        apply_placeholders=True,
        no_hash=getattr(args, "no_hash", False),
        local_dataset=getattr(args, "local_dataset", None),
        remote_dataset=getattr(args, "remote_dataset", None),
        force_push=getattr(args, "force_push", False),
        auto_download=getattr(args, "auto_download", None),
        open_after=not getattr(args, "no_open", False),
    )
