"""Plain data handed between layers, plus their on-disk JSON form.

Two shapes matter most, and the endpoint's asymmetry is baked in:

* precision returns ``batch_id`` and later a zip containing markdown, blocks and
  images;
* flash returns ``task_id`` and later nothing but a markdown URL.

A job therefore carries whichever handle it got, and ``has_zip`` / ``has_blocks``
on the mode caps decide what ``deliver`` is allowed to expect.

Identifiers are *not* defined here (see ``util.ids``): this module only describes
what has to be stored, and loading a record written by an older version must not
break because a field was renamed or removed.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


def now_ts() -> float:
    return time.time()


def _declared_only(cls: type, payload: dict[str, Any]) -> dict[str, Any]:
    """Drop keys this version does not know, so old records still load."""
    known = {f.name for f in fields(cls)}
    return {key: value for key, value in payload.items() if key in known}


@dataclass
class Source:
    """An input the user named: a local path or a URL."""

    value: str
    kind: str                       # "file" | "url"
    name: str
    pages: int | None = None
    size_mb: float | None = None
    page_bytes: list[int] | None = None   # serialized size of page 1, 2, ... when measured

    @property
    def is_url(self) -> bool:
        return self.kind == "url"


@dataclass
class Job:
    """One file as it will be submitted: a source, optionally a page window."""

    job_id: str
    source: Source
    name: str                       # name sent to the endpoint
    page_range: str | None = None   # "1-200" | None for the whole file
    state: str = "planned"
    err_msg: str = ""
    zip_url: str | None = None
    markdown_url: str | None = None
    upload_url: str | None = None
    batch_id: str | None = None
    task_id: str | None = None
    attempts: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    materialized_at: float | None = None
    outputs: list[str] = field(default_factory=list)
    block_count: int = 0
    image_count: int = 0
    images_dir: str | None = None

    @property
    def elapsed_s(self) -> float | None:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 1)
        return None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = asdict(self.source)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        payload = _declared_only(cls, data)
        payload["source"] = Source(**_declared_only(Source, payload["source"]))
        return cls(**payload)


@dataclass
class ItemState:
    """What the batch query returns per file -- only four fields exist."""

    file_name: str
    state: str
    err_msg: str = ""
    zip_url: str | None = None


@dataclass
class FlashState:
    """Flash's task view.

    Unlike a precision batch item -- which comes back with a name, a state, a message
    and a zip URL and nothing else -- a flash task *does* report ``err_code``.  Ignoring
    it meant a page-limit refusal arrived as an anonymous "failed" and the window
    ladder never started.
    """

    task_id: str
    state: str
    markdown_url: str | None = None
    err_msg: str = ""
    err_code: str = ""


@dataclass
class LinkBatch:
    batch_id: str
    file_urls: list[str]


@dataclass
class RunRecord:
    """The single source of truth for a run, persisted as ``run.json``."""

    run_id: str
    mode: str
    created_at: float
    input_dir: str
    output_dir: str
    options: dict[str, Any] = field(default_factory=dict)
    batch_ids: list[str] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)
    finished_at: float | None = None
    exit_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "options": self.options,
            "batch_ids": self.batch_ids,
            "jobs": [job.to_dict() for job in self.jobs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        payload = _declared_only(cls, data)
        payload["jobs"] = [Job.from_dict(job) for job in payload.get("jobs", [])]
        return cls(**payload)


def relative_outputs(run_dir: Path, paths: list[Path]) -> list[str]:
    out: list[str] = []
    for path in paths:
        try:
            out.append(str(path.relative_to(run_dir)))
        except ValueError:
            out.append(str(path))
    return out
