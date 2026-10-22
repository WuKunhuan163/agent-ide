"""How a file is cut into parts, and why the cut is decided once.

The endpoint fixes two things when an upload is created: how many parts a file may
have (a hard ceiling) and which part number each piece belongs to. The split
therefore has to be chosen before the first byte goes out — parts can be retried,
their boundaries cannot.

That constraint is what makes this module the place where "adaptive" has to be
defined precisely:

* the **piece size** adapts to the link speed, but only when a file is planned;
  an upload already in flight keeps its plan so that a resume can name the parts
  that are still missing;
* **parts go up one at a time, in order.** The endpoint is a sequential multipart
  store: part N is accepted only after N-1 is stored, so "in flight" is always 1
  per file. Parallel parts do not go faster, they get rejected — see SKILL.md,
  "What the endpoint actually requires".

Everything here is pure arithmetic over a `Plan`; no network, no threads, which is
why it can be tested without an account.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field

# Client-side amortisation floor, not a server limit. The endpoint's size floor is
# 100 KB (measured: 96 KB refused, 100 KB accepted by `complete`), and its count
# ceiling is 10000 (official CreateFile: "最多 10000 个分片").
MIN_CHUNK = 512 * 1024
MAX_PARTS = 10000
MIN_DOWNLOAD_CHUNK = 10 * 1024 * 1024
DEFAULT_THREADS = 10


@dataclass(frozen=True)
class TransferOptions:
    """Everything tunable, kept apart from the algorithm that consumes it.

    The algorithm below decides a chunk from (remaining bytes, part quota, measured
    speed, target_seconds). These are the inputs a caller may override, so tuning
    never means editing the decision code.

    `target_seconds` is the time one chunk should take; a chunk is
    `speed * target_seconds` bytes, floored by the quota. 1.0 is the value the
    archived dispatcher hard-coded.
    """

    min_chunk: int = MIN_CHUNK
    target_chunk: int = 0          # 0 = follow the measured speed
    target_seconds: float = 1.0    # how long one chunk should take; 1 was implicit
    max_concurrent_chunks: int = 1  # 1 = sequential parts, the endpoint's default
    max_threads: int = DEFAULT_THREADS


@dataclass
class Plan:
    """A fixed partition of one file, plus which parts are known to be done."""

    size: int
    parts: list[tuple[int, int]]
    completed: set[int] = field(default_factory=set)

    @property
    def part_count(self) -> int:
        return len(self.parts)

    @property
    def pending(self) -> list[int]:
        return [n for n in range(1, self.part_count + 1) if n not in self.completed]

    @property
    def done_bytes(self) -> int:
        return sum(
            self.parts[n - 1][1] - self.parts[n - 1][0] for n in self.completed
        )

    def span(self, part: int) -> tuple[int, int]:
        return self.parts[part - 1]


def make_plan(size: int, *, min_chunk: int = MIN_CHUNK, max_parts: int = MAX_PARTS,
              target_chunk: int | None = None) -> Plan:
    """Cut `size` into at most `max_parts` pieces of roughly `target_chunk` bytes.

    `max_parts` is the endpoint's ceiling, so the piece size has a floor:
    `ceil(size / max_parts)`. A target below that floor is raised to it, which is
    the only case where a very large file ends up with pieces larger than the link
    would prefer.
    """
    if size <= 0:
        return Plan(size=0, parts=[])
    floor = max(min_chunk, math.ceil(size / max_parts))
    chunk = max(floor, target_chunk or floor)
    parts: list[tuple[int, int]] = []
    start = 0
    while start < size:
        end = min(start + chunk, size)
        parts.append((start, end))
        start = end
    return Plan(size=size, parts=parts)


def plan_from_parts(size: int, spans: list[list[int]], completed: list[int]) -> Plan:
    """Rebuild a plan recorded by a previous run."""
    parts = [(int(a), int(b)) for a, b in spans]
    return Plan(size=size, parts=parts, completed={int(n) for n in completed})


class FileState:
    """One file in the shared pool: what is left, and which parts are in flight."""

    def __init__(self, file_key: str, total_size: int, *, min_chunk: int = MIN_CHUNK,
                 max_parts: int = MAX_PARTS, max_concurrent_chunks: int = 1) -> None:
        self.file_key = file_key
        self.total_size = total_size
        self.remaining_size = total_size
        quota = math.ceil(total_size / min_chunk) if min_chunk > 0 else 1
        self.remaining_parts_quota = min(quota, max_parts)
        self.active_chunks = 0
        self.max_concurrent_chunks = max_concurrent_chunks
        self.next_part_num = 1
        self.current_offset = 0
        self.min_required_chunk_size = min_chunk
        self.meta: dict = {}


class Dispatcher:
    """Claim one chunk at a time, from any file that has a free slot.

    This is the archived dispatcher: a single pool of threads, each calling
    `take()`. `max_concurrent_chunks` bounds how many chunks of the *same* file
    may be in flight, so the pool naturally spreads across files while an
    upload stays sequential (1) unless the endpoint is opened for parallel parts.
    """

    def __init__(self, initial_speed: int, options: TransferOptions | None = None) -> None:
        self.files: dict[str, FileState] = {}
        self.lock = threading.Lock()
        self.options = options or TransferOptions()
        self.expected_speed = float(initial_speed)
        self.min_chunk = self.options.min_chunk
        self.producer_done = False
        self.progress_lock = threading.Lock()
        self.done_bytes = 0
        self.on_progress = None

    def add(self, state: FileState) -> None:
        with self.lock:
            self.files[state.file_key] = state

    def take(self) -> tuple[str, dict | None]:
        with self.lock:
            free = [f for f in self.files.values()
                    if f.active_chunks < f.max_concurrent_chunks and f.remaining_size > 0]
            if not free:
                if all(f.remaining_size == 0 for f in self.files.values()) and self.producer_done:
                    return "DONE", None
                return "WAIT", None

            # Bytes one chunk should cover: the measured speed times the caller's
            # target_seconds. `--bs` overrides it with a fixed size.
            chunk_bytes = self.options.target_chunk or max(
                self.expected_speed * self.options.target_seconds, self.min_chunk
            )
            # Two chunks is the point where cutting one off still leaves a valid
            # tail; below it the remainder is merged whole.
            two_chunks = 2 * chunk_bytes
            for f in free:
                f.min_required_chunk_size = (
                    math.ceil(f.remaining_size / f.remaining_parts_quota)
                    if f.remaining_parts_quota > 0 else f.remaining_size
                )

            ideal = [f for f in free
                     if f.remaining_size >= two_chunks and f.min_required_chunk_size < chunk_bytes]
            if ideal:
                chosen = max(ideal, key=lambda f: f.remaining_size)
                chunk = chunk_bytes
            else:
                smallest = min(free, key=lambda f: f.min_required_chunk_size)
                floor = smallest.min_required_chunk_size
                largest = max(free, key=lambda f: f.remaining_size)
                ceiling = max(largest.remaining_size, 1)
                if floor / chunk_bytes > chunk_bytes / ceiling:
                    small = [f for f in free if f.remaining_size < two_chunks]
                    if small:
                        chosen = max(small, key=lambda f: f.remaining_size)
                        chunk = chosen.remaining_size
                    else:
                        chosen = largest
                        chunk = chunk_bytes
                else:
                    chosen = smallest
                    chunk = (chosen.remaining_size if chosen.remaining_size < two_chunks
                             else max(chunk_bytes, floor))

            if chunk < self.min_chunk or (chosen.remaining_size - chunk) < self.min_chunk:
                chunk = chosen.remaining_size
            if chunk < chosen.min_required_chunk_size:
                chunk = chosen.min_required_chunk_size
            # The first chunk is the only one sized without a measurement, so it
            # stays at the probe size instead of inheriting target_seconds. A 60 s
            # target would otherwise make the first chunk carry the initial guess
            # (512 KB/s * 60 = 30 MB) and outlive the upload url on a slow link.
            if (not self.options.target_chunk and chosen.next_part_num == 1
                    and chunk > self.min_chunk and chosen.remaining_size > self.min_chunk):
                chunk = self.min_chunk
            chunk = int(min(chunk, chosen.remaining_size))

            chosen.active_chunks += 1
            chosen.remaining_size -= chunk
            chosen.remaining_parts_quota -= 1
            task = {
                "file_key": chosen.file_key,
                "part_num": chosen.next_part_num,
                "offset": chosen.current_offset,
                "chunk_size": chunk,
                "meta": chosen.meta,
            }
            chosen.next_part_num += 1
            chosen.current_offset += chunk
            return "OK", task

    def done(self, file_key: str, speed: float) -> None:
        with self.lock:
            state = self.files.get(file_key)
            if state is None:
                return
            state.active_chunks -= 1
            if speed > 0:
                self.expected_speed = self.expected_speed * 0.7 + speed * 0.3

    def failed(self, file_key: str, chunk_size: int) -> None:
        with self.lock:
            state = self.files.get(file_key)
            if state is None:
                return
            state.active_chunks -= 1
            state.remaining_size += chunk_size
            state.remaining_parts_quota += 1
            state.current_offset -= chunk_size
            state.next_part_num -= 1

    def run(self, *, max_threads: int, worker, total_bytes: int) -> None:
        """Prime the speed estimate with one chunk, then fan out."""
        status, pivot = self.take()
        if status == "OK":
            started = time.monotonic()
            ok, size, speed = worker(pivot)
            if ok:
                speed = size / max(time.monotonic() - started, 0.001)
                self.expected_speed = speed
                self._advance(pivot["file_key"], size, speed, total_bytes)
            else:
                self.failed(pivot["file_key"], pivot["chunk_size"])

        def loop() -> None:
            while True:
                status, task = self.take()
                if status == "DONE":
                    return
                if status == "WAIT":
                    time.sleep(0.5)
                    continue
                ok, size, speed = worker(task)
                if ok:
                    self._advance(task["file_key"], size, speed, total_bytes)
                else:
                    self.failed(task["file_key"], task["chunk_size"])

        threads = [threading.Thread(target=loop, daemon=True) for _ in range(max_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def _advance(self, file_key: str, size: int, speed: float, total: int) -> None:
        self.done(file_key, speed)
        with self.progress_lock:
            self.done_bytes += size
            if self.on_progress:
                self.on_progress(self.done_bytes, total)
