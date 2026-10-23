"""What the push prints when it is over: slug, who does what next, how to accept it.

Kept apart from the checks because this text is read by a human afterwards, and
because the two modes owe that human completely different next steps.
"""
from __future__ import annotations

from src import identity


def print_post_push_guidance(meta: dict, username: str, exit_code: int, mode) -> tuple[str, str]:
    """Print slug + how to watch it + acceptance hints, whatever the push exited with."""
    owner, short_id = meta["id"].split("/", 1)
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("[INFO] KAGGLE NOTEBOOK PUSH COMPLETED")
    else:
        print("[INFO] KAGGLE NOTEBOOK PUSH FINISHED (non-zero exit — may be GPU guard on a CPU session)")
        print("  This is often AWAITING_GPU_SELECTION, not a deploy failure. Still run notebook open.")
    print(f"  Mode:                      {mode.name}")
    print(f"  Account:                   {username}")
    print(f"  Pushed slug:               {short_id}")
    print(f"  Pushed complete id:        {meta['id']}")
    if mode.requires_run_all:
        print(f"\n[AGENT NOTICE] agent -> tell the user: {identity.entry_hint()} notebook open {short_id}")
        print("\n[HUMAN STEP] Settings -> GPU T4 x2 -> Run All from the first cell.")
        print("  Nothing runs until that happens; polling the ledger before it is pointless.")
    else:
        print(f"\n[AGENT NOTICE] agent -> run now: {identity.entry_hint()} notebook monitor {short_id}")
        print("\n[NO HUMAN STEP] Kaggle already started this run on the accelerator it picked.")
        print("  Do not open the editor to press Run All - that would restart a live session.")
        print(f"  Watch it with: {identity.entry_hint()} notebook monitor {short_id}")
        print("  Logs stay empty for several minutes (queue, dataset mount, pip install);")
        print("  an empty log right now is not a failure. Do not re-push to 'fix' it.")
    print("\nAcceptance (after the run finishes):")
    print(f"  Use `{identity.entry_hint()} notebook logs {short_id}` as auxiliary evidence,")
    print("  and confirm the pushed dataset_sources round-tripped via `kernels pull`.")
    print("=" * 80 + "\n")
    return owner, short_id
