"""Cross-cutting contract gates.

Two families live here, both about *not bypassing the contract*:

1. The official-CLI passthrough — whatever the router does not own falls through
   to the official ``kaggle`` CLI, gated by exactly two named contracts:
   ``kernels push`` is redirected to ``notebook push`` (the GPU anti-P100
   protocol lives there), and ``kernels output`` is reserved for the monitor's
   own artifact recovery. There is no per-family verb whitelist: any other
   passthrough command runs as-is.
2. The push contract — preflight checklist, duplicate-RUNNING rejection and the
   post-push guidance that must print even when a GPU notebook exits non-zero.
   ``run_kernels_output_whitelist`` is the one permitted ``kernels output``.
"""
from __future__ import annotations

import json
import os
import sys

from src import identity, kaggle_exec
from src.exit_codes import BLOCKED_BY_CONTRACT, INPUT_USAGE
from src.runtime.store import load_state


def meta_bool(value, default: bool = False) -> bool:
    """Parse a kernel-metadata boolean (JSON true/false or string 'true'/'false')."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


# Not a whitelist: the only passthrough verb that must never run is `kernels push`,
# because it bypasses the GPU anti-P100 protocol that lives in `notebook push`.
# `kernels output` is handled by guard_kernels_output_passthrough below.
FORBIDDEN_PASSTHROUGH: dict[str, frozenset[str]] = {
    "kernels": frozenset({"push"}),
}

OUTPUT_ALLOW_ENV = "KAGGLE_ALLOW_OUTPUT"
OUTPUT_ALLOW_FLAG = "--allow-output"


def _hint() -> str:
    return identity.entry_hint()


def _block(argv: list[str], reason: str) -> None:
    print("\n" + "=" * 72, file=sys.stderr)
    print(f"[BLOCKED] passthrough not allowed: {' '.join(argv[:3])}", file=sys.stderr)
    print(f"  Reason: {reason}", file=sys.stderr)
    print(f"  Push:   {_hint()} notebook push <dir>", file=sys.stderr)
    print(f"  Edit:   {_hint()} notebook edit <slug> '<json>'", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    raise identity.IdentityError(BLOCKED_BY_CONTRACT, reason)


def enforce_passthrough_contract(argv: list[str]) -> list[str]:
    """Refuse only the named contract violation; hand everything else to the official CLI."""
    verb = argv[0]
    sub = argv[1] if len(argv) > 1 else ""
    if sub in FORBIDDEN_PASSTHROUGH.get(verb, frozenset()):
        _block(argv, "kernels push is forbidden — use notebook push (GPU anti-P100 protocol)")
    return argv


def guard_kernels_output_passthrough(argv: list[str]) -> list[str]:
    """Block routine ``kernels output``; notebook acceptance is logs-only."""
    if len(argv) < 3 or argv[0] != "kernels" or argv[1] != "output":
        return argv
    if os.environ.get(OUTPUT_ALLOW_ENV) == "1" or OUTPUT_ALLOW_FLAG in argv:
        return [arg for arg in argv if arg != OUTPUT_ALLOW_FLAG]
    print("\n" + "=" * 72, file=sys.stderr)
    print("[BLOCKED] kernels output — notebook acceptance is logs-only", file=sys.stderr)
    print(f"  Use:  {_hint()} notebook status <slug>", file=sys.stderr)
    print(f"  Use:  {_hint()} notebook logs <slug>", file=sys.stderr)
    print(f"  Human artifact download: re-run with {OUTPUT_ALLOW_FLAG} or {OUTPUT_ALLOW_ENV}=1", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    raise identity.IdentityError(
        BLOCKED_BY_CONTRACT, "kernels output is reserved for the monitor's artifact recovery."
    )


def run_kernels_output_whitelist(
    notebook: str, download_dir: str, *, username: str | None = None
) -> int:
    """Whitelisted ``kernels output`` — the monitor's post-complete artifact pull.

    Deliberately the *only* place that runs ``kernels output``: the passthrough
    gate rejects every routine call, so artifact recovery has exactly one door.
    """
    os.makedirs(download_dir, exist_ok=True)
    username, token = (
        (username, identity.read_token(username))
        if username
        else identity.credentials()
    )
    proc = kaggle_exec.run_kaggle(
        ["kernels", "output", notebook, "-p", download_dir, "--force"],
        username=username,
        token=token,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


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


def print_push_preflight(meta: dict, push_dir: str) -> None:
    """Mandatory checklist printed on every push (agents cannot skip stdout)."""
    dataset_sources = meta.get("dataset_sources") or []
    print("\n" + "=" * 72)
    print("KAGGLE PUSH PREFLIGHT")
    print("=" * 72)
    print(f"  account (active):     {identity.bound_username() or '(unbound)'}")
    print(f"  title:                {meta.get('title', '')}")
    print(f"  dataset_sources ({len(dataset_sources)}):")
    for source in dataset_sources:
        print(f"    - {source}")
    print("  engine-payload:       prefer payload dataset VERSION over re-pushing notebook")
    print("  paths in notebook:    /kaggle/input/<slug>/...")
    required_gpu = meta.get("required_gpu", "T4")
    from src.config.config import gpu_interlock_enabled

    if not gpu_interlock_enabled():
        gpu_line = (
            f"interlock off -> API push sends enable_gpu="
            f"{meta_bool(meta.get('enable_gpu', False))}; Kaggle starts the run itself on its "
            f"default accelerator (probed: T4 x2); required_gpu={required_gpu}; no Run All owed"
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
    print("  after push:           browser opens by default; pass `--no-open` to suppress")
    print("=" * 72 + "\n")


def print_post_push_guidance(meta: dict, username: str, exit_code: int) -> tuple[str, str]:
    """Print slug + open + acceptance hints even when a GPU guard exits non-zero."""
    owner, short_id = meta["id"].split("/", 1)
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("[INFO] KAGGLE NOTEBOOK PUSH COMPLETED")
    else:
        print("[INFO] KAGGLE NOTEBOOK PUSH FINISHED (non-zero exit — may be GPU guard on a CPU session)")
        print("  This is often AWAITING_GPU_SELECTION, not a deploy failure. Still run notebook open.")
    print(f"  Account:                   {username}")
    print(f"  Pushed slug:               {short_id}")
    print(f"  Pushed complete id:        {meta['id']}")
    print(f"\n[AGENT NOTICE] agent -> run now: {identity.entry_hint()} notebook open {short_id}")
    print("\n[VERSION BUMP] Open tabs do NOT auto-refresh after push.")
    print(f"  Re-open: {identity.entry_hint()} notebook open {short_id}")
    from src.config.config import gpu_interlock_enabled

    if gpu_interlock_enabled():
        print("  Then: Settings -> GPU T4 x2 -> Run All from the first cell.")
    else:
        print("  No accelerator step: the push sent enable_gpu=true, so Kaggle runs it itself.")
        print(f"  Watch it with: {identity.entry_hint()} notebook monitor {short_id}")
    print("\nAcceptance (after the user runs all):")
    print(f"  Use `{identity.entry_hint()} notebook logs {short_id}` as auxiliary evidence,")
    print("  and confirm the pushed dataset_sources round-tripped via `kernels pull`.")
    print("=" * 80 + "\n")
    return owner, short_id


def require_push_target(value: str, what: str) -> str:
    """Reject a missing/placeholder field with INPUT_USAGE instead of pushing junk."""
    text = str(value or "").strip()
    if not text or "username/" in text or "dataset-slug" in text:
        raise identity.IdentityError(INPUT_USAGE, f"Invalid {what}: {value!r}")
    return text
