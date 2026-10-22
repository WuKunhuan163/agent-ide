"""The report gate: a round opens only after the session was read in full.

State is two small JSON files per agent id:

* `data/last_round/<id>.json`  — when the previous round ended (window start).
* `data/session_context/<id>.json` — proof of a full read, and its scope.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone

from . import config
from .ide.base import iso, parse_ts
from .paths import marker as marker_path
from .paths import stamp, token as token_path


# --------------------------------------------------------------------- marker


def read_marker(agent_id: str) -> datetime | None:
    try:
        doc = json.loads(marker_path(agent_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parse_ts(doc.get("at")) if isinstance(doc, dict) else None


def write_marker(agent_id: str) -> None:
    now = datetime.now(tz=timezone.utc)
    marker_path(agent_id).parent.mkdir(parents=True, exist_ok=True)
    marker_path(agent_id).write_text(
        json.dumps({"at": iso(now), "round": stamp()}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def window_start(agent_id: str, since_raw: str | None, *, first_hours: int | None) -> tuple[datetime | None, str]:
    """Window start plus a human label for it."""
    if since_raw:
        return parse_when(since_raw), f"--since {since_raw}"
    marker = read_marker(agent_id)
    if marker is not None:
        return marker, "since the previous round"
    if first_hours is None:
        raise config.ConfigError(
            "no completed round for this agent id, so there is no "
            "'since last contact' window; pass --since <when>"
        )
    return (
        datetime.now(tz=timezone.utc) - timedelta(hours=first_hours),
        f"last {first_hours}h (first start; pass --since to widen)",
    )


def parse_when(raw: str) -> datetime:
    """`YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`, `YYYYMMDD_HHMMSS`, or an epoch."""
    text = str(raw).strip()
    for fmt in ("%Y%m%d_%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).astimezone().astimezone(timezone.utc)
        except ValueError:
            continue
    parsed = parse_ts(text)
    if parsed is None:
        raise config.ConfigError(f"cannot read a time from {raw!r}")
    return parsed


# ---------------------------------------------------------------------- token


def read_token(agent_id: str) -> dict | None:
    try:
        doc = json.loads(token_path(agent_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def write_token(agent_id: str, *, ide: str, store: str, since, until, window: str,
                scope: str, conversations: int, messages: int, text: str,
                delivery: str = "stdout") -> dict:
    now = datetime.now(tz=timezone.utc)
    token = {
        "at": iso(now),
        "delivery": delivery,
        "scope": scope,
        "ide": ide,
        "store": store,
        "since": iso(since),
        "until": iso(until) if until else None,
        "window": window,
        "conversations": conversations,
        "messages": messages,
        "chars": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    token_path(agent_id).parent.mkdir(parents=True, exist_ok=True)
    token_path(agent_id).write_text(
        json.dumps(token, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return token


def blocked_reason(agent_id: str) -> str | None:
    """Why a report must not open yet; None when it may."""
    try:
        store = config.make_store()
    except config.ConfigError as exc:
        return str(exc)

    read = f"run: contact-user --id {agent_id} --ide-context"

    token = read_token(agent_id)
    if token is None:
        return f"no session read for this round\n{read}"
    if token.get("ide") != store.ide_id or token.get("store") != str(store.root):
        return f"session token is from another ide or store\n{read}"
    if (token.get("delivery") or "stdout") != "stdout":
        return f"token came from an export, not from a read\n{read}"
    if (token.get("scope") or "all") != "all":
        return f"token is a narrowed read ({token['scope']}), not the whole window\n{read}"
    if int(token.get("messages") or 0) == 0:
        return (
            "token covers 0 messages, so nothing was actually read\n"
            f"run: contact-user --id {agent_id} --ide-context --since <earlier>"
        )
    read_at = parse_ts(token.get("at"))
    marker = read_marker(agent_id)
    if read_at and marker and read_at <= marker:
        return f"token predates the last round\n{read}"
    return None
