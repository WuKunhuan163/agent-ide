"""Kaggle identity: shared token pool + per-agent account binding.

Layout:
    data/accounts/<kaggle_username>/kaggle.json   shared token pool (mode 0600)
    data/agents/<agent_id>/config.json            {"username": "<kaggle_username>"}

The agent id (``--id``) and the Kaggle account are independent. An agent binds
exactly one account (``config --switch-user``); the per-command ``--account``
override was dropped on purpose, so account resolution is deterministic.
"""
from __future__ import annotations

import json
import os

from src.config.config import load_config, save_config
from src.exit_codes import AUTH_NO_ACCOUNT, AUTH_TOKEN_MISSING, IdentityError
from src.paths import require_ctx

TOKEN_NAME = "kaggle.json"
SETTINGS_URL = "https://www.kaggle.com/settings/api"


def entry_hint() -> str:
    """Canonical thin-entry invocation for recovery text (no entry.sh, no pool binary)."""
    return f"python3 .agent-ide/skills/kaggle/kaggle.py --id {require_ctx().agent_id}"


def accounts_root() -> str:
    return require_ctx().accounts_dir


def token_path(username: str) -> str:
    return os.path.join(accounts_root(), username, TOKEN_NAME)


def has_token(username: str) -> bool:
    return os.path.isfile(token_path(username))


def list_accounts() -> list[str]:
    """Kaggle usernames that have a token file in the shared pool."""
    root = accounts_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        name
        for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name, TOKEN_NAME))
    )


def read_token(username: str) -> dict:
    path = token_path(username)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise IdentityError(AUTH_TOKEN_MISSING, token_missing_message(username)) from None
    except (json.JSONDecodeError, OSError) as exc:
        raise IdentityError(
            AUTH_TOKEN_MISSING, f"Token file for '{username}' is unreadable: {path} ({exc})"
        ) from None
    return data if isinstance(data, dict) else {}


def bind(username: str) -> None:
    config = load_config()
    config["username"] = username
    save_config(config)


def register_token(src_path: str) -> str:
    """Copy a downloaded kaggle.json into the shared pool; return its Kaggle username."""
    src = os.path.expanduser(src_path)
    if not os.path.isfile(src):
        raise IdentityError(AUTH_TOKEN_MISSING, f"Token file not found: {src}")
    try:
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise IdentityError(AUTH_TOKEN_MISSING, f"Not a valid kaggle.json: {src} ({exc})") from None
    username = data.get("username") if isinstance(data, dict) else None
    if not username or not data.get("key"):
        raise IdentityError(
            AUTH_TOKEN_MISSING, f"kaggle.json must contain both 'username' and 'key': {src}"
        )
    dest = token_path(username)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.chmod(dest, 0o600)
    return username


def bound_username() -> str | None:
    """Account this agent is bound to, read from config only (no side effects)."""
    return load_config().get("username") or None


def resolve_username() -> str:
    """Bound account, else the only account on disk, else an IdentityError."""
    config = load_config()
    bound = config.get("username")
    if bound:
        if has_token(bound):
            return bound
        raise IdentityError(
            AUTH_TOKEN_MISSING,
            token_missing_message(bound)
            + "\n  note: config.json points at it, but no token is registered.",
        )

    available = list_accounts()
    if len(available) == 1:
        bind(available[0])
        return available[0]
    if not available:
        from src.chrome.browser import open_once

        open_once(SETTINGS_URL, account=None)
        raise IdentityError(
            AUTH_NO_ACCOUNT,
            f"Agent '{require_ctx().agent_id}' has no Kaggle account.\n"
            f"  Ask the human to create a token at {SETTINGS_URL} (Create New Token),\n"
            f"  then register it: {entry_hint()} config --token-file <downloaded_kaggle.json>",
        )
    raise IdentityError(
        AUTH_NO_ACCOUNT,
        f"Agent '{require_ctx().agent_id}' is not bound to an account and {len(available)} exist on disk:\n"
        + "\n".join(f"    - {name}" for name in available)
        + f"\n  Pick one: {entry_hint()} config --switch-user <kaggle_user>",
    )


def credentials() -> tuple[str, dict]:
    """Resolved username plus its token payload (for the exec layer's env)."""
    username = resolve_username()
    return username, read_token(username)


def token_missing_message(username: str) -> str:
    return (
        f"No token registered for Kaggle account '{username}'.\n"
        f"  expected: {token_path(username)}\n"
        f"  fix: {entry_hint()} config --token-file <kaggle.json>"
    )


def auth_rejected_message(username: str, detail: str = "") -> str:
    """Recovery text for AUTH_REJECTED (Kaggle API refused the credentials)."""
    lines = [
        f"Kaggle API rejected the credentials of account '{username}'.",
        f"  token: {token_path(username)}",
        "  fix: create a fresh token at https://www.kaggle.com/settings/api, then re-register it:",
        f"    {entry_hint()} config --token-file <kaggle.json>",
    ]
    if detail:
        lines.append(f"  api said: {detail.strip()}")
    return "\n".join(lines)
