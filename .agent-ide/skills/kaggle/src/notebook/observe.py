"""Kernel observation: status parsing/classification plus logs and status.

Classification is deliberately forgiving: a run that trips the notebook's own
CPU-only guard, and a stale ERROR left by a previous CPU session, both look like
failures to the API while the training is actually fine. Only this layer knows
those shapes; the exec layer stays generic and merely retries/tolerates HTTP
statuses on request.

The GPU case is decided by the *push ledger*, never by the log text. ``kernels
push`` always sends ``enable_gpu=false`` (otherwise Kaggle auto-assigns the
legacy P100), so Kaggle immediately starts a CPU run that cannot succeed; the
operative session belongs to the human, who picks the accelerator and presses
Run All. ``requires_user_gpu=true`` in the ledger records exactly that contract,
so an API ERROR for such a notebook is expected by construction.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import os
import platform
import re
import subprocess
import sys
import time

from src import identity, kaggle_exec
from src.exit_codes import BLOCKED_BY_CONTRACT, KERNEL_FAILED, OK
from src.kaggle_exec import failure_output
from src.notebook import gates
from src.notebook.refs import resolve_notebook_args
from src.runtime.store import notebook_requires_user_gpu, runtime_path, update_notebook_state

STATUS_TOKENS = ("COMPLETE", "ERROR", "CANCELLED", "RUNNING", "QUEUED")

_PENDING_NOTE = (
    "Kernel is still registering on Kaggle's side (HTTP 404 while it starts). "
    "Re-run status in a moment if the state does not settle."
)


def _emit_kernel_log_chunk(chunk: str) -> None:
    """Print one raw log chunk, unwrapping the JSON log-event envelope."""
    chunk = chunk.strip()
    if not chunk:
        return
    if chunk.startswith("[") or chunk.startswith("{"):
        try:
            entries = json.loads(chunk) if chunk.startswith("[") else [json.loads(chunk)]
            for entry in entries:
                stream = entry.get("stream_name", "stdout")
                data = entry.get("data", "")
                prefix = "[stderr] " if stream == "stderr" else ""
                if data:
                    print(f"{prefix}{data}", end="" if data.endswith("\n") else "\n")
            return
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    print(chunk)



def _training_progress_in_logs(log_text: str) -> tuple[int, int] | None:
    matches = re.findall(r"Step (\d+)/(\d+)", log_text or "")
    if not matches:
        return None
    step, total = max((int(a), int(b)) for a, b in matches)
    return step, total


def _parse_api_kernel_status(raw_out: str) -> str:
    raw = raw_out or ""
    for token in STATUS_TOKENS:
        if token in raw:
            return token
    return "UNKNOWN"


def _classify_kernel_state(
    api_status: str, log_text: str, *, requires_user_gpu: bool = False
) -> tuple[str, str | None]:
    """Map raw API status + logs to an agent-facing status (no false failures).

    ``requires_user_gpu`` comes from the push ledger, not from ``log_text``: the
    ledger is what records that the notebook was pushed CPU-only on purpose and
    that a human is expected to drive the real session.
    """
    progress = _training_progress_in_logs(log_text)
    if progress:
        step, total = progress
        if api_status == "ERROR":
            return "RUNNING", (
                f"Training in progress (log shows step {step}/{total}). "
                "API status ERROR is stale from a prior CPU-only session — not a real failure."
            )
        if step < total:
            return "RUNNING", f"Training in progress: step {step}/{total}."
        if api_status == "COMPLETE":
            return "COMPLETE", f"Training finished at step {step}/{total}."

    if requires_user_gpu and api_status == "ERROR":
        return "AWAITING_GPU_SELECTION", (
            "Push ledger marks requires_user_gpu=true and the API reports ERROR. "
            "The API layer is pushed with enable_gpu=false (anti-P100), so Kaggle's own "
            "CPU-only auto-run failed; the operative session is the human's. "
            "Not a code failure."
        )
    return api_status, None


def _kernel_started_local(
    notebook: str, username: str, token: dict
) -> tuple[datetime.datetime | None, str | None]:
    """Start time of the newest run, localised, plus the raw API text.

    Kaggle prints ``lastRunTime`` in UTC and labels nothing. Reading it as local
    time is exactly how a 26-minute run becomes an "8-hour stall", so the
    timestamp is stamped UTC here and only then converted. Best effort: any
    failure returns ``(None, None)`` and the banner simply omits the clock.
    """
    proc = kaggle_exec.run_kaggle(
        ["kernels", "list", "-m", "--csv", "--page-size", "50"],
        username=username,
        token=token,
    )
    if proc.returncode != 0:
        return None, None
    # the CLI prints its "outdated version" warning on stdout, not stderr, so the
    # header row is not necessarily line 0
    lines = (proc.stdout or "").splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith("ref,")), None)
    if header is None:
        return None, None
    for row in csv.DictReader(io.StringIO("\n".join(lines[header:]))):
        if (row.get("ref") or "").strip() != notebook:
            continue
        raw = (row.get("lastRunTime") or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                utc = datetime.datetime.strptime(raw, fmt).replace(
                    tzinfo=datetime.timezone.utc
                )
            except ValueError:
                continue
            return utc.astimezone(), raw
    return None, None


def _print_run_clock(
    notebook: str, status: str, username: str | None, token: dict | None
) -> None:
    """``started <local> · running HH:MM`` — the clock the API does not give."""
    if not username or not token:
        return
    started, _raw = _kernel_started_local(notebook, username, token)
    if started is None:
        return
    offset = started.strftime("%z")
    zone = f"UTC{offset[:3]}:{offset[3:]}" if offset else "local"
    line = f"  started {started:%Y-%m-%d %H:%M:%S} {zone}"
    if status in {"RUNNING", "QUEUED", "AWAITING_GPU_SELECTION"}:
        now = datetime.datetime.now(datetime.timezone.utc)
        minutes = max(int((now - started).total_seconds() // 60), 0)
        line += f" · running {minutes // 60:02d}:{minutes % 60:02d}"
    print(line)


def _print_kernel_state_banner(
    notebook: str,
    status: str,
    note: str | None = None,
    *,
    username: str | None = None,
    token: dict | None = None,
) -> None:
    print(f'{notebook} has status "{status}"')
    _print_run_clock(notebook, status, username, token)
    if note:
        print(f"[INFO] {note}")
    if status == "AWAITING_GPU_SELECTION":
        print("\n" + "=" * 72)
        print("[ACTION REQUIRED] GPU selection — NOT a training/code failure.")
        print("  Decided by: push ledger requires_user_gpu=true (not the kernel log text).")
        print("  Human: Kaggle Settings → Accelerator → GPU T4 x2 → wait for restart → Run All")
        print("  Agent: do NOT treat KernelWorkerStatus.ERROR as failure in this case.")
        print("=" * 72)


def _kernel_logs_text(notebook: str, username: str, token: dict) -> str:
    """Best-effort log text for classification (never raises on a bad run)."""
    proc = kaggle_exec.run_kaggle(["kernels", "logs", notebook], username=username, token=token)
    return failure_output(proc)


def cmd_notebook_logs(args: argparse.Namespace) -> int:
    username, _slug, notebook = resolve_notebook_args(args.notebook)
    token = identity.read_token(username)
    run_args = ["kernels", "logs", notebook]
    if getattr(args, "follow", False):
        run_args.append("-f")

    proc = kaggle_exec.run_kaggle(run_args, username=username, token=token)
    if proc.stdout:
        _emit_kernel_log_chunk(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

    combined = failure_output(proc)
    if proc.returncode != 0 and "404" in combined:
        print(f"[INFO] {_PENDING_NOTE}", file=sys.stderr)
        return OK

    api_status = _parse_api_kernel_status(combined)
    status, note = _classify_kernel_state(
        api_status, combined, requires_user_gpu=notebook_requires_user_gpu(notebook)
    )
    if status in ("AWAITING_GPU_SELECTION", "RUNNING") and note:
        print(f"\n[INFO] Interpreted status: {status}")
        print(f"[INFO] {note}")
    if status == "AWAITING_GPU_SELECTION":
        _print_kernel_state_banner(notebook, status, note, username=username, token=token)
        return OK
    if status == "RUNNING" and api_status == "ERROR":
        return OK
    if proc.returncode != 0:
        kaggle_exec.classify_failure(run_args, proc, username)
    return OK


def cmd_notebook_status(args: argparse.Namespace) -> int:
    username, _slug, notebook = resolve_notebook_args(args.notebook)
    print(f"Checking status for {notebook} as {username}...")
    token = identity.read_token(username)

    run_args = ["kernels", "status", notebook]
    proc = kaggle_exec.run_kaggle_checked(
        run_args,
        username=username,
        token=token,
        retry_statuses=(404, 409),
        tolerate=(401, 404, 500),
    )
    raw_out = failure_output(proc)
    if proc.returncode != 0 and "401" in raw_out:
        print(
            "[INFO] Kaggle answered 401 to status while the logs are readable; "
            "reading the logs to classify the run instead.",
            file=sys.stderr,
        )
    if proc.returncode != 0 and "500" in raw_out:
        print(
            "[INFO] Kaggle answered 500 to status (known API flake); "
            "reading the logs to classify the run instead.",
            file=sys.stderr,
        )

    api_status = _parse_api_kernel_status(raw_out)
    if api_status == "UNKNOWN" and "404" in raw_out:
        api_status = "QUEUED"
        print(f"[INFO] {_PENDING_NOTE}")

    log_text = _kernel_logs_text(notebook, username, token)
    status, note = _classify_kernel_state(
        api_status, log_text, requires_user_gpu=notebook_requires_user_gpu(notebook)
    )

    update_notebook_state(username, notebook, status)
    _print_kernel_state_banner(notebook, status, note, username=username, token=token)
    return KERNEL_FAILED if status == "ERROR" else OK


_GPU_MONITOR_MSG = """\
[ERROR] notebook monitor is not supported for this GPU notebook ({notebook}).

The push ledger marks requires_user_gpu=true (a human must Run All in the browser).
Agent: stop monitoring; align status with the user through contact-user.
"""


def _extract_downloaded_zips(download_dir: str) -> None:
    import zipfile

    for name in os.listdir(download_dir):
        if not name.endswith(".zip"):
            continue
        zip_path = os.path.join(download_dir, name)
        print(f"[Monitor] Extracting {zip_path}...")
        try:
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(download_dir)
        except zipfile.BadZipFile as exc:
            print(f"[WARN] Could not extract {zip_path}: {exc}", file=sys.stderr)


def cmd_notebook_monitor(args: argparse.Namespace) -> int:
    """Poll status (5s running / 10s idle) while streaming ``logs -f``; pull artifacts after COMPLETE."""
    username, slug, notebook = resolve_notebook_args(args.notebook)
    if notebook_requires_user_gpu(notebook):
        print(_GPU_MONITOR_MSG.format(notebook=notebook), file=sys.stderr)
        return BLOCKED_BY_CONTRACT

    download_dir = getattr(args, "download_dir", None) or runtime_path(
        "output", slug.replace("/", "_")
    )
    print(f"Monitoring execution for {notebook} as {username}...")

    token = identity.read_token(username)
    env = kaggle_exec.kaggle_env(username, token)
    binary = kaggle_exec.kaggle_binary()

    logs_proc = None
    if not getattr(args, "no_logs", False):
        print("[Monitor] Streaming live logs (kernels logs -f)...")
        logs_proc = subprocess.Popen(
            [binary, "kernels", "logs", notebook, "-f"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
        )

    started = False
    try:
        while True:
            if logs_proc and logs_proc.stdout:
                if platform.system() == "Windows":
                    line = logs_proc.stdout.readline()
                    if line:
                        _emit_kernel_log_chunk(line)
                else:
                    import select

                    ready, _, _ = select.select([logs_proc.stdout], [], [], 0.5)
                    if ready:
                        line = logs_proc.stdout.readline()
                        if line:
                            _emit_kernel_log_chunk(line)

            proc = kaggle_exec.run_kaggle(
                ["kernels", "status", notebook], username=username, token=token
            )
            raw = failure_output(proc)
            api_status = _parse_api_kernel_status(raw)

            if api_status in ("RUNNING", "QUEUED"):
                if not started:
                    print("[Monitor] Detected execution running.")
                    started = True
            elif api_status == "COMPLETE":
                print("[Monitor] Execution completed successfully!")
                update_notebook_state(username, notebook, "COMPLETE")
                break
            elif api_status == "ERROR" and started:
                print("[Monitor] Execution failed or was cancelled.")
                update_notebook_state(username, notebook, "ERROR")
                return KERNEL_FAILED
            elif api_status == "ERROR" and not started:
                status, note = _classify_kernel_state(
                    api_status,
                    _kernel_logs_text(notebook, username, token),
                    requires_user_gpu=notebook_requires_user_gpu(notebook),
                )
                if status == "AWAITING_GPU_SELECTION":
                    print(f"[{time.strftime('%H:%M:%S')}] {status}: waiting for human GPU selection...")
                    if note:
                        print(f"[INFO] {note}")
                elif status == "RUNNING":
                    print("[Monitor] Detected training via logs (API status stale ERROR).")
                    started = True
                    if note:
                        print(f"[INFO] {note}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Status: {raw.strip()} ... waiting...")
            elif not started:
                print(f"[{time.strftime('%H:%M:%S')}] Status: {raw.strip()} ... waiting...")

            time.sleep(5 if started else 10)
    finally:
        if logs_proc:
            logs_proc.terminate()
            try:
                logs_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logs_proc.kill()

    print(f"[Monitor] Downloading outputs to {download_dir}...")
    gates.run_kernels_output_whitelist(notebook, download_dir, username=username)
    _extract_downloaded_zips(download_dir)
    return OK


def register_observe(verbs) -> None:
    status = verbs.add_parser("status", help="kernel status, classified into a real run state")
    status.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")

    logs = verbs.add_parser("logs", help="print the kernel log")
    logs.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    logs.add_argument("-f", "--follow", action="store_true", help="follow until the run ends")

    monitor = verbs.add_parser(
        "monitor",
        help="poll status + stream logs, then download artifacts (blocked for GPU ledger notebooks)",
    )
    monitor.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    monitor.add_argument(
        "-d",
        "--download-dir",
        metavar="<dir>",
        help="artifact destination (default: data/agents/<id>/runtime/output/<slug>)",
    )
    monitor.add_argument("--no-logs", action="store_true", help="disable live log streaming")
