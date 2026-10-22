"""One token slot, resolved in a documented order.

There is deliberately no key pool and no rotation: the archived tool's pool existed
to stretch one account's daily quota across several accounts, and the endpoint gives
no way to observe quota anyway (no balance endpoint exists), so the pool could only
guess.  The interface keeps a slot for it, and nothing more.

Order: ``--token`` > ``MINERU_TOKEN`` > ``data/token.json``.

The token is a **cloud** credential: it is only ever sent as
``Authorization: Bearer`` to ``mineru.net``.  Local processing never sees it.
"""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass

from ..util import log, paths


ENV_VAR = "MINERU_TOKEN"


@dataclass
class Credential:
    token: str | None
    origin: str          # "flag" | "env" | "data/token.json" | "none"

    @property
    def present(self) -> bool:
        return bool(self.token)

    def channel(self) -> str:
        """The channel a token selects -- a token is not an optimisation flag."""
        return "precision" if self.present else "flash"

    def masked(self) -> str:
        if not self.token:
            return "(none)"
        body = self.token
        return f"{body[:6]}...{body[-4:]} (len {len(body)})" if len(body) > 12 else "(short)"


def load_token() -> str | None:
    path = paths.token_file()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warn("data/token.json is not valid JSON; ignoring it")
        return None
    token = payload.get("token") if isinstance(payload, dict) else None
    return str(token) if token else None


def save_token(token: str) -> None:
    path = paths.token_file()
    path.write_text(json.dumps({"token": token}, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)      # 0600: it is a live credential
    except OSError:  # pragma: no cover - platform dependent
        log.warn(f"could not restrict permissions on {path}")


def delete_token() -> bool:
    path = paths.token_file()
    if path.exists():
        path.unlink()
        return True
    return False


def resolve_credential(flag_token: str | None = None,
                       env: dict[str, str] | None = None) -> Credential:
    env = os.environ if env is None else env
    if flag_token:
        return Credential(flag_token, "flag")
    from_env = env.get(ENV_VAR)
    if from_env:
        return Credential(from_env, f"env {ENV_VAR}")
    stored = load_token()
    if stored:
        return Credential(stored, "data/token.json")
    return Credential(None, "none")
