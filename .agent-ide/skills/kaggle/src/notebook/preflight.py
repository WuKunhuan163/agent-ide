"""The push checklist: is this metadata worth sending, and is it safe to send now.

Nothing here pushes. Each function answers one question and returns a verdict or
prints one block, so the deploy flow reads as a list of questions instead of a
hundred-line conditional.
"""
from __future__ import annotations

import json

from src import identity, kaggle_exec
from src.exit_codes import INPUT_USAGE
from src.runtime.store import load_state

_READABLE_CACHE: dict[tuple[str, str], bool] = {}


def meta_bool(value, default: bool = False) -> bool:
    """Parse a kernel-metadata boolean (JSON true/false or string 'true'/'false')."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def dataset_readable(source: str, username: str) -> bool:
    """Can ``username`` mount ``source``?

    Kaggle accepts a push whose ``dataset_sources`` the pushing account cannot
    read - the kernel is created, starts a GPU session, and only fails at mount
    time. A private dataset belongs to exactly one account, so a 403 here is the
    signature of "pushed from the wrong account".

    Anything that is not a 403 (network trouble, expired token) returns True: a
    flaky check must not block a push that would otherwise work.
    """
    key = (source, username)
    if key in _READABLE_CACHE:
        return _READABLE_CACHE[key]

    proc = kaggle_exec.run_kaggle(
        ["datasets", "files", source, "--page-size", "1"],
        username=username,
        token=identity.read_token(username),
    )
    detail = f"{proc.stderr or ''}{proc.stdout or ''}"
    readable = "403" not in detail
    _READABLE_CACHE[key] = readable
    return readable


def reject_unreadable_datasets(sources: list[str], username: str, *, force: bool = False) -> None:
    """Refuse a push whose dataset_sources this account cannot mount."""
    blocked = [source for source in sources if not dataset_readable(source, username)]
    if not blocked or force:
        if blocked:
            print(f"[PREFLIGHT] --force-push: pushing with unreadable datasets {blocked}")
        return
    raise identity.IdentityError(
        INPUT_USAGE,
        "dataset_sources not readable by "
        f"{username}: {blocked}. A private dataset belongs to one account, so either "
        f"`config --switch-user <owner>` and push from there, or override with --force-push.",
    )


def require_push_target(value: str, what: str) -> str:
    """Reject a missing/placeholder field with INPUT_USAGE instead of pushing junk."""
    text = str(value or "").strip()
    if not text or "username/" in text or "dataset-slug" in text:
        raise identity.IdentityError(INPUT_USAGE, f"Invalid {what}: {value!r}")
    return text

def check_and_reject_push(username: str, meta_path: str, *, force: bool = False) -> bool:
    """Preflight before push; returns False to abort (duplicate RUNNING, no --force)."""
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return True

    nb_id = meta.get("id")
    if nb_id:
        entry = (load_state().get("notebooks") or {}).get(nb_id, {})
        ledger_user = entry.get("username")
        if ledger_user and username and ledger_user != username:
            print("\n" + "=" * 72)
            print(f"[PREFLIGHT WARN] Ledger owner {ledger_user} != push account {username} for {nb_id}")
            print("=" * 72 + "\n")
        if entry.get("status") == "RUNNING" and not force:
            print("\n" + "=" * 72)
            print(f"[PREFLIGHT ERROR] Notebook {nb_id} already RUNNING in state ledger.")
            print("  Use --force-push if you intend a version bump on the same slug.")
            print("=" * 72 + "\n")
            return False

    if not (meta.get("dataset_sources") or []):
        print("\n" + "=" * 72)
        print("[PREFLIGHT WARN] dataset_sources is EMPTY.")
        print("  This project uses INPUT DATASETS, not Kaggle Secrets.")
        print("=" * 72 + "\n")

    return True

def print_push_preflight(meta: dict, push_dir: str, mode, username: str) -> None:
    """Mandatory checklist printed on every push (agents cannot skip stdout)."""
    dataset_sources = meta.get("dataset_sources") or []
    print("\n" + "=" * 72)
    print("KAGGLE PUSH PREFLIGHT")
    print("=" * 72)
    print(f"  mode:                 {mode.name}")
    print(f"  account:              {username} (bound: {identity.bound_username() or 'none'})")
    print(f"  title:                {meta.get('title', '')}")
    print(f"  dataset_sources ({len(dataset_sources)}):")
    for source in dataset_sources:
        print(f"    - {source}")
    print("  engine-payload:       prefer payload dataset VERSION over re-pushing notebook")
    print("  paths in notebook:    /kaggle/input/<slug>/...")
    required_gpu = meta.get("required_gpu", "T4")
    if mode.starts_itself:
        gpu_line = (
            f"API push sends enable_gpu={meta_bool(meta.get('enable_gpu', False))}; "
            f"Kaggle starts the run itself (probed: T4 x2); required_gpu={required_gpu}; "
            "no Run All owed"
        )
    elif meta_bool(meta.get("enable_gpu", False)):
        gpu_line = (
            f"authoring enable_gpu=true -> GPU CHECK injected; "
            f"post-push metadata enable_gpu=false; required_gpu={required_gpu}; "
            "user sets T4 x2 in browser -> Run All"
        )
    else:
        gpu_line = "push CPU -> user sets T4 x2 in browser -> Run All"
    print(f"  GPU:                  {gpu_line}")
    if mode.opens_editor:
        print(f"  after push:           opens the {mode.page} page; `--no-open` suppresses it")
    else:
        print("  after push:           no browser tab; watch it with `notebook monitor`")
    print("=" * 72 + "\n")
