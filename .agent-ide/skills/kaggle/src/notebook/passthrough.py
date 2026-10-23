"""The two passthrough contracts.

Anything the router does not own is handed to the official ``kaggle`` CLI. Two
verbs must not go through untouched: ``kernels push`` (it would skip the deploy
pipeline) and ``kernels output`` (reserved for ``monitor``'s artifact recovery).
"""
from __future__ import annotations

import os
import sys

from src import identity, kaggle_exec
from src.exit_codes import BLOCKED_BY_CONTRACT


OUTPUT_ALLOW_ENV = "KAGGLE_ALLOW_OUTPUT"
OUTPUT_ALLOW_FLAG = "--allow-output"

# Not a whitelist: the only passthrough verb that must never run is `kernels push`,
# because it would skip the deploy pipeline that lives in `notebook push`.
FORBIDDEN_PASSTHROUGH: dict[str, frozenset[str]] = {
    "kernels": frozenset({"push"}),
}

def _block(argv: list[str], reason: str) -> None:
    print("\n" + "=" * 72, file=sys.stderr)
    print(f"[BLOCKED] passthrough not allowed: {' '.join(argv[:3])}", file=sys.stderr)
    print(f"  Reason: {reason}", file=sys.stderr)
    print(f"  Push:   {identity.entry_hint()} notebook push <dir>", file=sys.stderr)
    print(f"  Edit:   {identity.entry_hint()} notebook edit <slug> '<json>'", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    raise identity.IdentityError(BLOCKED_BY_CONTRACT, reason)

def enforce_passthrough_contract(argv: list[str]) -> list[str]:
    """Refuse only the named contract violation; hand everything else to the official CLI."""
    verb = argv[0]
    sub = argv[1] if len(argv) > 1 else ""
    if sub in FORBIDDEN_PASSTHROUGH.get(verb, frozenset()):
        _block(argv, "kernels push is forbidden — use notebook push (it runs the push gates)")
    return argv

def guard_kernels_output_passthrough(argv: list[str]) -> list[str]:
    """Block routine ``kernels output``; notebook acceptance is logs-only."""
    if len(argv) < 3 or argv[0] != "kernels" or argv[1] != "output":
        return argv
    if os.environ.get(OUTPUT_ALLOW_ENV) == "1" or OUTPUT_ALLOW_FLAG in argv:
        return [arg for arg in argv if arg != OUTPUT_ALLOW_FLAG]
    print("\n" + "=" * 72, file=sys.stderr)
    print("[BLOCKED] kernels output — notebook acceptance is logs-only", file=sys.stderr)
    print(f"  Use:  {identity.entry_hint()} notebook status <slug>", file=sys.stderr)
    print(f"  Use:  {identity.entry_hint()} notebook logs <slug>", file=sys.stderr)
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
    username, token = identity.credentials_for(username)
    proc = kaggle_exec.run_kaggle(
        ["kernels", "output", notebook, "-p", download_dir, "--force"],
        username=username,
        token=token,
    )
    kaggle_exec.forward_output(proc)
    return proc.returncode
