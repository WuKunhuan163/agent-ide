"""The deploy flow: prepare the metadata, check it, push it, record it, follow up.

The flow is written as five named steps instead of one long function, because the
steps are what the two push modes disagree about:

    _prepare   same for both: dataset sync, placeholders, id, GPU guard, validation
    _gate      same for both: preflight listing, dataset sources, duplicate RUNNING
    _push      differs only in the metadata handed to the API (see mode.py)
    _record    same for both: ledger entry plus the post-push report
    _follow_up differs: a manual run waits for a human, a background run may be
               polled and is never "opened" for someone to press Run All

Nothing here reads the interlock flag; the mode object is passed down.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile

from src import identity, kaggle_exec
from src.dataset.cmds import sync_local_dataset
from src.exit_codes import INPUT_USAGE, OK, PUSH_FAILED
from src.notebook import gpu_guard, openpage, preflight, refs, report
from src.notebook import meta as meta_mod
from src.notebook import mode as push_mode
from src.paths import resolve_arg
from src.notebook.observe import cmd_notebook_monitor
from src.runtime.store import log_event, update_notebook_state


def api_push_meta(authoring_meta: dict, *, mode) -> dict:
    """Transient API metadata for the push itself, decided by the push mode.

    Background: ``enable_gpu`` is sent as authored, so Kaggle allocates the
    accelerator and starts the run. Manual: it is forced to false, the injected
    GPU check marks the CPU session AWAITING_GPU_SELECTION, and a human picks the
    accelerator before Run All.
    """
    api_meta = dict(authoring_meta)
    api_meta["enable_gpu"] = (
        bool(authoring_meta.get("enable_gpu")) if mode.api_enable_gpu_as_authored else False
    )
    api_meta["enable_tpu"] = False
    for key in ("accelerator", "gpu_type", "accelerator_name"):
        api_meta.pop(key, None)
    return api_meta


def push_with_gpu_protocol(
    push_dir: str, authoring_meta: dict, *, username: str, mode
) -> int:
    """Write transient API metadata, ``kernels push``, restore authoring metadata."""
    meta_path = os.path.join(push_dir, "kernel-metadata.json")

    if mode.starts_itself:
        print(
            f"[INFO] {mode.name}: API push layer sends "
            f"enable_gpu={bool(authoring_meta.get('enable_gpu'))} — Kaggle starts the run "
            "itself; no accelerator pick, no Run All, no browser tab"
        )
    else:
        print(
            f"[INFO] {mode.name}: API push layer sends enable_gpu=false enable_tpu=false "
            f"(authoring enable_gpu={authoring_meta.get('enable_gpu')}) — a human picks T4 x2 "
            "and presses Run All"
        )
    meta_mod._write_meta(meta_path, api_push_meta(authoring_meta, mode=mode))
    try:
        proc = kaggle_exec.run_kaggle(
            ["kernels", "push", "-p", push_dir],
            username=username,
            token=identity.read_token(username),
        )
        kaggle_exec.forward_output(proc)
        return proc.returncode
    finally:
        meta_mod._write_meta(meta_path, authoring_meta)


def _prepare(
    push_dir: str,
    username: str,
    *,
    assign_id: bool,
    apply_placeholders: bool,
    no_hash: bool,
    local_dataset: list[str] | None,
    remote_dataset: list[str] | None,
) -> dict:
    """Everything that must be true of the files on disk before the API sees them."""
    push_dir = resolve_arg(push_dir)
    meta_path = os.path.join(push_dir, "kernel-metadata.json")
    meta = meta_mod._apply_meta_defaults(meta_mod._load_meta(push_dir), push_dir, meta_path)

    for folder in local_dataset or []:
        if not os.path.isdir(folder):
            raise identity.IdentityError(INPUT_USAGE, f"Not a folder: {folder}")
        full_slug = sync_local_dataset(folder, username, identity.read_token(username))
        if full_slug not in meta["dataset_sources"]:
            meta["dataset_sources"].append(full_slug)

    for dataset in remote_dataset or []:
        if dataset not in meta["dataset_sources"]:
            meta["dataset_sources"].append(dataset)

    if apply_placeholders:
        meta_mod.apply_push_placeholders(meta, push_dir, username, skip_hash=no_hash)

    if assign_id:
        title = meta.get("title", "")
        if not title:
            raise identity.IdentityError(INPUT_USAGE, "'title' is required in kernel-metadata.json")
        meta["id"] = f"{username}/{refs.slugify(title)}"
        print(f"[INFO] Auto-generated missing id: {meta['id']}")

    meta_mod._write_meta(meta_path, meta)

    authoring_meta, gpu_authoring = gpu_guard.inject_gpu_assertion(meta, push_dir)
    meta_mod._validate_push_meta(authoring_meta, push_dir)
    return {
        "dir": push_dir,
        "meta_path": meta_path,
        "meta": meta,
        "authoring": authoring_meta,
        "gpu_authoring": gpu_authoring,
    }


def _gate(prepared: dict, username: str, *, push_dir: str, force_push: bool, mode) -> None:
    """Refuse a push that cannot work, or one that would duplicate a live run."""
    authoring_meta = prepared["authoring"]
    preflight.print_push_preflight(authoring_meta, push_dir, mode, username)

    needs_input = meta_mod._notebook_needs_input_dataset(push_dir, authoring_meta)
    if needs_input and not authoring_meta.get("dataset_sources") and not force_push:
        raise identity.IdentityError(
            INPUT_USAGE,
            "Notebook references /kaggle/input but dataset_sources is empty. "
            "Add datasets / --remote-dataset, or override with --force-push.",
        )
    if needs_input and not authoring_meta.get("dataset_sources"):
        print("[PREFLIGHT] dataset_sources empty but --force-push given; continuing.", file=sys.stderr)

    # a private dataset belongs to one account; pushing from another one creates a
    # kernel that starts a GPU session and then fails at mount time
    preflight.reject_unreadable_datasets(
        authoring_meta.get("dataset_sources") or [], username, force=force_push
    )

    if not preflight.check_and_reject_push(username, prepared["meta_path"], force=force_push):
        raise identity.IdentityError(
            PUSH_FAILED,
            f"{prepared['meta'].get('id')} is already RUNNING in the state ledger; "
            "pass --force-push.",
        )


def _record(prepared: dict, username: str, exit_code: int, mode) -> tuple[str, str] | None:
    """Write the ledger entry and print the report a human will act on."""
    notebook_id = prepared["meta"].get("id")
    if not notebook_id:
        return None
    owner, short_id = report.print_post_push_guidance(
        prepared["authoring"], username, exit_code, mode
    )
    update_notebook_state(
        username,
        notebook_id,
        "RUNNING" if exit_code == 0 else f"PUSH_EXIT_{exit_code}",
        requires_user_gpu=prepared["gpu_authoring"],
    )
    log_event(username, "PUSH_NOTEBOOK", notebook_id)
    return owner, short_id


def _follow_up(
    prepared: dict,
    username: str,
    exit_code: int,
    *,
    auto_download: str | None,
    open_after: bool,
    mode,
    short_id: str,
    owner: str,
) -> int:
    """The mode-dependent tail: poll it, open it, or explicitly do neither."""
    if exit_code != 0:
        return exit_code

    if auto_download:
        if mode.requires_run_all:
            print(
                "\n[WARN] --auto-download skipped: this run waits for a human Run All. "
                "Align status with the user instead.",
                file=sys.stderr,
            )
        else:
            print("\n[INFO] --auto-download: switching to monitor mode...")
            code = cmd_notebook_monitor(
                argparse.Namespace(
                    notebook=prepared["meta"]["id"], download_dir=auto_download, no_logs=False
                )
            )
            if code != OK:
                return code

    if open_after and mode.opens_editor:
        code = openpage.cmd_notebook_open(
            argparse.Namespace(notebook=f"{owner}/{short_id}", page=mode.page)
        )
        if code != OK:
            print(
                f"\n[WARN] Post-push notebook open failed for {owner}/{short_id} "
                f"(exit {code}); the push itself succeeded — open it manually.",
                file=sys.stderr,
            )
    return exit_code


def run_deploy_push(
    push_dir: str,
    username: str,
    *,
    push_label: str,
    assign_id: bool = False,
    apply_placeholders: bool = True,
    no_hash: bool = False,
    local_dataset: list[str] | None = None,
    remote_dataset: list[str] | None = None,
    force_push: bool = False,
    auto_download: str | None = None,
    open_after: bool = True,
) -> int:
    """Prepare -> gate -> push -> record -> follow up. Returns the exit code."""
    mode = push_mode.current()
    prepared = _prepare(
        push_dir,
        username,
        assign_id=assign_id,
        apply_placeholders=apply_placeholders,
        no_hash=no_hash,
        local_dataset=local_dataset,
        remote_dataset=remote_dataset,
    )

    _gate(prepared, username, push_dir=prepared["dir"], force_push=force_push, mode=mode)

    print(f"[INFO] Pushing and executing notebook from {prepared['dir']}...")
    exit_code = push_with_gpu_protocol(
        prepared["dir"], prepared["authoring"], username=username, mode=mode
    )

    if exit_code == 0 and prepared["authoring"].get("dataset_sources"):
        _verify_pushed_dataset_sources(
            prepared["authoring"], username, list(prepared["authoring"]["dataset_sources"])
        )

    recorded = _record(prepared, username, exit_code, mode)
    meta_mod._write_meta(prepared["meta_path"], prepared["authoring"])
    if recorded is None:
        return exit_code

    owner, short_id = recorded
    return _follow_up(
        prepared,
        username,
        exit_code,
        auto_download=auto_download,
        open_after=open_after,
        mode=mode,
        short_id=short_id,
        owner=owner,
    )


def _verify_pushed_dataset_sources(meta: dict, username: str, pushed: list[str]) -> None:
    """Pull the pushed metadata back and warn on any dataset_source that did not land."""
    verify_dir = tempfile.mkdtemp(prefix="kaggle_push_verify_")
    try:
        proc = kaggle_exec.run_kaggle(
            ["kernels", "pull", meta["id"], "-p", verify_dir, "-m"],
            username=username,
            token=identity.read_token(username),
        )
        remote_meta = os.path.join(verify_dir, "kernel-metadata.json")
        if proc.returncode == 0 and os.path.isfile(remote_meta):
            with open(remote_meta, encoding="utf-8") as f:
                remote = list(json.load(f).get("dataset_sources") or [])
            missing = [source for source in pushed if source not in remote]
            if missing:
                print(
                    f"[WARN] push ok but remote dataset_sources missing: {missing}",
                    file=sys.stderr,
                )
    finally:
        shutil.rmtree(verify_dir, ignore_errors=True)
