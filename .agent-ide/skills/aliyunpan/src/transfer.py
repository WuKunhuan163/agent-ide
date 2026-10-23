"""Upload and download, resumable from disk.

Upload is a single pool of threads over a shared claim list, the shape the
archived dispatcher had: every thread calls `Dispatcher.take()` and gets
`{file_key, part_num, offset, chunk_size}` — one chunk, not one file. The only
gate between chunks of the same file is `max_concurrent_chunks`, which is 1 for
uploads because the endpoint stores parts sequentially: part N is refused with
`PartNotSequential` unless N-1 is stored. Threads therefore spread across files
and never race inside one.

* **a fresh `getUploadUrl` immediately before every PUT.** The call re-signs, so
  a url held from `create` starts failing with `SignatureDoesNotMatch`.
* **chunk size is `measured speed * target_seconds`** (default 1.0 s), floored by
  the part quota and merged into the last piece when the remainder would fall
  under the minimum. The first chunk doubles as the speed probe, so it is sized
  from the initial guess rather than a measurement.
* **a failed chunk is rolled back**, keeping the same part number and offset, so
  the retry asks for the same range and the endpoint never sees a gap.

Resume state is the offset and the next part number, keyed by content hash and
size; a killed run continues from that pair instead of restarting the file.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from . import paths

from . import remote, scheduler
from .errors import PanError, TransferFailed
from .paths import resume_path
from .session import Session

MIN_CHUNK = scheduler.MIN_CHUNK
MAX_PARTS = scheduler.MAX_PARTS
CHUNK_RETRIES = 3
FILE_GIVE_UP = 6


def sha1_of(path: Path, chunk: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def upload(session: Session, agent_id: str, local: Path, remote_dir: str) -> dict:
    """One file, one entry point: the pool is still shared, it just has one member."""
    return upload_many(session, agent_id, [(local, remote_dir)])[0]


def upload_many(session: Session, agent_id: str, pairs: list[tuple[Path, str]],
                *, options: scheduler.TransferOptions | None = None) -> list[dict]:
    if not pairs:
        return []
    options = options or scheduler.TransferOptions()

    parents: dict[str, str] = {}
    states: list[scheduler.FileState] = []
    for local, remote_dir in pairs:
        if remote_dir not in parents:
            parents[remote_dir] = remote.resolve(session, remote_dir, create=True)
        remote.assert_free(session, parents[remote_dir], [local.name])
        size = local.stat().st_size
        state = scheduler.FileState(
            str(local), size,
            min_chunk=options.min_chunk,
            max_parts=MAX_PARTS,
            max_concurrent_chunks=options.max_concurrent_chunks,
        )
        state.meta.update({
            "local": local,
            "parent": parents[remote_dir],
            "digest": "",
            "file_id": "",
            "upload_id": "",
            "rapid": False,
            "fatal": "",
            "failures": 0,
        })
        states.append(state)

    # The smallest file goes first and its first chunk measures the link.
    states.sort(key=lambda s: s.total_size)
    pivot = states[0]

    def prepare(state: scheduler.FileState) -> None:
        local: Path = state.meta["local"]
        digest = sha1_of(local)
        state.meta["digest"] = digest
        key = _key(digest, state.total_size)
        state.meta["resume_key"] = key
        saved = _load(agent_id, key)
        if saved is None:
            saved = _create(session, agent_id, key, local, state.meta["parent"], digest,
                            state.remaining_parts_quota)
        state.meta["file_id"] = saved["file_id"]
        state.meta["upload_id"] = saved["upload_id"]
        state.meta["rapid"] = bool(saved.get("rapid"))
        state.meta["quota"] = int(saved.get("quota") or 1)
        if state.meta["rapid"]:
            state.remaining_size = 0
            state.remaining_parts_quota = 0
            return
        # Only a run that stopped cleanly can be resumed: the parts it recorded
        # are exactly the ones the endpoint has, and parts cannot be overwritten.
        offset = int(saved.get("offset") or 0)
        part = int(saved.get("part") or 1)
        if 0 < offset < state.total_size and part > 1:
            state.current_offset = offset
            state.next_part_num = part
            state.remaining_size = state.total_size - offset
            state.remaining_parts_quota = max(1, int(saved.get("quota") or 1))
            state.meta["resumed"] = offset

    prepare(pivot)
    initial = state_uploaded(pivot)
    dispatcher = scheduler.Dispatcher(initial_speed=options.min_chunk, options=options)
    if pivot.remaining_size > 0:
        dispatcher.add(pivot)

    def producer() -> None:
        for state in states:
            if state is pivot:
                continue
            try:
                prepare(state)
            except PanError as exc:
                state.meta["fatal"] = str(exc)
                continue
            if state.remaining_size > 0:
                dispatcher.add(state)
        dispatcher.producer_done = True

    producer_thread = threading.Thread(target=producer, name="producer", daemon=True)
    producer_thread.start()

    def worker(task: dict):
        meta = task["meta"]
        part = task["part_num"]
        size = task["chunk_size"]
        if meta["fatal"]:
            return False, size, 0.0
        local: Path = meta["local"]
        try:
            with open(local, "rb") as handle:
                handle.seek(task["offset"])
                body = handle.read(size)
        except OSError as exc:
            meta["fatal"] = str(exc)
            return False, size, 0.0

        started = time.monotonic()
        for attempt in range(1, CHUNK_RETRIES + 1):
            try:
                session.put(_upload_url(session, meta, part), body)
                elapsed = max(time.monotonic() - started, 0.001)
                _say(f"part {part} {len(body)}B {elapsed:.1f}s "
                     f"({len(body) / elapsed / 1024:.1f} kB/s)")
                meta["quota"] = max(meta["quota"] - 1, 1)
                _save(agent_id, meta["resume_key"], {
                    "size": meta["local"].stat().st_size,
                    "offset": task["offset"] + len(body),
                    "part": part + 1,
                    "quota": meta["quota"],
                    "file_id": meta["file_id"],
                    "upload_id": meta["upload_id"],
                    "rapid": False,
                })
                return True, len(body), len(body) / elapsed
            except PanError as exc:
                if _permanent(exc) or attempt == CHUNK_RETRIES:
                    meta["failures"] = meta["failures"] + 1
                    _say(f"part {part} failed: {exc}")
                    if meta["failures"] >= FILE_GIVE_UP:
                        meta["fatal"] = f"part {part}: {exc}"
                    return False, size, 0.0
                _say(f"part {part} attempt {attempt} failed: {exc}; retrying")
                time.sleep(attempt)
        return False, size, 0.0

    total = sum(s.total_size for s in states)
    dispatcher.run(max_threads=options.max_threads, worker=worker, total_bytes=total)
    producer_thread.join()

    results = []
    fatal = ""
    for state in states:
        meta = state.meta
        if meta["fatal"]:
            fatal = fatal or f"{meta['local'].name}: {meta['fatal']}"
            continue
        if meta["rapid"]:
            _clear(agent_id, meta["resume_key"])
            results.append({"file": str(meta["local"]), "bytes": state.total_size,
                            "parts": 0, "resumed": 0, "rapid": True})
            continue
        session.call("complete", {"file_id": meta["file_id"], "upload_id": meta["upload_id"]})
        _clear(agent_id, meta["resume_key"])
        results.append({
            "file": str(meta["local"]),
            "bytes": state.total_size,
            "parts": state.next_part_num - 1,
            "resumed": round(meta.get("resumed", 0) / state.total_size, 3) if state.total_size else 0,
            "rapid": False,
        })
    if fatal:
        raise TransferFailed(fatal)
    return results


def state_uploaded(state: scheduler.FileState) -> int:
    return int(state.meta.get("resumed") or 0)


def _create(session: Session, agent_id: str, key: str, local: Path,
            parent: str, digest: str, quota: int) -> dict:
    size = local.stat().st_size
    body = session.call(
        "create",
        {
            "parent_file_id": parent,
            "name": local.name,
            "type": "file",
            "size": size,
            "content_hash": digest,
            "content_hash_name": "sha1",
            "check_name_mode": "refuse",
            "part_info_list": [{"part_number": n} for n in range(1, max(quota, 1) + 1)],
        },
    )
    state = {
        "size": size,
        "offset": 0,
        "part": 1,
        "quota": max(quota, 1),
        "file_id": body.get("file_id") or "",
        "upload_id": body.get("upload_id") or "",
        "rapid": bool(body.get("rapid_upload")),
    }
    if not state["file_id"] and not state["rapid"]:
        raise TransferFailed(f"create returned no file_id for {local.name}")
    _save(agent_id, key, state)
    return state


def _say(line: str) -> None:
    # Progress goes to stderr and stdout stays clean, as the CLI contract says.
    print(line, file=sys.stderr, flush=True)


def _permanent(exc: PanError) -> bool:
    """Errors that a retry cannot fix: the request itself is wrong."""
    text = str(exc)
    return any(f"HTTP {code}" in text for code in (400, 403, 409))


def _key(digest: str, size: int) -> str:
    return f"{digest[:16]}-{size}"


def download(session: Session, remote_file: str, local_dir: str, *, force: bool = False) -> dict:
    item = remote.stat(session, remote_file)
    if item.get("type") == "folder":
        raise TransferFailed(f"{remote_file} is a folder; download its files individually")
    size = int(item.get("size") or 0)
    target = paths.resolve_arg(local_dir) / item["name"]
    if target.exists() and not force:
        raise TransferFailed(f"{target} exists; pass --force to replace it")
    target.parent.mkdir(parents=True, exist_ok=True)

    url = remote.download_url(session, item["file_id"])
    chunk = max(scheduler.MIN_DOWNLOAD_CHUNK, size // 64 or 1)
    plan = scheduler.make_plan(size, min_chunk=chunk, max_parts=64)
    with open(target, "wb") as handle:
        handle.truncate(size)

    whole = threading.Event()

    def fetch(part: int) -> None:
        if whole.is_set():
            return
        start, end = plan.span(part)
        try:
            response = session.http.get(
                url, headers={"Range": f"bytes={start}-{end - 1}"}, timeout=300
            )
        except requests.RequestException as exc:
            raise PanError(f"range {start}-{end - 1}: {type(exc).__name__}: {exc}")
        if response.status_code == 200:
            # The endpoint ignored Range and sent the whole file. It can only be
            # placed at offset 0; writing it at any other offset would corrupt the
            # file silently, which is worse than failing.
            if start != 0 or (size and len(response.content) != size):
                raise PanError(
                    f"server answered with the whole file ({len(response.content)}B) "
                    f"for bytes={start}-{end - 1}"
                )
            with open(target, "r+b") as handle:
                handle.seek(0)
                handle.write(response.content)
            whole.set()
            return
        if response.status_code != 206:
            raise PanError(f"range {start}-{end - 1}: HTTP {response.status_code}")
        if len(response.content) != end - start:
            raise PanError(
                f"range {start}-{end - 1}: got {len(response.content)}B, expected {end - start}B"
            )
        with open(target, "r+b") as handle:
            handle.seek(start)
            handle.write(response.content)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, n) for n in plan.pending]
        for future in as_completed(futures):
            future.result()

    written = target.stat().st_size
    if size and written != size:
        raise TransferFailed(f"{target} is {written} bytes, expected {size}")
    return {"file": str(target), "bytes": written}


# --------------------------------------------------------------------- helpers


def _upload_url(session: Session, meta: dict, part: int) -> str:
    body = session.call(
        "getUploadUrl",
        {
            "file_id": meta["file_id"],
            "upload_id": meta["upload_id"],
            "part_info_list": [{"part_number": part}],
        },
    )
    items = body.get("part_info_list") or []
    if not items or not items[0].get("upload_url"):
        raise TransferFailed(f"no upload url for part {part}")
    return items[0]["upload_url"]


def _load(agent_id: str, key: str) -> dict | None:
    path = resume_path(agent_id, key)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not data.get("file_id") or not data.get("upload_id"):
        return None
    return data


def _save(agent_id: str, key: str, state: dict) -> None:
    path = resume_path(agent_id, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: v for k, v in state.items() if not k.startswith("_")}, ensure_ascii=False),
        encoding="utf-8",
    )


def _clear(agent_id: str, key: str) -> None:
    try:
        os.remove(resume_path(agent_id, key))
    except OSError:
        pass
