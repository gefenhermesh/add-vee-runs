"""Tests for campaign/scout/scout_queue.py. Run: python -m unittest campaign/scout/test_scout_queue.py"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scout_queue as sq  # noqa: E402


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(sq, "known", return_value={"bay"})
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_add_merges_and_skips_known(self):
        q = {"items": []}
        self.assertIsNone(sq.add(q, "Bay", "x"))
        sq.add(q, "Mavria", "next_play", today="2026-11-22")
        sq.add(q, "Mavria Inc", "firgun", trigger_date="2026-11-10", today="2026-11-22")
        self.assertEqual(len(q["items"]), 1)
        self.assertEqual(q["items"][0]["sources"], ["next_play", "firgun"])

    def test_batch_order_b2b_fresh_then_oldest(self):
        q = {"items": []}
        sq.add(q, "Old B2B", "s", today="2026-10-01")
        sq.add(q, "Fresh B2B", "s", trigger_date="2026-11-15", today="2026-11-20")
        sq.add(q, "Consumer", "s", b2b=False, trigger_date="2026-11-20", today="2026-09-01")
        names = [it["name"] for it in sq.batch(q, 3, today="2026-11-22")]
        self.assertEqual(names, ["Fresh B2B", "Old B2B", "Consumer"])
        self.assertEqual(sq.batch(q, 3, today="2026-11-22"), [])


if __name__ == "__main__":
    unittest.main()
