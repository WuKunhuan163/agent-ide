"""The partition arithmetic, tested without an account or a network."""
from __future__ import annotations

import unittest

from src import scheduler


class MakePlanTest(unittest.TestCase):
    def test_parts_tile_the_file_exactly(self):
        plan = scheduler.make_plan(10_000_000, target_chunk=1_000_000)
        self.assertEqual(plan.parts[0][0], 0)
        self.assertEqual(plan.parts[-1][1], 10_000_000)
        for (_, end), (start, _) in zip(plan.parts, plan.parts[1:]):
            self.assertEqual(end, start)

    def test_part_count_never_exceeds_the_ceiling(self):
        plan = scheduler.make_plan(20 * 1024 ** 3, target_chunk=1024)
        self.assertLessEqual(plan.part_count, scheduler.MAX_PARTS)

    def test_ceiling_raises_the_piece_size(self):
        size = 20 * 1024 ** 3
        plan = scheduler.make_plan(size, target_chunk=1024)
        floor = -(-size // scheduler.MAX_PARTS)  # ceil
        # The last piece carries the remainder, so only the others must reach it.
        for start, end in plan.parts[:-1]:
            self.assertGreaterEqual(end - start, floor)

    def test_target_chunk_is_honoured_below_the_floor(self):
        plan = scheduler.make_plan(4 * 1024 * 1024, target_chunk=1024 * 1024)
        self.assertEqual(plan.part_count, 4)

    def test_empty_file_has_no_parts(self):
        plan = scheduler.make_plan(0)
        self.assertEqual(plan.part_count, 0)
        self.assertEqual(plan.pending, [])

    def test_completed_parts_are_skipped(self):
        plan = scheduler.make_plan(4 * 1024 * 1024, target_chunk=1024 * 1024)
        plan.completed = {1, 2}
        self.assertEqual(plan.pending, [3, 4])
        self.assertEqual(plan.done_bytes, 2 * 1024 * 1024)


class ResumeTest(unittest.TestCase):
    def test_rebuilding_keeps_boundaries_and_progress(self):
        original = scheduler.make_plan(3 * 1024 * 1024, target_chunk=1024 * 1024)
        rebuilt = scheduler.plan_from_parts(
            original.size, [[a, b] for a, b in original.parts], [1, 3]
        )
        self.assertEqual(rebuilt.parts, original.parts)
        self.assertEqual(rebuilt.pending, [2])
        self.assertEqual(rebuilt.done_bytes, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
