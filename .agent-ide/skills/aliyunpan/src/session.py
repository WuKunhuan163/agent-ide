"""One HTTP session per process: credentials, the backup drive, and the rate limit.

Three things live here because they are the same concern — staying inside what the
endpoint tolerates:

* the bearer token and the drive id are read once from `config.json` and refreshed
  from it after a 401, never cached across processes;
* every API call passes through `RateLimiter`, which keeps the request rate under
  the endpoint's limit instead of discovering it through 429s;
* retries are for transport failures, not for application errors: a refused name
  is an answer, not something to try again.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from . import paths
from .errors import DriveMissing, NotLoggedIn, PanError

BASE = "https://openapi.alipan.com/adrive/v1.0/openFile"
BACKUP_DRIVE_TAG = "File"
QPS = 5
RETRY_STATUS = (429, 500, 502, 503, 504)


class RateLimiter:
    """A sliding one-second window; `acquire` blocks until a slot is free."""

    def __init__(self, per_second: int = QPS) -> None:
        self.per_second = per_second
        self._sent: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._sent = [t for t in self._sent if now - t <= 1.0]
                if len(self._sent) < self.per_second:
                    self._sent.append(now)
                    return
            time.sleep(0.05)


class Session:
    """Credentials plus the transport, built from one agent id's config file."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.drive_id = ""
        self.token = ""
        self.limiter = RateLimiter()
        self.http = _build_http()
        self._load()

    # ---------------------------------------------------------------- state

    def _load(self) -> None:
        path = paths.config_path(self.agent_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise NotLoggedIn(f"no login for {self.agent_id!r}; run: aliyunpan login --id {self.agent_id}")
        except (OSError, json.JSONDecodeError) as exc:
            raise NotLoggedIn(f"unreadable {path}: {exc}")
        self._apply(data)

    def reload(self) -> None:
        """After a 401: the binary may have refreshed the token on disk."""
        self._load()

    def _apply(self, data: dict) -> None:
        users = data.get("userList") or []
        if not users:
            raise NotLoggedIn("config.json has no user; run: aliyunpan login")
        user = users[0]
        token = (user.get("openapiToken") or {}).get("accessToken") or ""
        expired = int((user.get("openapiToken") or {}).get("expired") or 0)
        if not token or expired <= int(time.time()):
            raise NotLoggedIn("the stored token has expired; run: aliyunpan login")
        drive = ""
        for item in user.get("driveList") or []:
            if item.get("driveTag") == BACKUP_DRIVE_TAG:
                drive = item.get("driveId") or ""
                break
        if not drive:
            raise DriveMissing(
                "this account has no backup drive (备份盘); enable it in the app, then log in again"
            )
        self.token = token
        self.drive_id = drive

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # ----------------------------------------------------------------- calls

    def call(self, endpoint: str, payload: dict, *, timeout: int = 15) -> dict:
        """POST one API endpoint; return the decoded body or raise `PanError`."""
        payload = {"drive_id": self.drive_id, **payload}
        url = f"{BASE}/{endpoint}"
        last = ""
        for attempt in range(4):
            self.limiter.acquire()
            try:
                response = self.http.post(url, headers=self.headers, json=payload, timeout=timeout)
            except requests.RequestException as exc:
                last = str(exc)
                time.sleep(min(2 ** attempt, 8))
                continue
            if response.status_code == 401:
                self.reload()
                last = "401 after refresh"
                continue
            if response.status_code in RETRY_STATUS:
                last = f"HTTP {response.status_code}"
                time.sleep(min(2 ** attempt, 8))
                continue
            if response.status_code >= 400:
                raise PanError(f"{endpoint}: HTTP {response.status_code} {response.text[:200]}")
            try:
                return response.json()
            except ValueError:
                raise PanError(f"{endpoint}: response is not JSON")
        raise PanError(f"{endpoint}: giving up after retries ({last})")

    def put(self, url: str, body: bytes, *, timeout: int = 120) -> None:
        self.limiter.acquire()
        try:
            response = self.http.put(url, data=body, timeout=timeout)
        except requests.RequestException as exc:
            # A dropped connection is a failed part, not a failed upload: the
            # caller retries this part and keeps the rest of the plan.
            raise PanError(f"part upload: {type(exc).__name__}: {exc}")
        if response.status_code not in (200, 201):
            # The object store explains refusals in the body; without it a 400 is
            # indistinguishable from a bad part size, a stale url or a signature miss.
            detail = response.text[:300].replace("\n", " ")
            raise PanError(f"part upload: HTTP {response.status_code} {detail}")


def _build_http() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=0)
    session.mount("https://", adapter)
    return session
