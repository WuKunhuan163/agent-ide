"""``dataset`` group: parse registration + command bodies.

Verbs are nested under the ``dataset`` group (``find``/``ls``/``create``/
``version``); the router only ever branches on the top-level group, so new verbs
land here without touching it.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime

from src import identity, kaggle_exec
from src.dataset.meta import (
    METADATA_NAME,
    ensure_metadata,
    has_metadata,
    metadata_owner,
    slugify,
)
from src.dataset.size import check_dataset_size
from src.exit_codes import INPUT_USAGE, OK, PUSH_OWNER_MISMATCH


def register_dataset(groups) -> None:
    dataset = groups.add_parser("dataset", help="search, inspect and publish datasets")
    verbs = dataset.add_subparsers(dest="dataset_cmd", metavar="<cmd>")

    find = verbs.add_parser("find", help="search Kaggle datasets")
    find.add_argument("query", metavar="<query>", help="Kaggle search query")

    ls = verbs.add_parser("ls", aliases=["files"], help="list the files of a dataset")
    ls.add_argument("dataset", metavar="<owner/slug>", help="dataset ref, e.g. user/name")

    create = verbs.add_parser("create", help="create a new private dataset from a folder")
    create.add_argument("folder", metavar="<folder>", help="folder holding the files to upload")
    create.add_argument("title", metavar="<title>", help="dataset title")

    version = verbs.add_parser("version", help="upload a new version of an existing dataset")
    version.add_argument(
        "folder", metavar="<folder>", help="folder with files and dataset-metadata.json"
    )
    version.add_argument("-m", "--message", required=True, metavar="<msg>", help="version message")


def cmd_dataset(args: argparse.Namespace) -> int:
    verb = getattr(args, "dataset_cmd", None)
    if verb == "find":
        return cmd_dataset_find(args)
    if verb in ("ls", "files"):
        return cmd_dataset_ls(args)
    if verb == "create":
        return cmd_dataset_create(args)
    if verb == "version":
        return cmd_dataset_version(args)
    raise identity.IdentityError(
        INPUT_USAGE, "dataset: pick a subcommand (find / ls / create / version)."
    )


def _require_folder(folder: str) -> str:
    if not os.path.isdir(folder):
        raise identity.IdentityError(INPUT_USAGE, f"Not a folder: {folder}")
    return folder


def cmd_dataset_find(args: argparse.Namespace) -> int:
    proc = kaggle_exec.run_kaggle_checked(["datasets", "list", "-s", args.query])
    kaggle_exec.forward_output(proc)
    return OK


def cmd_dataset_ls(args: argparse.Namespace) -> int:
    proc = kaggle_exec.run_kaggle_checked(["datasets", "files", args.dataset])
    kaggle_exec.forward_output(proc)
    return OK


def cmd_dataset_create(args: argparse.Namespace) -> int:
    folder = _require_folder(args.folder)
    check_dataset_size(folder)
    username, _token = identity.credentials()
    title = slugify(f"{args.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    ensure_metadata(folder, username, title=title)
    proc = kaggle_exec.run_kaggle_checked(
        ["datasets", "create", "-p", folder, "--dir-mode", "zip"]
    )
    kaggle_exec.forward_output(proc)
    return OK


def cmd_dataset_version(args: argparse.Namespace) -> int:
    folder = _require_folder(args.folder)
    if not has_metadata(folder):
        raise identity.IdentityError(
            INPUT_USAGE, f"No {METADATA_NAME} in {folder}; create the dataset first."
        )
    check_dataset_size(folder)
    username, _token = identity.credentials()

    owner = metadata_owner(folder)
    if owner and owner != username:
        raise identity.IdentityError(
            PUSH_OWNER_MISMATCH,
            f"{METADATA_NAME} belongs to '{owner}', but this agent is bound to '{username}'.\n"
            f"  Switch account first: config --switch-user {owner}",
        )

    proc = kaggle_exec.run_kaggle_checked(
        ["datasets", "version", "-p", folder, "-m", args.message, "--dir-mode", "zip"]
    )
    kaggle_exec.forward_output(proc)
    return OK


def sync_local_dataset(folder: str, username: str, token: dict) -> str:
    """Create or version a local folder; return the full ``username/slug``.

    Not a CLI verb: the (future) notebook push pipeline calls this for
    ``--local-dataset`` and writes the returned slug into ``dataset_sources``.
    Falls back to a new version when the dataset already exists.
    """
    _require_folder(folder)
    check_dataset_size(folder)
    slug = ensure_metadata(folder, username)
    print(f"[dataset] syncing {folder} as {username}/{slug} ...")

    create_args = ["datasets", "create", "-p", folder, "--dir-mode", "zip"]
    proc = kaggle_exec.run_kaggle(create_args, username=username, token=token)
    if proc.returncode != 0:
        blob = kaggle_exec.failure_output(proc).lower()
        if "already exists" in blob or "403" in blob or "409" in blob:
            print("[dataset] dataset already exists; uploading a new version ...")
            version_args = [
                "datasets", "version", "-p", folder, "-m", "Auto update", "--dir-mode", "zip"
            ]
            proc = kaggle_exec.run_kaggle(version_args, username=username, token=token)
            if proc.returncode != 0:
                kaggle_exec.classify_failure(version_args, proc, username)
        else:
            kaggle_exec.classify_failure(create_args, proc, username)

    kaggle_exec.forward_output(proc)
    return f"{username}/{slug}"
