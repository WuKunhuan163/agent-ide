"""Write a run's products, idempotently.

Layout (see ``docs/outputs.md``)::

    data/runs/<run_id>/
    ├── run.json                 # the run record (state, handles, per-job truth)
    ├── summary.json             # per-job ledger, keyed by job id -- never by path
    └── jobs/<job_id>/
        ├── full.md
        ├── content_list.json    # precision only
        └── images/…             # precision only, straight from the server zip

Products live per job, because one run may hold several page windows of the same
source and those must not collide.  ``summary.json`` is keyed by ``run_id`` +
``job_id``; the archived tool keyed its summary by the source's *absolute path*,
which made the file useless on any other machine.

Re-running delivery skips anything already written, so ``fetch`` twice costs nothing.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..endpoint.models import Job, RunRecord
from ..mode import Caps
from ..util import log


def job_dir(run_dir: Path, job: Job) -> Path:
    path = run_dir / "jobs" / job.job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def already_materialized(job: Job) -> bool:
    return job.materialized_at is not None and bool(job.outputs)


def write_job(run_dir: Path, job: Job, product: dict, caps: Caps) -> list[Path]:
    """Persist one job's product; returns the paths written.

    Figures are counted, not enumerated: a 38-page paper ships 88 of them, and listing
    every path in the run record buries the four facts a reader wants behind a wall of
    hashes (the first version of this file produced a 12KB summary that was 95% image
    paths).
    """
    target = job_dir(run_dir, job)
    written: list[Path] = []

    markdown = product.get("markdown") or ""
    md_path = target / "full.md"
    md_path.write_text(markdown, encoding="utf-8")
    written.append(md_path)

    content_list = product.get("content_list")
    if content_list is not None:
        cl_path = target / "content_list.json"
        cl_path.write_text(json.dumps(content_list, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(cl_path)

    images = product.get("images") or {}
    for name, payload in images.items():
        image_path = target / name
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(payload)

    job.materialized_at = time.time()
    job.outputs = [str(path.relative_to(run_dir)) for path in written]
    job.block_count = len(content_list) if isinstance(content_list, list) else 0
    job.image_count = len(images)
    job.images_dir = f"jobs/{job.job_id}/images" if images else None
    # An archive legitimately has no figures when the document has none, so an empty
    # images/ is information, not a fault.  A skipped block structure is worth naming
    # because it means the endpoint's own product was thinner than its contract.
    if caps.has_blocks and content_list is None:
        log.warn(f"{job.name}: the archive carried no block structure")
    elif caps.has_images and not images:
        log.debug(f"{job.name}: no figures in this document")
    return written


def write_summary(run_dir: Path, record: RunRecord) -> Path:
    """One file describing the whole run, keyed by ids rather than by paths."""
    payload = {
        "run_id": record.run_id,
        "mode": record.mode,
        "created_at": record.created_at,
        "finished_at": record.finished_at or time.time(),
        "exit_code": record.exit_code,
        "batch_ids": record.batch_ids,
        "jobs": [
            {
                "job_id": job.job_id,
                "name": job.name,
                "source": job.source.value,
                "source_kind": job.source.kind,
                "page_range": job.page_range,
                "state": job.state,
                "err_msg": job.err_msg,
                "elapsed_s": job.elapsed_s,
                "blocks": job.block_count,
                "images": job.image_count,
                "images_dir": job.images_dir,
                "outputs": job.outputs,
            }
            for job in record.jobs
        ],
    }
    path = run_dir / "summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
