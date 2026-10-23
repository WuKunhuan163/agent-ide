"""``kernel-metadata.json``: read it, default it, resolve placeholders, hand the API copy over.

Nothing here talks to Kaggle. The push pipeline and the API layer both need a
metadata dict, and they need it shaped differently - which is why shaping lives
here, next to the file format, instead of inside the deploy flow.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime

from src.exit_codes import INPUT_USAGE
from src.notebook.preflight import require_push_target


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
        require_push_target(source, "dataset_sources entry")

    title = meta.get("title", "")
    if len(title) < 5:
        raise identity.IdentityError(
            INPUT_USAGE, f"title '{title}' must be at least 5 characters."
        )

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
