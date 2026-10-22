"""HTTP helpers (requests + system CA bundle)."""
from __future__ import annotations

import requests


def http_get_bytes(url: str, *, headers: dict | None = None, timeout: float = 15) -> bytes:
    with requests.get(url, headers=headers or {}, timeout=timeout) as resp:
        resp.raise_for_status()
        return resp.content


def http_get_json(url: str, *, headers: dict | None = None, timeout: float = 3) -> dict:
    with requests.get(url, headers=headers or {}, timeout=timeout) as resp:
        resp.raise_for_status()
        return resp.json()
