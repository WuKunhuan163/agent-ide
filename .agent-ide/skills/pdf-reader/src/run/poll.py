"""Polling: cheap probes, exponential backoff, one deadline.

The probe is the bare batch/flash query and nothing else.  The archived client used
the SDK's ``get_batch``, which silently re-downloads the whole result zip every time
it observes ``done`` -- fine as a fetch, ruinous as a status check.

A run gets one wall-clock budget (``poll_total_timeout_s``); everything here is
bounded by it so a stuck task can never hang the process indefinitely.
"""
from __future__ import annotations

import time
from typing import Callable

from ..endpoint.client import EndpointClient
from ..endpoint.errors import ApiError
from ..endpoint.models import FlashState, ItemState, Job
from ..util import log


TERMINAL = ("done", "failed")


def _sleep_for(step: int, cfg) -> int:
    steps = cfg.common.backoff_steps
    index = min(step, len(steps) - 1)
    return min(steps[index], cfg.common.poll_max_s)


def poll_batch(client: EndpointClient, batch_id: str, expected: int, cfg,
               deadline: float, on_progress=None) -> list[ItemState]:
    """Poll one precision batch until every file reaches a terminal state.

    ``on_progress(done, expected)`` fires whenever the finished count changes, which is
    the only feedback a user gets during a wait that ran to 80 seconds here.
    """
    step = 0
    last: list[ItemState] = []
    announced = -1
    while True:
        try:
            items = client.poll_batch(batch_id)
            last = items
            resolved = [item for item in items if item.state in TERMINAL]
            if on_progress is not None and len(resolved) != announced:
                announced = len(resolved)
                on_progress(len(resolved), expected)
            if items and len(resolved) >= expected:
                return items
        except ApiError as exc:
            if not exc.retryable:
                raise
            log.warn(f"state probe failed ({exc.describe()}); will retry")
        step += 1
        remaining = deadline - time.time()
        if remaining <= 0:
            log.warn(f"batch {batch_id} did not finish within the run budget")
            return last
        time.sleep(min(_sleep_for(step, cfg), max(1, int(remaining))))


def poll_flash(client: EndpointClient, task_id: str, cfg, deadline: float,
               on_state=None) -> FlashState:
    """Poll one flash task until it reaches a terminal state."""
    step = 0
    state = FlashState(task_id=task_id, state="unknown")
    announced = None
    while True:
        try:
            state = client.poll_flash(task_id)
            if on_state is not None and state.state != announced:
                announced = state.state
                on_state(state)
            if state.state in TERMINAL:
                return state
        except ApiError as exc:
            if not exc.retryable:
                raise
            log.warn(f"flash probe failed ({exc.describe()}); will retry")
        step += 1
        remaining = deadline - time.time()
        if remaining <= 0:
            log.warn(f"flash task {task_id} did not finish within the run budget")
            return state
        time.sleep(min(_sleep_for(step, cfg), max(1, int(remaining))))


def apply_items(jobs: list[Job], items: list[ItemState],
                on_failure: Callable[[Job, str], None]) -> None:
    """Copy terminal states onto jobs, routing failures through one callback.

    Pairing is by name first.  For a URL submission the server reports the name it
    derived itself, which need not equal the one we used (an arXiv URL has no file
    extension at all), so whatever is left over on both sides is paired in order
    instead of being written off as "no result" -- that mistake would report success
    as failure.
    """
    remaining_jobs = list(jobs)
    unmatched_items: list[ItemState] = []
    for item in items:
        match = next((job for job in remaining_jobs if job.name == item.file_name), None)
        if match is None:
            unmatched_items.append(item)
        else:
            remaining_jobs.remove(match)
            _apply(match, item, on_failure)

    for job, item in zip(remaining_jobs, unmatched_items):
        log.debug(f"{job.name}: paired with the endpoint's {item.file_name!r} by order")
        _apply(job, item, on_failure)
    for job in remaining_jobs[len(unmatched_items):]:
        on_failure(job, "the endpoint returned no result for this file")


def _apply(job: Job, item: ItemState, on_failure: Callable[[Job, str], None]) -> None:
    if item.state == "done":
        job.state = "done"
        job.zip_url = item.zip_url
        job.err_msg = ""
    else:
        on_failure(job, item.err_msg or f"state={item.state}")
