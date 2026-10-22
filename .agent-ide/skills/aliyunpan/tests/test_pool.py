"""The upload pool driven by a fake endpoint: concurrency, gating, retry.

No account, no network. Every PUT sleeps `size / RATE`, so the dispatcher's own
speed probe and EWMA see a consistent link and cut chunks exactly as they would
against the real endpoint. Each case asserts one property of the pool instead of
printing a timeline.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from src import scheduler, transfer
from src.errors import PanError

AGENT = "test-pool"
RATE = 4 * 1024 * 1024  # simulated link, bytes per second
KB = 1024
SIZE = 1024 * KB  # above the 512 KB floor, so the pool has something to cut


class FakeSession:
    """Answers the three calls upload_many makes and stores parts slowly."""

    def __init__(self, rate: int = RATE) -> None:
        self.rate = rate
        self.lock = threading.Lock()
        self.puts: list[tuple[str, int, int, float, float]] = []
        self.completes: list[str] = []
        self.fail_once: dict[tuple[str, int], int] = {}
        self.failures = 0

    def call(self, endpoint: str, payload: dict, timeout: int = 15) -> dict:
        if endpoint == "create":
            return {"file_id": f"fid-{payload['name']}", "upload_id": "uid",
                    "rapid_upload": False}
        if endpoint == "getUploadUrl":
            part = payload["part_info_list"][0]["part_number"]
            return {"part_info_list": [{"part_number": part,
                                        "upload_url": f"https://fake/{payload['file_id']}/{part}"}]}
        if endpoint == "complete":
            self.completes.append(payload["file_id"])
            return {}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    def put(self, url: str, body: bytes, timeout: int = 120) -> None:
        _, file_id, part_text = url.rsplit("/", 2)
        part = int(part_text)
        with self.lock:
            left = self.fail_once.get((file_id, part), 0)
            if left:
                self.fail_once[(file_id, part)] = left - 1
                self.failures += 1
                raise PanError("part upload: HTTP 500 injected")
        started = time.monotonic()
        time.sleep(len(body) / self.rate)
        ended = time.monotonic()
        with self.lock:
            self.puts.append((file_id, part, len(body), started, ended))


@contextmanager
def endpoint():
    """Replace the two remote lookups upload_many performs before transferring."""
    with mock.patch.object(transfer.remote, "resolve", return_value="parent"), \
         mock.patch.object(transfer.remote, "assert_free", return_value=None):
        yield


def peak_concurrency(session: FakeSession) -> int:
    events = []
    for _, _, _, started, ended in session.puts:
        events.append((started, 1))
        events.append((ended, -1))
    events.sort()
    peak = current = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


class UploadPoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = Path(__file__).resolve().parents[1] / "data" / AGENT
        shutil.rmtree(self.state, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.state, ignore_errors=True)

    def run_case(self, *sizes: int, options: scheduler.TransferOptions | None = None,
                 fail_part: int | None = None) -> tuple[FakeSession, list[dict]]:
        paths = []
        for index, size in enumerate(sizes):
            path = self.tmp / f"case{index}_{size}.bin"
            path.write_bytes(os.urandom(size))
            paths.append(path)
        session = FakeSession()
        if fail_part:
            session.fail_once = {(f"fid-{paths[0].name}", fail_part): 1}
        with endpoint():
            results = transfer.upload_many(
                session, AGENT, [(p, "/pool") for p in paths],
                options=options or scheduler.TransferOptions(),
            )
        return session, results

    def test_defaults_never_overlap_parts_of_one_file(self):
        session, results = self.run_case(SIZE)
        self.assertEqual(peak_concurrency(session), 1)
        self.assertEqual(len(session.completes), 1)
        self.assertEqual(sum(p[2] for p in session.puts), SIZE)
        self.assertEqual(results[0]["bytes"], SIZE)

    def test_pool_spreads_across_files(self):
        session, _ = self.run_case(*([SIZE] * 3),
                                   options=scheduler.TransferOptions(max_threads=10))
        self.assertGreater(peak_concurrency(session), 1)
        self.assertEqual(len(session.completes), 3)
        self.assertEqual(sum(p[2] for p in session.puts), 3 * SIZE)

    def test_target_chunk_cuts_finer(self):
        plain, _ = self.run_case(SIZE)
        fixed, _ = self.run_case(SIZE, options=scheduler.TransferOptions(
            min_chunk=256 * KB, target_chunk=256 * KB))
        self.assertEqual(len(fixed.puts), 4)
        self.assertGreater(len(fixed.puts), len(plain.puts))

    def test_gate_allows_two_parts_in_flight(self):
        session, _ = self.run_case(SIZE, options=scheduler.TransferOptions(
            min_chunk=256 * KB, target_chunk=256 * KB, max_concurrent_chunks=2))
        self.assertEqual(peak_concurrency(session), 2)
        self.assertEqual(sum(p[2] for p in session.puts), SIZE)

    def test_failed_part_is_resent_not_replaced(self):
        fine = scheduler.TransferOptions(min_chunk=256 * KB, target_chunk=256 * KB)
        clean, _ = self.run_case(SIZE, options=fine)
        session, results = self.run_case(SIZE, options=fine, fail_part=2)
        self.assertEqual(session.failures, 1)
        self.assertEqual(len(session.puts), len(clean.puts))
        self.assertEqual(results[0]["bytes"], SIZE)
        self.assertEqual(len(session.completes), 1)


if __name__ == "__main__":
    unittest.main()
