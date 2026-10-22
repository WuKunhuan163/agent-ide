"""A local ledger, because the endpoint has no way to ask about quota.

There is no balance/remaining/usage endpoint anywhere in the documented API, and no
management-page view of consumption is mentioned either.  The only signal is a lazy
refusal (``-60018``), so the honest design is: keep your own count, warn before you
submit, and stop when the server finally refuses.

The documented rule is "1000 pages/day at top priority; beyond that, priority drops"
-- a degradation, not a refusal -- so exceeding the ledger never blocks a run by
itself; it only warns.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

try:                                     # stdlib on 3.9+
    from zoneinfo import ZoneInfo
except ImportError:                      # pragma: no cover - very old interpreters
    ZoneInfo = None                      # type: ignore

from ..endpoint.models import Job
from ..mode import Caps
from ..util import log, paths
from .planner import pages_selected


def _today(tz_name: str) -> str:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
        except Exception:
            log.warn(f"unknown timezone {tz_name!r}; falling back to local date")
    return datetime.now().strftime("%Y-%m-%d")


def _load() -> dict:
    path = paths.quota_file()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save(payload: dict) -> None:
    paths.quota_file().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def current(tz_name: str = "Asia/Shanghai") -> dict:
    """Ledger for today, rolling over automatically on the configured midnight."""
    day = _today(tz_name)
    payload = _load()
    if payload.get("date") != day:
        payload = {"date": day, "tz": tz_name, "pages": 0, "files": 0}
        _save(payload)
    return payload


def estimate(jobs: list[Job]) -> int | None:
    """Planned page spend, or ``None`` when a job's page count is unknown."""
    total = 0
    for job in jobs:
        if job.source.pages is None:
            return None
        total += pages_selected(job.page_range) if job.page_range else job.source.pages
    return total


def prewarn(jobs: list[Job], caps: Caps, cfg) -> None:
    """Warn (never refuse) when the plan would cross the documented daily quota."""
    quota = caps.daily_quota_value
    if not quota:
        return
    planned = estimate(jobs)
    if planned is None:
        return
    field = "pages" if caps.daily_quota_unit == "pages" else "files"
    used = current(cfg.common.quota_reset_tz).get(field, 0)
    if used + planned > quota:
        log.warn(f"planned {planned} {caps.daily_quota_unit} on top of {used} already spent today; "
                 f"the {quota}-{caps.daily_quota_unit}/day top-priority quota will be exceeded "
                 f"(submissions continue, but priority drops)")


def commit(jobs: list[Job], caps: Caps, tz_name: str = "Asia/Shanghai") -> dict:
    """Record what a finished run actually spent.

    Owned here, but called by ``run`` -- the ledger file belongs to the planning
    layer, the moment of truth belongs to execution.
    """
    payload = current(tz_name)
    pages = 0
    files = 0
    # The documented 1000-page budget belongs to the precision channel; flash is
    # throttled per IP instead, so counting its pages here would silently eat the
    # precision quota (it did, once: an extra 10 pages appeared for a flash run).
    counts_pages = caps.daily_quota_unit == "pages"
    for job in jobs:
        if job.state != "done":
            continue
        files += 1
        if counts_pages and job.source.pages is not None:
            pages += pages_selected(job.page_range) if job.page_range else job.source.pages
    payload["pages"] = int(payload.get("pages", 0)) + pages
    payload["files"] = int(payload.get("files", 0)) + files
    _save(payload)
    log.debug(f"ledger now {payload['pages']} pages / {payload['files']} files for {payload['date']}")
    return payload


def describe(caps: Caps, cfg) -> str:
    payload = current(cfg.common.quota_reset_tz)
    quota = caps.daily_quota_value or "(unknown)"
    return (f"local ledger {payload['date']} ({payload['tz']}): "
            f"{payload.get('pages', 0)} pages, {payload.get('files', 0)} files; "
            f"documented quota {quota} {caps.daily_quota_unit}/day")
