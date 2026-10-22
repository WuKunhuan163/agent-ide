"""Execution layer: run the kaggle CLI in a per-account env, classify failures.

Retries are opt-in per exit status and only cover genuinely transient ones by
default (409 Conflict while a resource is still settling). Kernel-state quirks
(404 while a kernel is still registering, the `kernels status` 500 bug) stay in
the notebook observation layer, which asks for them through ``retry_statuses``
and ``tolerate`` so the raw process is handed back instead of raised on.
"""
from __future__ import annotations
import os, shutil, subprocess, sys, time
from src import identity
from src.exit_codes import (
    AUTH_REJECTED, EXEC_CLI_MISSING, EXEC_FAILED, EXEC_TIMEOUT, QUOTA_EXCEEDED,
)

AUTH_MARKER =  "Authentication required to call the Kaggle API."
PROBE_ARGS = ["competitions", "list", "--page-size", "1"]
RETRY_STATUSES = (409,)
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5.0

def kaggle_env(username: str, token: dict) -> dict: 
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = os.path.dirname(identity.token_path(username))
    env["KAGGLE_USERNAME"] = str(token.get("username", username))
    env["KAGGLE_KEY"] = str(token.get("key", ""))
    return env

def kaggle_binary() -> str:
    """Absolute path of the ``kaggle`` executable, or raise EXEC_CLI_MISSING.

    Also the entry point for callers that need a raw ``Popen`` (the monitor
    streams ``kernels logs -f`` and cannot use the blocking ``run_kaggle``).
    """
    binary = shutil.which("kaggle")
    if binary is None:
        raise identity.IdentityError(
            EXEC_CLI_MISSING, "kaggle CLI not found in PATH"
        )
    return binary


def run_kaggle(
    args: list[str], *, username: str, token: dict, timeout: float | None = None
) -> subprocess.CompletedProcess: 
    binary = kaggle_binary()
    try: 
        return subprocess.run(
            [binary, *args], 
            env=kaggle_env(username, token), 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired: 
        raise identity.IdentityError(
            EXEC_TIMEOUT, f"kaggle {' '.join(args)} timed out after {timeout}s"
        ) from None


def failure_output(proc: subprocess.CompletedProcess) -> str:
    """Child stdout+stderr as one stripped blob (for classification and messages)."""
    return f"{proc.stdout}\n{proc.stderr}".strip()


def _is_quota_failure(output: str) -> bool:
    lowered = output.lower()
    return "quota" in lowered and "exceeded" in lowered


def _status_hits(proc: subprocess.CompletedProcess, statuses: tuple[int, ...]) -> bool:
    """True when the run carries one of these HTTP statuses.

    The CLI reports API statuses as text ("409 Conflict", "404 - Not Found") and
    only rarely as its own exit code (POSIX caps those at 255), so both are read.
    """
    if not statuses:
        return False
    if proc.returncode in statuses:
        return True
    output = failure_output(proc)
    return any(str(status) in output for status in statuses)


def classify_failure(args: list[str], proc: subprocess.CompletedProcess, username: str) -> None:
    """Turn a non-zero kaggle run into the right IdentityError; never returns."""
    output = failure_output(proc)
    if AUTH_MARKER in output:
        raise identity.IdentityError(
            AUTH_REJECTED, identity.auth_rejected_message(username, output)
        )
    if _is_quota_failure(output):
        raise identity.IdentityError(
            QUOTA_EXCEEDED,
            f"Kaggle quota exceeded for '{username}':\n{output}\n"
            "  Wait for the quota window to reset, or lower the notebook's runtime "
            "(GPU hours and dataset size both count).",
        )
    raise identity.IdentityError(
        EXEC_FAILED,
        f"kaggle {' '.join(args)} failed with exit {proc.returncode}:\n{output}",
    )


def run_kaggle_checked(
    args: list[str],
    *,
    username: str | None = None,
    token: dict | None = None,
    timeout: float | None = None,
    retry_statuses: tuple[int, ...] = RETRY_STATUSES,
    tolerate: tuple[int, ...] = (),
    attempts: int = RETRY_ATTEMPTS,
    delay: float = RETRY_DELAY,
) -> subprocess.CompletedProcess:
    """Run kaggle and raise on failure instead of returning a bad process.

    Credentials resolve lazily (identity.credentials) unless the caller already
    holds them, so read-only commands stay one-liners while a caller that already
    resolved an account can pin it explicitly.

    ``retry_statuses`` are retried up to ``attempts`` times with ``delay`` seconds
    in between; ``tolerate`` statuses are returned as-is so a caller can add its
    own meaning (e.g. 404 -> "still queued"). Classification on the final
    attempt: ``AUTH_MARKER`` in the output -> AUTH_REJECTED; a quota blow-up ->
    QUOTA_EXCEEDED; any other non-zero exit -> EXEC_FAILED carrying the output.
    """
    if username is None or token is None:
        username, token = identity.credentials()
    attempt = 1
    while True:
        proc = run_kaggle(args, username=username, token=token, timeout=timeout)
        if proc.returncode == 0:
            return proc
        if attempt < attempts and _status_hits(proc, retry_statuses):
            print(
                f"[kaggle] {' '.join(args)} -> transient failure; "
                f"retry {attempt + 1}/{attempts} in {delay:g}s",
                file=sys.stderr,
            )
            time.sleep(delay)
            attempt += 1
            continue
        if _status_hits(proc, tolerate):
            return proc
        classify_failure(args, proc, username)
        raise AssertionError("classify_failure must raise")


def verify_credentials(username: str, token: dict) -> None:
    """Cheap probe: raise AUTH_REJECTED when the API refuses these credentials."""
    run_kaggle_checked(PROBE_ARGS, username=username, token=token)
