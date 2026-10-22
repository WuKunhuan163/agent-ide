"""``run.json``: the single source of truth for a run.

The write order is the contract: the record is persisted **before** polling starts,
so a process killed mid-poll still leaves behind everything needed to resume.  ``cli``
prints the run handle it carries as the run's first line.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..endpoint.models import RunRecord
from ..util import log, paths
from ..util.ids import new_run_id


def create(mode: str, options: dict, output_dir: Path | None = None) -> RunRecord:
    run_id = new_run_id()
    run_dir = Path(output_dir) if output_dir else paths.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunRecord(
        run_id=run_id,
        mode=mode,
        created_at=time.time(),
        input_dir="",
        output_dir=str(run_dir),
        options=options,
    )


def path_for(record: RunRecord) -> Path:
    return Path(record.output_dir) / "run.json"


def save(record: RunRecord) -> Path:
    """Atomic-ish write: temp file then replace, so a reader never sees a half file."""
    target = path_for(record)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target


def load(run_id_or_dir: str) -> RunRecord:
    """Load by run id (under ``data/runs``) or by an explicit directory path.

    The two forms are not interchangeable: a run started with ``-o`` keeps its record in
    that directory, not under ``data/runs``, so its id is not a handle for ``--run``.  The
    error says so, rather than reporting a path the caller never named.
    """
    candidate = Path(run_id_or_dir)
    by_path = candidate.is_dir() or "/" in run_id_or_dir
    target = (candidate / "run.json") if by_path else paths.runs_dir() / run_id_or_dir / "run.json"
    if not target.exists():
        if by_path:
            raise FileNotFoundError(f"no run.json in {candidate}")
        raise FileNotFoundError(
            f"no run {run_id_or_dir} under {paths.runs_dir()}; a run started with -o keeps "
            f"its record in that directory, so pass the directory to --run")
    return RunRecord.from_dict(json.loads(target.read_text(encoding="utf-8")))


def list_runs(limit: int = 20) -> list[RunRecord]:
    out: list[RunRecord] = []
    for directory in sorted(paths.runs_dir().iterdir(), reverse=True):
        record_file = directory / "run.json"
        if not record_file.exists():
            continue
        try:
            out.append(RunRecord.from_dict(json.loads(record_file.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, TypeError) as exc:
            log.warn(f"skipping unreadable {record_file}: {exc}")
        if len(out) >= limit:
            break
    return out



