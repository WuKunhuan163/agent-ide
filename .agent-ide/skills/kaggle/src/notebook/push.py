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


class _RejectForcePush(argparse.Action):
    """Refuse the flag outright instead of letting it bypass the RUNNING gate."""

    def __call__(self, parser, namespace, values, option_string=None):
        parser.error(
            "--force-push is disabled: pushing a new version onto a notebook that is "
            "already RUNNING terminates the live session. Wait for that run to finish, "
            "or stop it explicitly first."
        )


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
    # --force-push 被刻意禁用，而不是删掉：删掉会让旧调用得到 argparse 的
    # "unrecognized arguments"，看起来像笔误；保留并直接报错，才能把原因说清。
    #
    # 它原本干两件事：跳过 dataset_sources 的空检查，以及跳过「账本里这条已经
    # RUNNING 就不许推」的门。第二件事是致命的——Kaggle 对同名 kernel 推新版本
    # 会终止它正在运行的 session，于是 agent 每修一个报错再推一次，就把用户刚
    # 跑起来的 session 杀一次，而 gate 因为 force=True 一路放行。
    push.add_argument(
        "--force-push",
        action=_RejectForcePush,
        nargs=0,
        help="DISABLED — pushing over a RUNNING notebook kills its session",
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
        auto_download=getattr(args, "auto_download", None),
        open_after=not getattr(args, "no_open", False),
    )
