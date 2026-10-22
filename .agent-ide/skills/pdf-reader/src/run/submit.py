"""Submission: ask for upload links, then PUT the bytes.

Precision batches files into link requests (the documented ceiling is 50 links per
request); flash takes exactly one file per request.  Uploads for one link batch run
concurrently, which is where most of the wall-clock saving comes from: measured, an
upload costs ~0.9s while the server needs ~3-4s of fixed work per file.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..endpoint import errors
from ..endpoint.client import EndpointClient
from ..endpoint.errors import ApiError
from ..endpoint.models import Job, LinkBatch
from ..plan import planner, probe
from ..util import log


def precision_payload(job: Job, options: dict) -> dict:
    """One entry of the ``files`` array for the precision link request.

    No ``page_ranges``, ever.  A windowed job is cut out here first and the pages travel
    as the uploaded file (see :func:`put_job`), so a range would describe a document
    that no longer resembles the one that arrives -- "pages 201-400" of a file that *is*
    pages 201-400 can only point past its end.
    """
    entry: dict = {"name": job.name}
    if options.get("ocr") is not None:
        entry["is_ocr"] = bool(options["ocr"])
    return entry


def flash_payload(job: Job, options: dict) -> dict:
    """Body of the flash task-creation request.

    Like the precision entry, it names no page range: a window travels as the file
    itself.
    """
    payload: dict = {"file_name": job.name}
    language = options.get("language")
    payload["language"] = language or "ch"
    if options.get("ocr") is not None:
        payload["is_ocr"] = bool(options["ocr"])
    if options.get("formula") is not None:
        payload["enable_formula"] = bool(options["formula"])
    if options.get("table") is not None:
        payload["enable_table"] = bool(options["table"])
    return payload


def url_payload(job: Job, options: dict) -> dict:
    """One entry of the ``files`` array for the URL batch request.

    Reached only by a whole document named by URL (see :func:`server_fetched`): a job with
    a page range is materialised locally and uploaded as its equivalent PDF instead, so a
    range has nothing left to describe here.
    """
    entry: dict = {"url": job.source.value}
    if options.get("ocr") is not None:
        entry["is_ocr"] = bool(options["ocr"])
    return entry


def url_batch_payload(jobs: list[Job], options: dict) -> dict:
    body: dict = {"files": [url_payload(job, options) for job in jobs]}
    if options.get("language"):
        body["language"] = options["language"]
    body["enable_formula"] = bool(options.get("formula", True))
    body["enable_table"] = bool(options.get("table", True))
    if options.get("model"):
        body["model_version"] = options["model"]
    return body


def flash_url_payload(job: Job, options: dict) -> dict:
    """Flash's URL entry point takes ``url`` instead of ``file_name``."""
    payload = flash_payload(job, options)
    payload.pop("file_name", None)
    payload["url"] = job.source.value
    return payload


def batch_payload(jobs: list[Job], options: dict) -> dict:
    """Top-level body of the precision link request.

    Formula/table/language are sent **explicitly**: the official client leaves them
    out by default, which lets behaviour drift with whatever the server decided that
    week.
    """
    body: dict = {"files": [precision_payload(job, options) for job in jobs]}
    if options.get("language"):
        body["language"] = options["language"]
    body["enable_formula"] = bool(options.get("formula", True))
    body["enable_table"] = bool(options.get("table", True))
    if options.get("model"):
        body["model_version"] = options["model"]
    return body


def request_links(client: EndpointClient, jobs: list[Job], options: dict) -> LinkBatch:
    links = client.request_links(batch_payload(jobs, options))
    for job, url in zip(jobs, links.file_urls):
        job.batch_id = links.batch_id
        job.upload_url = url
    return links


def server_fetched(job: Job) -> bool:
    """Whether the endpoint fetches this input itself: a whole document named by URL.

    Anything carrying a page range is materialised and uploaded instead -- URL or not --
    because a window is an equivalent PDF (see :func:`put_job`) and no range can stand in
    for one.  That is also why the URL payloads carry no range: the jobs that ride them are
    the ones with nothing to range.
    """
    return job.source.is_url and not job.page_range


def _local_path(client: EndpointClient, job: Job) -> Path:
    """The local file a job is cut from, fetching a URL input once if it still is one.

    A windowed URL therefore stops being a URL here: the mapping table has to be read off
    real pages, so the document is kept locally first and the job becomes an ordinary
    local one from then on.
    """
    if not job.source.is_url:
        return Path(job.source.value)
    local = Path(probe.materialise(client, job.source.value))
    job.source.kind = "file"
    job.source.value = str(local)
    return local


def put_job(client: EndpointClient, job: Job) -> int:
    """PUT one job's bytes: the file, or the equivalent PDF of the pages it names.

    A window is *materialised* before it travels: "201-400 of this file" becomes a PDF of
    pages 201-400, cut in memory, and that document is what is uploaded.  The endpoint
    measures the bytes it is handed, so this is the only form a window can take and
    nothing downstream is ever told a range instead.  Returns how many bytes were sent.
    Both channels upload through this call, so a flash window and a precision window are
    cut by the same code.
    """
    url = job.upload_url or ""
    if not url:
        raise ApiError(errors.Action.UNKNOWN, "",
                       f"{job.name}: the endpoint issued no upload link")
    path = _local_path(client, job)
    if not job.page_range:
        return client.upload(url, path)
    pages = planner.window_pages(job.source, job.page_range)
    if pages is None:
        raise ApiError(errors.Action.UNKNOWN, "no-window",
                       f"{job.name}: pages {job.page_range} cannot be cut into a PDF of their "
                       f"own (the page count is unmeasurable), and a window is never sent as "
                       f"a range instead; nothing was submitted")
    if not pages:
        raise ApiError(errors.Action.UNKNOWN, "no-pages",
                       f"{job.name}: pages {job.page_range} do not exist in "
                       f"{path.name}; nothing was submitted")
    data = probe.window_bytes(path, pages)
    if data is None:
        raise ApiError(errors.Action.UNKNOWN, "no-window",
                       f"{job.name}: the equivalent PDF of pages {job.page_range} could not "
                       f"be built; nothing was submitted")
    return client.upload_bytes(url, data)


def upload_jobs(client: EndpointClient, jobs: list[Job], cfg, pool: ThreadPoolExecutor | None = None) -> dict[str, str]:
    """PUT every job's bytes. Returns ``{job_id: error}`` for the failures only."""
    failures: dict[str, str] = {}

    def one(job: Job) -> tuple[str, str]:
        if server_fetched(job) or not job.upload_url:
            return job.job_id, ""                # the server fetches whole URLs itself
        try:
            size = put_job(client, job)
            log.debug(f"uploaded {job.name} ({size} bytes)")
            return job.job_id, ""
        except ApiError as exc:
            return job.job_id, exc.describe()

    runnable = [job for job in jobs if job.upload_url and not server_fetched(job)]
    if not runnable:
        return failures
    if pool is None:
        with ThreadPoolExecutor(max_workers=min(len(runnable), cfg.common.concurrency_max)) as pool:
            results = list(pool.map(one, runnable))
    else:
        results = list(pool.map(one, runnable))
    for job_id, err in results:
        if err:
            failures[job_id] = err
    return failures
