"""The adaptive scheduler: the only place in the skill that runs things concurrently.

Its whole job is to keep a *budget* of in-flight work and let the endpoint's own
feedback move that budget.  The documentation publishes no concurrency limit at all
-- the only two signals that exist are ``-60009`` ("submission queue full") and HTTP
429 (flash, per-IP).  So the rule is: start modest, back off multiplicatively when
refused, creep back up after a clean streak.  Measured, six concurrent flash jobs
finish with no refusal at all, which is why the ceiling starts at 6 and not at 1.

Three behaviours are worth knowing before reading the code:

* **Retries are separated by action.**  A queue-full answer is worth retrying, an
  oversized file is not; the mapping lives in ``endpoint.errors``.
* **Splitting is error-driven and incremental.**  A blind submission (a source whose
  page count could not be read) that comes back with the page-limit code is replaced by
  windows *one at a time*: because the page count is unknown, the only honest way to
  find the end of the file is to ask for the next window and see whether it finishes.
  Each window is cut out of the source in memory on its way out (``submit.put_job``);
  no file is ever written to disk.
* **Halt is sticky.**  A daily-quota refusal or a rejected token stops the run
  instead of burning the remaining attempts against a wall.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from ..config import Config
from ..endpoint import errors
from ..endpoint.client import EndpointClient
from ..endpoint.errors import Action, ApiError
from ..endpoint.models import Job, RunRecord
from ..mode import Caps, Mode
from ..plan import planner, quota
from ..util import exit_codes, log
from ..util.ids import new_job_id
from . import poll, store, submit


class Scheduler:
    def __init__(self, client: EndpointClient, cfg: Config, caps: Caps,
                 record: RunRecord, options: dict) -> None:
        self.client = client
        self.cfg = cfg
        self.caps = caps
        self.record = record
        self.options = options
        self.limit = cfg.common.concurrency_initial
        self.streak = 0
        self.backoff_index = 0
        self.deadline = time.time() + cfg.common.poll_total_timeout_s
        self.halted: str | None = None
        self._lock = threading.Lock()
        #: blind sources being walked window by window: source -> next start page
        self._ladder: dict[str, int] = {}
        #: sources with at least one window finished, so a later refusal means "past
        #: the end of the file" rather than "this file cannot be split at all"
        self._ladder_progress: set[str] = set()
        #: every name already sent to the endpoint; a batch item comes back by name
        #: only, so two files in one run may never share one
        self._taken: set[str] = set()

    # ------------------------------------------------------------------ #
    # the run
    # ------------------------------------------------------------------ #
    def run(self, jobs: list[Job]) -> int:
        self.record.jobs = list(jobs)
        self._taken = {job.name for job in self.record.jobs}
        # the opening line names only what no other line does: the job count arrives with
        # the closing tally, and the mode with `cli`'s run handle
        log.info(f"concurrency {self.limit}/{self.cfg.common.concurrency_max}")
        self._save()          # the record exists before anything is submitted
        if self.caps.mode is Mode.PRECISION:
            self._run_precision(deque(self.record.jobs))
        else:
            self._run_flash(deque(self.record.jobs))
        return self._exit_code()

    def _exit_code(self) -> int:
        total = len(self.record.jobs)
        done = sum(1 for job in self.record.jobs if job.state == "done")
        if total and done == total:
            return exit_codes.OK
        if done:
            return exit_codes.PARTIAL
        return exit_codes.FAILED

    # ------------------------------------------------------------------ #
    # adaptive budget
    # ------------------------------------------------------------------ #
    def _slow_down(self, why: str) -> None:
        before = self.limit
        self.limit = max(1, int(self.limit * self.cfg.common.concurrency_down_factor))
        self.streak = 0
        log.warn(f"{why}; in-flight budget {before} -> {self.limit}")

    def _speed_up(self) -> None:
        self.streak += 1
        ceiling = self.cfg.common.concurrency_max
        if self.streak >= self.cfg.common.concurrency_probe_after and self.limit < ceiling:
            self.limit = min(ceiling, self.limit + self.cfg.common.concurrency_up_step)
            self.streak = 0
            log.info(f"clean streak; in-flight budget -> {self.limit}")

    def _sleep_backoff(self) -> None:
        steps = self.cfg.common.backoff_steps
        delay = steps[min(self.backoff_index, len(steps) - 1)]
        self.backoff_index += 1
        remaining = self.deadline - time.time()
        if remaining <= 0:
            return
        delay = int(min(delay, max(1, remaining)))
        log.info(f"waiting {delay}s before retrying")
        time.sleep(delay)

    # ------------------------------------------------------------------ #
    # identifier contract
    # ------------------------------------------------------------------ #
    def _save(self) -> None:
        store.save(self.record)

    def _announce(self) -> None:
        """Persist first -- never the other way round.

        The record is on disk before the request that gives it meaning is answered, so a
        process killed at any point leaves behind what a resume needs.  ``cli`` prints the
        run handle from it at startup.
        """
        with self._lock:
            store.save(self.record)

    # ------------------------------------------------------------------ #
    # shared failure handling
    # ------------------------------------------------------------------ #
    def _requeue_or_fail(self, job: Job, action: Action, message: str, pending: deque) -> None:
        if errors.should_split(action) and job.page_range is None:
            log.info(f"{job.name}: refused ({action.value}); asking for the first "
                     f"{self.caps.page_limit}-page window")
            job.state = "split"
            job.err_msg = message
            self._ask_for_window(job, pending)
            return

        if action is Action.SPLIT_REQUIRED:
            if job.source.value in self._ladder_progress:
                # A window the endpoint refused after earlier ones were accepted, so the
                # refusal is about this window, not about the file.  The end of a file is
                # normally found by the mapping table before anything is sent (see
                # ``_ask_for_window``); this is where the server disagrees with our count.
                log.info(f"{job.source.name}: nothing beyond {job.page_range}; ladder finished")
                self._finish_ladder(job)
                return
            message += " (already split; this window is still too large)"

        if action is Action.RETRY_BACKOFF:
            self._slow_down(message)
            if job.attempts < self.cfg.common.retry_max:
                job.attempts += 1
                job.state = "planned"
                job.err_msg = message
                pending.append(job)
                return

        if action in (Action.QUOTA_STOP, Action.BAD_TOKEN):
            self.halted = message
            log.error(f"stopping the run: {message}")

        job.state = "failed"
        job.err_msg = message
        self._end_ladder(job)

    # ------------------------------------------------------------------ #
    # blind sources: the page count is unknown, so the split is a guess
    # ------------------------------------------------------------------ #
    def _ask_for_window(self, job: Job, pending: deque) -> None:
        """Ask for exactly one more window of a source the plan could not measure.

        The *mapping table* of the next window decides whether there is anything to ask
        for: pages that do not exist map to nothing, so the ladder learns where the file
        ends without spending a request on finding out.  A source whose page count cannot
        be measured at all has no equivalent PDF to send, and says so instead of climbing.

        One window at a time still matters for the old reason: asking for all of them up
        front would mean dozens of submissions that cannot succeed.
        """
        start = self._ladder.get(job.source.value, 1)
        if (start - 1) // self.caps.page_limit + 1 > planner.MAX_WINDOWS:
            log.warn(f"{job.source.name}: stopping the window ladder after "
                     f"{planner.MAX_WINDOWS} windows; the endpoint accepted every one of them")
            self._ladder.pop(job.source.value, None)
            return
        start, end = planner.window_at(self.caps.page_limit, start)
        pages = planner.window_pages(job.source, f"{start}-{end}")
        if pages is None:
            reason = (f"{job.source.name}: pages {start}-{end} cannot be cut out -- its page "
                      f"count is unmeasurable, so the file cannot be split")
            log.error(reason)
            job.state = "failed"
            job.err_msg = reason
            self._finish_ladder(job)
            return
        if not pages:
            log.info(f"{job.source.name}: nothing beyond page {start - 1}; ladder finished")
            self._finish_ladder(job)
            return
        self._ladder[job.source.value] = end + 1
        clone = Job(
            job_id=new_job_id(),
            source=job.source,
            name=planner.unique_name(planner.window_name(job.source, start, end), self._taken),
            page_range=f"{start}-{end}",
        )
        if job.page_range is None:
            # the blind parent is not a deliverable any more: the windows replace it,
            # and leaving it in the record would report the run as partial forever
            self.record.jobs = [other for other in self.record.jobs if other is not job]
        self.record.jobs.append(clone)
        pending.append(clone)
        log.info(f"{job.source.name}: asking for pages {start}-{end}")

    def _continue_ladder(self, job: Job, pending: deque) -> None:
        """Only a finished window justifies asking for the next one."""
        if job.state == "done" and job.source.value in self._ladder:
            self._ladder_progress.add(job.source.value)
            self._ask_for_window(job, pending)

    def _end_ladder(self, job: Job) -> None:
        """A window that failed *is* the end of the ladder -- do not keep guessing."""
        if job.page_range is not None:
            self._ladder.pop(job.source.value, None)

    def _finish_ladder(self, job: Job) -> None:
        """The file ends here: drop the ladder, and the blind parent along with it.

        The windows replaced the parent, so leaving the parent in the record would report
        a fully delivered run as partial forever.
        """
        self._ladder.pop(job.source.value, None)
        if job.page_range is None:
            self.record.jobs = [other for other in self.record.jobs if other is not job]

    def _absorb_submit_error(self, exc: ApiError, jobs: list[Job], pending: deque) -> None:
        """A failure at submission time applies to the whole chunk."""
        if exc.action is Action.RETRY_BACKOFF:
            self._slow_down(exc.describe())
            requeued = 0
            for job in jobs:
                if job.attempts < self.cfg.common.retry_max:
                    job.attempts += 1
                    job.state = "planned"
                    pending.append(job)
                    requeued += 1
                else:
                    job.state = "failed"
                    job.err_msg = exc.describe()
                    self._end_ladder(job)
            log.warn(f"submission refused ({exc.describe()}); requeued {requeued}/{len(jobs)}")
            self._sleep_backoff()
            return
        if exc.action in (Action.QUOTA_STOP, Action.BAD_TOKEN):
            self.halted = exc.describe()
            log.error(f"stopping the run: {exc.describe()}")
        for job in jobs:
            job.state = "failed"
            job.err_msg = exc.describe()
            self._end_ladder(job)

    # ------------------------------------------------------------------ #
    # precision
    # ------------------------------------------------------------------ #
    def _run_precision(self, pending: deque) -> None:
        while pending and not self.halted and time.time() < self.deadline:
            size = min(self.caps.link_batch_size, len(pending))
            chunk = [pending.popleft() for _ in range(size)]
            groups = self._submit_chunk(chunk, pending)
            for batch_id, members in groups:
                if batch_id not in self.record.batch_ids:
                    self.record.batch_ids.append(batch_id)
                self._announce()
                live = [job for job in members if job.state != "failed"]
                if not live:
                    continue
                started = time.time()

                def progress(done: int, expected: int, _t=started) -> None:
                    # a sole job needs no progress line -- its own outcome line follows
                    # immediately -- and the first probe fires before there is anything to
                    # report, so "0/2 finished (0s)" is never worth a line either
                    if done == 0 or expected == 1:
                        return
                    log.info(f"waiting: {done}/{expected} finished ({time.time() - _t:.0f}s)")

                try:
                    items = poll.poll_batch(self.client, batch_id, len(live), self.cfg,
                                            self.deadline, on_progress=progress)
                except ApiError as exc:
                    self._absorb_submit_error(exc, live, pending)
                    continue
                poll.apply_items(
                    live, items,
                    lambda job, message: self._requeue_or_fail(
                        job, errors.action_from_message(message), message, pending),
                )
                settled = time.time()
                for job in live:
                    if job.state in ("done", "failed"):
                        job.finished_at = settled
                    if job.state == "done":
                        self._speed_up()
                        self._continue_ladder(job, pending)
                store.save(self.record)

    def _submit_chunk(self, chunk: list[Job], pending: deque) -> list[tuple[str, list[Job]]]:
        """Send one chunk; local files and URLs travel by different endpoints."""
        groups: list[tuple[str, list[Job]]] = []
        files = [job for job in chunk if not submit.server_fetched(job)]
        urls = [job for job in chunk if submit.server_fetched(job)]

        if files:
            try:
                links = submit.request_links(self.client, files, self.options)
                failures = submit.upload_jobs(self.client, files, self.cfg)
            except ApiError as exc:
                self._absorb_submit_error(exc, files, pending)
            else:
                groups.append((links.batch_id, files))
                submitted_at = time.time()
                for job in files:
                    job.started_at = submitted_at
                    log.info(f"submit {job.name}")
                    if job.job_id in failures:
                        self._requeue_or_fail(job, Action.RETRY_BACKOFF, failures[job.job_id], pending)

        if urls:
            try:
                batch_id = self.client.request_url_batch(submit.url_batch_payload(urls, self.options))
            except ApiError as exc:
                self._absorb_submit_error(exc, urls, pending)
            else:
                submitted_at = time.time()
                for job in urls:
                    job.batch_id = batch_id
                    job.started_at = submitted_at
                    log.info(f"submit {job.name} (server fetches it)")
                groups.append((batch_id, urls))
        return groups

    # ------------------------------------------------------------------ #
    # flash
    # ------------------------------------------------------------------ #
    def _run_flash(self, pending: deque) -> None:
        ceiling = max(1, self.cfg.common.concurrency_max)
        with ThreadPoolExecutor(max_workers=ceiling) as pool:
            futures: dict = {}
            while not self.halted and time.time() < self.deadline:
                while pending and len(futures) < self.limit:
                    job = pending.popleft()
                    futures[pool.submit(self._flash_one, job)] = job
                if not futures:
                    break
                done, _ = wait(list(futures), return_when=FIRST_COMPLETED)
                for future in done:
                    job = futures.pop(future)
                    try:
                        markdown_url = future.result()
                    except ApiError as exc:
                        self._requeue_or_fail(job, exc.action, exc.describe(), pending)
                    else:
                        job.state = "done"
                        job.markdown_url = markdown_url or None
                        job.err_msg = ""
                        self._speed_up()
                        self._continue_ladder(job, pending)
                    self._announce()
            for future, job in list(futures.items()):
                future.cancel()
                if job.state not in ("done", "failed"):
                    job.state = "failed"
                    job.err_msg = "run budget exhausted before this task finished"

    def _flash_one(self, job: Job) -> str:
        """Create one flash task, upload, and poll it to completion."""
        started = time.time()
        job.started_at = started
        try:
            if submit.server_fetched(job):
                task_id = self.client.create_flash_url_task(
                    submit.flash_url_payload(job, self.options))
            else:
                task_id, file_url = self.client.create_flash_task(
                    submit.flash_payload(job, self.options))
                job.upload_url = file_url
                submit.put_job(self.client, job)
            job.task_id = task_id
            log.info(f"submit {job.name}")
            self._announce()

            def on_state(state, _job=job, _t=started) -> None:
                # a terminal state is not worth its own line: the job's outcome line says
                # the same thing with the elapsed time a moment later
                if state.state in ("done", "failed"):
                    return
                log.info(f"{_job.name}: {state.state} ({time.time() - _t:.0f}s)")

            state = poll.poll_flash(self.client, task_id, self.cfg, self.deadline,
                                    on_state=on_state)
        finally:
            job.finished_at = time.time()
        if state.state == "done":
            return state.markdown_url or ""
        # classify from what the task said, not from the fact that it ended: "failed"
        # on its own says nothing about whether a split or a retry would help, and the
        # code the task reports is the one that decides it
        detail = " ".join(part for part in (state.err_code, state.err_msg) if part) or state.state
        raise ApiError(errors.action_from_message(detail), state.err_code,
                       f"task ended in state={state.state}"
                       + (f": {state.err_msg}" if state.err_msg else ""))

    # ------------------------------------------------------------------ #
    # reporting
    # ------------------------------------------------------------------ #
    def summary(self) -> str:
        """One line per job, plus the halt reason if the run was stopped.

        The tally is deliberately not repeated here: the closing JSON already carries
        ``done``/``failed``, and two counts of one run on one screen is one too many.
        """
        lines = job_lines(self.record)
        if self.halted:
            lines.append(f"halted: {self.halted}")
        return "\n".join(lines)


def job_lines(record: RunRecord) -> list[str]:
    """One dense line per job -- what a shell user wants to read at the end.

    Fields are separated by a single space: padding to align columns is what turns a
    readable line into one that has to be re-aligned by hand every time a field changes.
    """
    lines: list[str] = []
    for job in record.jobs:
        mark = {"done": "ok", "failed": "FAIL"}.get(job.state, job.state)
        bits = [mark, job.name]
        if job.page_range:
            bits.append(f"pages {_page_spec(job.page_range)}")
        elif job.source.pages:
            bits.append(f"pages {job.source.pages}")
        if job.elapsed_s is not None:
            bits.append(f"{job.elapsed_s:.1f}s")
        if job.block_count:
            bits.append(f"{job.block_count} blocks")
        if job.image_count:
            bits.append(f"{job.image_count} img")
        if job.state == "failed" and job.err_msg:
            bits.append(f"-- {_clipped(job.err_msg)}")
        lines.append(" ".join(bits))
    return lines


def _page_spec(spec: str) -> str:
    """``"2-2"`` reads as a typo, so a one-page window prints as ``"2"``."""
    head, dash, tail = spec.partition("-")
    return head if dash and head == tail else spec


def _clipped(text: str, limit: int = 160) -> str:
    """Cut on a word boundary: a message that stops mid-word reads as a bug of its own."""
    if len(text) <= limit:
        return text
    return f"{text[:limit].rsplit(' ', 1)[0]}…"


def ledger_note(cfg: Config, caps: Caps) -> str:
    return quota.describe(caps, cfg)
