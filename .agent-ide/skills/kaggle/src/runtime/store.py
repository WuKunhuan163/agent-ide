"""Per-agent runtime store: state ledger, event log and the runtime tree.

Everything hangs off ``data/agents/<id>/`` so two agents never share a ledger.
The first read of each file also migrates the pre-per-agent ``global_state.json``
/ ``event_log.json`` (skill-level ``data/``) into the agent dir, once.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

from src.paths import require_ctx


def _legacy_global_path(name: str) -> str:
    return os.path.join(require_ctx().skill_dir, "data", name)


def _migrate_legacy_file(agent_path: str, legacy_name: str) -> None:
    if os.path.exists(agent_path):
        return
    legacy = _legacy_global_path(legacy_name)
    if not os.path.exists(legacy):
        return
    os.makedirs(os.path.dirname(agent_path), exist_ok=True)
    shutil.copy2(legacy, agent_path)


def _read_json_list(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def ensure_runtime_dirs() -> None:
    """Create the runtime tree (root + deploy/output/logs) if missing."""
    p = require_ctx()
    for path in (p.runtime_dir, p.runtime_deploy_dir, p.runtime_output_dir, p.runtime_logs_dir):
        os.makedirs(path, exist_ok=True)


def runtime_path(kind: str, name: str | None = None) -> str:
    """Canonical runtime path under ``data/agents/<id>/runtime/`` (tree ensured)."""
    ensure_runtime_dirs()
    p = require_ctx()
    if kind == "deploy":
        return os.path.join(p.runtime_deploy_dir, name) if name else p.runtime_deploy_dir
    if kind == "output":
        return os.path.join(p.runtime_output_dir, name) if name else p.runtime_output_dir
    if kind == "logs":
        return os.path.join(p.runtime_logs_dir, name) if name else p.runtime_logs_dir
    if kind == "root":
        return p.runtime_dir
    raise ValueError(f"unknown runtime kind: {kind}")


def log_event(username: str, action: str, target: str) -> None:
    """Append one record to the event log (also feeds notebook slug disambiguation)."""
    event_log = require_ctx().event_log_file
    _migrate_legacy_file(event_log, "event_log.json")
    os.makedirs(os.path.dirname(event_log), exist_ok=True)
    events = _read_json_list(event_log)
    events.append(
        {
            "timestamp": datetime.now().isoformat(),
            "username": username,
            "action": action,
            "target": target,
        }
    )
    with open(event_log, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=4)


def load_state() -> dict:
    """Load the per-agent ``state.json`` (mixed schema, migrated on first read)."""
    state_file = require_ctx().state_file
    _migrate_legacy_file(state_file, "global_state.json")
    if not os.path.exists(state_file):
        return {}
    try:
        with open(state_file, encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(state: dict) -> None:
    p = require_ctx()
    os.makedirs(p.agent_dir, exist_ok=True)
    with open(p.state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


def update_notebook_state(
    username: str,
    notebook: str,
    status: str,
    start_time_str: str | None = None,
    *,
    requires_user_gpu: bool | None = None,
) -> dict:
    """Upsert ``state["notebooks"][notebook]`` and return that entry."""
    state = load_state()
    notebooks = state.setdefault("notebooks", {})
    entry = notebooks.setdefault(notebook, {})
    entry["username"] = username
    entry["status"] = status
    entry["updated_at"] = datetime.now().isoformat()
    if start_time_str:
        entry["start_time"] = start_time_str
    if requires_user_gpu is not None:
        entry["requires_user_gpu"] = bool(requires_user_gpu)
    save_state(state)
    return entry


def notebook_requires_user_gpu(notebook: str) -> bool:
    """True when the ledger marks a GPU run *and* the current mode still waits on a human.

    A background push keeps ``enable_gpu=true`` for the API, so Kaggle starts the
    run itself and nobody is owed anything; the ledger flag stays as a record of
    how the push was authored, but no human step follows from it.
    """
    from src.notebook.mode import current

    if not current().requires_run_all:
        return False
    entry = (load_state().get("notebooks") or {}).get(notebook, {})
    return bool(entry.get("requires_user_gpu"))
