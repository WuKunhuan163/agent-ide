"""``notebook push``: the single deploy pipeline (metadata -> GPU protocol -> ledger).

One path serves both a first push and a hotfix bump:

    preflight -> placeholder injection -> GPU assertion -> API push (enable_gpu=false)
    -> verify dataset_sources round-trip -> ledger/event log -> optional monitor/open (open is default)

Placeholders (``<NOTEBOOK_HASH>`` / ``<KAGGLE_USERNAME>`` / ``<BUILD_TS>``) are
resolved here and must not survive into the pushed code. The GPU protocol keeps
``enable_gpu`` on the authoring metadata (so the human can pick T4 x2 in the
browser) while the *API* layer is always pushed with ``enable_gpu=false`` to stop
Kaggle auto-assigning the legacy P100.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime

from src import identity, kaggle_exec
from src.dataset.cmds import sync_local_dataset
from src.exit_codes import INPUT_USAGE, OK, PUSH_FAILED
from src.notebook import gates, refs
from src.notebook.gates import meta_bool
from src.notebook.observe import cmd_notebook_monitor
from src.runtime.store import log_event, update_notebook_state

NOTEBOOK_HASH_PLACEHOLDER = "<NOTEBOOK_HASH>"
KAGGLE_USER_PLACEHOLDER = "<KAGGLE_USERNAME>"
BUILD_TS_PLACEHOLDER = "<BUILD_TS>"
ALL_PUSH_PLACEHOLDERS = (
    NOTEBOOK_HASH_PLACEHOLDER,
    KAGGLE_USER_PLACEHOLDER,
    BUILD_TS_PLACEHOLDER,
)
_HASH_SUFFIX_RE = re.compile(r"-[0-9a-f]{6}$")

DEFAULT_META = {
    "language": "python",
    "is_private": True,
    "enable_gpu": False,
    "enable_tpu": False,
    "dataset_sources": [],
    "competition_sources": [],
    "kernel_sources": [],
}


# --------------------------------------------------------------------------- #
# metadata                                                                    #
# --------------------------------------------------------------------------- #
def _write_meta(meta_path: str, meta: dict) -> None:
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.flush()
        os.fsync(f.fileno())


def _load_meta(push_dir: str) -> dict:
    meta_path = os.path.join(push_dir, "kernel-metadata.json")
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        raise identity.IdentityError(
            INPUT_USAGE,
            f"kernel-metadata.json not found or invalid in {push_dir}",
        ) from None


def _apply_meta_defaults(meta: dict, push_dir: str, meta_path: str) -> dict:
    """Backfill the defaults the official CLI would otherwise reject."""
    for key, value in DEFAULT_META.items():
        meta.setdefault(key, value)

    if "code_file" not in meta:
        files = os.listdir(push_dir)
        if "main.ipynb" in files:
            meta["code_file"] = "main.ipynb"
            meta["kernel_type"] = "notebook"
        elif "main.py" in files:
            meta["code_file"] = "main.py"
            meta["kernel_type"] = "script"
        else:
            raise identity.IdentityError(
                INPUT_USAGE, f"No main.ipynb/main.py found in {push_dir}"
            )
        _write_meta(meta_path, meta)
    return meta


def _validate_push_meta(meta: dict, push_dir: str) -> None:
    code_path = os.path.join(push_dir, meta.get("code_file", ""))
    if not os.path.exists(code_path):
        raise identity.IdentityError(
            INPUT_USAGE,
            f"code file '{meta.get('code_file')}' not found in {push_dir}",
        )

    if meta.get("kernel_type") == "notebook":
        try:
            with open(code_path, encoding="utf-8") as f:
                json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise identity.IdentityError(
                INPUT_USAGE, f"{code_path} is not valid .ipynb JSON ({exc})"
            ) from None

    for source in meta.get("dataset_sources", []):
        gates.require_push_target(source, "dataset_sources entry")

    title = meta.get("title", "")
    if len(title) < 5:
        raise identity.IdentityError(
            INPUT_USAGE, f"title '{title}' must be at least 5 characters."
        )


# --------------------------------------------------------------------------- #
# placeholders                                                                #
# --------------------------------------------------------------------------- #
def _replace_push_placeholders(
    text: str, *, push_hash: str | None, username: str, build_ts: str, replace_hash: bool = True
) -> str:
    if not text:
        return text
    out = text
    if replace_hash and push_hash:
        out = out.replace(NOTEBOOK_HASH_PLACEHOLDER, push_hash)
    out = out.replace(KAGGLE_USER_PLACEHOLDER, username)
    out = out.replace(BUILD_TS_PLACEHOLDER, build_ts)
    # legacy build.py token (pre-2026-08-21)
    out = out.replace("__BUILD_TS__", build_ts)
    return out


def _validate_no_unresolved_placeholders(text: str, context: str) -> None:
    leftovers = [p for p in ALL_PUSH_PLACEHOLDERS if p in text]
    if leftovers:
        raise identity.IdentityError(
            INPUT_USAGE,
            f"Unresolved placeholders in {context}: {leftovers}\n"
            "  Push resolves <NOTEBOOK_HASH>, <KAGGLE_USERNAME>, <BUILD_TS> automatically.",
        )


def _notebook_needs_input_dataset(push_dir: str, meta: dict) -> bool:
    code_file = meta.get("code_file", "")
    if not code_file:
        return False
    path = os.path.join(push_dir, code_file)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            return "/kaggle/input" in f.read()
    except OSError:
        return False


def apply_push_placeholders(meta: dict, push_dir: str, username: str, *, skip_hash: bool = False) -> str | None:
    """Resolve the three placeholders in metadata + code file; return the push hash."""
    build_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    push_hash = None if skip_hash else uuid.uuid4().hex[:6]

    if push_hash:
        title = meta.get("title") or "notebook"
        base = _HASH_SUFFIX_RE.sub("", title)
        meta["title"] = f"{base}-{push_hash}"
        print(f"[INFO] Auto push hash: {push_hash} -> title: {meta['title']}")
    else:
        print(
            "[WARN] --no-hash: slug will NOT change; a rerun hits the SAME notebook. "
            "Deploy with the default hash unless you are probing."
        )

    hash_for_cells = push_hash or ""
    replace_hash = bool(push_hash)
    if not push_hash:
        match = _HASH_SUFFIX_RE.search(meta.get("title") or "")
        if match:
            hash_for_cells = match.group(0)[1:]

    for key in ("dataset_sources", "kernel_sources", "competition_sources"):
        items = meta.get(key)
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if isinstance(item, str):
                items[i] = _replace_push_placeholders(
                    item,
                    push_hash=hash_for_cells,
                    username=username,
                    build_ts=build_ts,
                    replace_hash=replace_hash,
                )

    code_file = meta.get("code_file", "")
    code_path = os.path.join(push_dir, code_file)
    if not os.path.isfile(code_path):
        return push_hash

    if meta.get("kernel_type", "notebook") == "notebook":
        with open(code_path, encoding="utf-8") as f:
            notebook = json.load(f)
        for cell in notebook.get("cells", []):
            cell["source"] = [
                _replace_push_placeholders(
                    line,
                    push_hash=hash_for_cells,
                    username=username,
                    build_ts=build_ts,
                    replace_hash=replace_hash,
                )
                for line in cell.get("source", [])
            ]
        notebook_text = json.dumps(notebook, ensure_ascii=False)
        if push_hash and NOTEBOOK_HASH_PLACEHOLDER in notebook_text:
            first = (notebook.get("cells") or [{}])[0]
            if first.get("cell_type") == "code":
                prefix = f'NOTEBOOK_HASH = "{push_hash}"  # auto-injected by kaggle push\n'
                if "NOTEBOOK_HASH" not in "".join(first.get("source", [])):
                    first["source"] = [prefix] + first.get("source", [])
        with open(code_path, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
        with open(code_path, encoding="utf-8") as f:
            _validate_no_unresolved_placeholders(f.read(), code_path)
    else:
        with open(code_path, encoding="utf-8") as f:
            content = f.read()
        content = _replace_push_placeholders(
            content,
            push_hash=hash_for_cells,
            username=username,
            build_ts=build_ts,
            replace_hash=replace_hash,
        )
        if push_hash and NOTEBOOK_HASH_PLACEHOLDER in content:
            content = f'# NOTEBOOK_HASH="{push_hash}"  # auto-injected by kaggle push\n' + content
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(content)
        _validate_no_unresolved_placeholders(content, code_path)

    return push_hash


# --------------------------------------------------------------------------- #
# GPU protocol                                                                #
# --------------------------------------------------------------------------- #
def inject_gpu_assertion(meta: dict, push_dir: str) -> tuple[dict, bool]:
    """Inject the GPU CHECK cell when authoring ``enable_gpu``; return (meta, enabled).

    The injected text only speaks to the human reading the Kaggle log. Whether an
    API ERROR means "waiting for the human" is decided by the ledger the caller
    writes (``requires_user_gpu``), never by this prose.
    """
    code_path = os.path.join(push_dir, meta.get("code_file", ""))
    required_gpu = meta.get("required_gpu", "T4")
    accelerator = "GPU T4 x2" if required_gpu == "T4" else f"GPU {required_gpu}"
    enable_gpu_authoring = meta_bool(meta.get("enable_gpu", False))

    if os.path.exists(code_path):
        try:
            assert_code = (
                "# === CRITICAL GPU CHECK ===\n"
                "import torch\n"
                "assert torch.cuda.is_available(), (\n"
                "    \"[gpu_check] FAIL cuda=unavailable"
                f" expected={required_gpu}\\n\"\n"
                f"    \"  fix: Settings -> Accelerator -> '{accelerator}'"
                " -> wait for restart -> Run All\"\n"
                ")\n"
                "gpu_name = torch.cuda.get_device_name(0)\n"
                "assert \""
                f"{required_gpu}"
                "\" in gpu_name, (\n"
                "    f\"[gpu_check] FAIL gpu={gpu_name}"
                f" expected={required_gpu}\\n\"\n"
                f"    \"  fix: Settings -> Accelerator -> '{accelerator}' -> Run All\"\n"
                ")\n"
                "print(f\"[gpu_check] ok gpu={gpu_name} n_gpu={torch.cuda.device_count()}\")\n"
                "# ==========================\n"
            )
            if meta.get("kernel_type") == "notebook":
                with open(code_path, encoding="utf-8") as f:
                    notebook = json.load(f)
                has_assert = any(
                    "CRITICAL GPU CHECK" in "".join(cell.get("source", []))
                    for cell in notebook.get("cells", [])
                )
                if enable_gpu_authoring and not has_assert:
                    print(f"[INFO] Auto-injecting GPU assertion cell into {meta.get('code_file')}")
                    notebook.setdefault("cells", []).insert(
                        0,
                        {
                            # nbformat>=5.5 requires every cell to carry an id.
                            "id": "gpu_check",
                            "cell_type": "code",
                            "execution_count": None,
                            "metadata": {},
                            "outputs": [],
                            "source": assert_code.splitlines(keepends=True),
                        },
                    )
                with open(code_path, "w", encoding="utf-8") as f:
                    json.dump(notebook, f, indent=2)
            else:
                with open(code_path, encoding="utf-8") as f:
                    script = f.read()
                if enable_gpu_authoring and "CRITICAL GPU CHECK" not in script:
                    print(f"[INFO] Auto-injecting GPU assertion header into {meta.get('code_file')}")
                    with open(code_path, "w", encoding="utf-8") as f:
                        f.write(assert_code + "\n" + script)
            if enable_gpu_authoring:
                print(
                    "[INFO] Authoring enable_gpu=true -> GPU CHECK injected; "
                    "API push uses transient enable_gpu=false (authoring metadata preserved on disk)."
                )
        except Exception as exc:  # injection is best-effort; the push still matters
            print(f"[WARNING] Failed to auto-inject GPU assertion: {exc}")

    authoring_meta = dict(meta)
    if enable_gpu_authoring:
        authoring_meta["enable_gpu"] = True
    return authoring_meta, enable_gpu_authoring


def api_push_meta(authoring_meta: dict, *, interlock: bool = True) -> dict:
    """Transient API metadata for the push itself.

    Interlock on: force ``enable_gpu=false`` so Kaggle cannot auto-assign the legacy P100, and
    the human picks the accelerator before Run All. Interlock off: send ``enable_gpu`` exactly as
    authored, so Kaggle starts the run itself on its default accelerator.
    """
    api_meta = dict(authoring_meta)
    api_meta["enable_gpu"] = False if interlock else bool(authoring_meta.get("enable_gpu"))
    api_meta["enable_tpu"] = False
    for key in ("accelerator", "gpu_type", "accelerator_name"):
        api_meta.pop(key, None)
    return api_meta


def push_with_gpu_protocol(
    push_dir: str, authoring_meta: dict, *, username: str, push_label: str
) -> int:
    """Write transient API metadata, ``kernels push``, restore authoring metadata."""
    meta_path = os.path.join(push_dir, "kernel-metadata.json")
    from src.config.config import gpu_interlock_enabled

    interlock = gpu_interlock_enabled()
    if interlock:
        print(
            "[INFO] API push layer: enable_gpu=false enable_tpu=false "
            f"(anti-P100; authoring enable_gpu={authoring_meta.get('enable_gpu')})"
        )
    else:
        print(
            "[INFO] GPU interlock off: API push layer sends "
            f"enable_gpu={bool(authoring_meta.get('enable_gpu'))} — Kaggle starts the run "
            "itself, no accelerator selection and no Run All"
        )
    _write_meta(meta_path, api_push_meta(authoring_meta, interlock=interlock))
    try:
        proc = kaggle_exec.run_kaggle(
            ["kernels", "push", "-p", push_dir],
            username=username,
            token=identity.read_token(username),
        )
        kaggle_exec.forward_output(proc)
        return proc.returncode
    finally:
        _write_meta(meta_path, authoring_meta)


# --------------------------------------------------------------------------- #
# pipeline                                                                    #
# --------------------------------------------------------------------------- #
def _verify_pushed_dataset_sources(
    meta: dict, username: str, pushed: list[str]
) -> None:
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
    """Preflight -> GPU push -> ledger -> optional monitor/open (open by default). Returns the exit code."""
    from src.notebook.cmds import cmd_notebook_open  # local: avoids an import cycle

    push_dir = os.path.abspath(push_dir)
    meta_path = os.path.join(push_dir, "kernel-metadata.json")
    meta = _load_meta(push_dir)
    meta = _apply_meta_defaults(meta, push_dir, meta_path)

    if local_dataset:
        for folder in local_dataset:
            if not os.path.isdir(folder):
                raise identity.IdentityError(INPUT_USAGE, f"Not a folder: {folder}")
            full_slug = sync_local_dataset(folder, username, identity.read_token(username))
            if full_slug not in meta["dataset_sources"]:
                meta["dataset_sources"].append(full_slug)

    for dataset in remote_dataset or []:
        if dataset not in meta["dataset_sources"]:
            meta["dataset_sources"].append(dataset)

    if apply_placeholders:
        apply_push_placeholders(meta, push_dir, username, skip_hash=no_hash)

    if assign_id:
        title = meta.get("title", "")
        if not title:
            raise identity.IdentityError(INPUT_USAGE, "'title' is required in kernel-metadata.json")
        meta["id"] = f"{username}/{refs.slugify(title)}"
        print(f"[INFO] Auto-generated missing id: {meta['id']}")

    _write_meta(meta_path, meta)

    authoring_meta, gpu_authoring = inject_gpu_assertion(meta, push_dir)
    _validate_push_meta(authoring_meta, push_dir)

    gates.print_push_preflight(authoring_meta, push_dir)
    if _notebook_needs_input_dataset(push_dir, authoring_meta) and not authoring_meta.get("dataset_sources"):
        if not force_push:
            raise identity.IdentityError(
                INPUT_USAGE,
                "Notebook references /kaggle/input but dataset_sources is empty. "
                "Add datasets / --remote-dataset, or override with --force-push.",
            )
        print("[PREFLIGHT] dataset_sources empty but --force-push given; continuing.", file=sys.stderr)

    if not gates.check_and_reject_push(username, meta_path, force=force_push):
        raise identity.IdentityError(
            PUSH_FAILED, f"{meta.get('id')} is already RUNNING in the state ledger; pass --force-push."
        )

    print(f"[INFO] Pushing and executing notebook from {push_dir}...")
    exit_code = push_with_gpu_protocol(
        push_dir, authoring_meta, username=username, push_label=push_label
    )

    if exit_code == 0 and authoring_meta.get("dataset_sources"):
        _verify_pushed_dataset_sources(authoring_meta, username, list(authoring_meta["dataset_sources"]))

    notebook_id = meta.get("id")
    if not notebook_id:
        return exit_code

    owner, short_id = gates.print_post_push_guidance(authoring_meta, username, exit_code)
    update_notebook_state(
        username,
        notebook_id,
        "RUNNING" if exit_code == 0 else f"PUSH_EXIT_{exit_code}",
        requires_user_gpu=gpu_authoring,
    )
    log_event(username, "PUSH_NOTEBOOK", notebook_id)

    if exit_code == 0 and auto_download:
        if gpu_authoring:
            print(
                "\n[WARN] --auto-download skipped: a GPU notebook needs a human Run All. "
                "Align status with the user instead.",
                file=sys.stderr,
            )
        else:
            print("\n[INFO] --auto-download: switching to monitor mode...")
            monitor_args = argparse.Namespace(
                notebook=notebook_id, download_dir=auto_download, no_logs=False
            )
            monitor_code = cmd_notebook_monitor(monitor_args)
            if monitor_code != OK:
                return monitor_code

    if exit_code == 0 and open_after:
        open_code = cmd_notebook_open(
            argparse.Namespace(notebook=f"{owner}/{short_id}")
        )
        if open_code != OK:
            print(
                f"\n[WARN] Post-push notebook open failed for {owner}/{short_id} "
                f"(exit {open_code}); the push itself succeeded — open it manually.",
                file=sys.stderr,
            )

    _write_meta(meta_path, authoring_meta)
    return exit_code


# --------------------------------------------------------------------------- #
# command                                                                     #
# --------------------------------------------------------------------------- #
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
        help="CPU notebooks only: wait for completion and download (skipped for GPU ledger entries)",
    )
    push.add_argument(
        "--no-open",
        action="store_true",
        help="skip opening the browser after a successful push (default: open it)",
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
        os.path.abspath(args.dir),
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
