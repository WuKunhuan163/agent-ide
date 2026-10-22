"""``notebook pull`` / ``notebook edit``: fetch, patch and re-push a kernel.

Every pull lands in its own timestamped folder under ``notebooks_dir`` unless the
caller pins ``-d/--dir``, so a pull never overwrites a previous snapshot and the
``edit`` verb can diff and re-push exactly what was fetched. ``edit`` keeps the
same slug (``assign_id=False``, ``no_hash=True``) and always forces past the
duplicate-RUNNING gate, because a hotfix is precisely a version bump.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import uuid
from datetime import datetime

from src import identity, kaggle_exec
from src.exit_codes import INPUT_USAGE, OK
from src.notebook.refs import resolve_notebook_args
from src.paths import require_ctx

def _pull_dir(slug: str, dir_arg: str | None) -> str:
    """Fresh ``<slug>-<stamp>-<hex8>`` folder, or the caller's pinned directory."""
    if dir_arg:
        return os.path.abspath(dir_arg)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(
        require_ctx().notebooks_dir, f"{slug}-{stamp}-{uuid.uuid4().hex[:8]}"
    )


def _pull_notebook(notebook: str, out_dir: str, username: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    kaggle_exec.run_kaggle_checked(
        ["kernels", "pull", notebook, "-p", out_dir, "-m"],
        username=username,
        token=identity.read_token(username),
    )


def _find_code_file(out_dir: str) -> str | None:
    """Source file in a pulled folder, preferring .ipynb then .py."""
    names = os.listdir(out_dir)
    for suffix in (".ipynb", ".py"):
        for name in names:
            if name.endswith(suffix) and name != "kernel-metadata.json":
                return name
    return None


def cmd_notebook_pull(args: argparse.Namespace) -> int:
    username, slug, notebook = resolve_notebook_args(args.notebook)
    out_dir = _pull_dir(slug, getattr(args, "dir", None))

    print(f"Pulling notebook {notebook} into {out_dir} as {username}...")
    _pull_notebook(notebook, out_dir, username)
    print(f"[OK] Pulled {notebook} -> {out_dir}")
    return OK


def cmd_notebook_edit(args: argparse.Namespace) -> int:
    """pull -> string/cell patch -> diff -> re-push the same slug."""
    from src.notebook.push import run_deploy_push  # local: avoids an import cycle

    username, slug, notebook = resolve_notebook_args(args.notebook)
    out_dir = _pull_dir(slug, None)

    try:
        replacements = json.loads(args.replacements)
        if not isinstance(replacements, list):
            raise ValueError("replacements must be a JSON array of [old, new] pairs")
    except (json.JSONDecodeError, ValueError) as exc:
        raise identity.IdentityError(INPUT_USAGE, f"Bad --replacements JSON: {exc}") from None

    print(f"[INFO] Pulling notebook {notebook} into {out_dir}...")
    _pull_notebook(notebook, out_dir, username)

    meta_path = os.path.join(out_dir, "kernel-metadata.json")
    meta: dict = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

    code_name = meta.get("code_file") or _find_code_file(out_dir)
    code_path = os.path.join(out_dir, code_name)
    if not code_name or not os.path.isfile(code_path):
        raise identity.IdentityError(
            INPUT_USAGE, f"No source file found in {out_dir} after pull"
        )
    is_notebook = code_name.endswith(".ipynb")

    with open(code_path, encoding="utf-8") as f:
        original = f.read()
    patched = original
    applied = 0
    for pair in replacements:
        if not isinstance(pair, list) or len(pair) != 2:
            print(f"[WARN] Skipping invalid replacement pair: {pair}", file=sys.stderr)
            continue
        old, new = pair
        if old in patched:
            patched = patched.replace(old, new, 1)
            applied += 1
        else:
            print(f"[WARN] String not found: {str(old)[:50]}...", file=sys.stderr)

    if args.append_cell:
        if is_notebook:
            notebook_json = json.loads(patched)
            lines = args.append_cell.splitlines()
            notebook_json.setdefault("cells", []).append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [line + ("\n" if i < len(lines) - 1 else "") for i, line in enumerate(lines)],
                }
            )
            patched = json.dumps(notebook_json, indent=1) + "\n"
        else:
            suffix = "" if patched.endswith("\n") else "\n"
            patched = patched + suffix + "\n# --- appended by kaggle notebook edit ---\n" + args.append_cell + "\n"

    with open(code_path, "w", encoding="utf-8") as f:
        f.write(patched)

    if meta:
        meta.pop("id_no", None)
        meta["code_file"] = code_name
        if args.enable_gpu:
            meta["enable_gpu"] = True
            print("[INFO] Enabled GPU in authoring metadata (API push stays enable_gpu=false).")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    print("\n--- Edit Diff ---")
    for line in difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile=f"original-{code_name}",
        tofile=f"modified-{code_name}",
    ):
        sys.stdout.write(line)
    print("-" * 17 + f"\n({applied} replacements made)\n")

    print("Pushing the updated notebook back to Kaggle...")
    return run_deploy_push(
        out_dir,
        username,
        push_label=f"Pushing edited notebook: {notebook}",
        assign_id=False,
        apply_placeholders=False,
        no_hash=True,
        force_push=True,
    )


def register_pull(verbs) -> None:
    pull = verbs.add_parser("pull", help="download the notebook source + metadata")
    pull.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    pull.add_argument("-d", "--dir", metavar="<dir>", help="output directory (default: a fresh snapshot folder)")

    edit = verbs.add_parser("edit", help="pull a notebook, patch it, and push it back")
    edit.add_argument("notebook", metavar="<slug>", help="slug | user:slug | user/slug")
    edit.add_argument("replacements", metavar="<json>", help="JSON array of [old, new] string pairs")
    edit.add_argument("--enable-gpu", action="store_true", help="set authoring enable_gpu=true in the metadata")
    edit.add_argument("--append-cell", metavar="<code>", help="append the given code as a new trailing cell")
