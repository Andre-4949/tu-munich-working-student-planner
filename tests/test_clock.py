"""Interval merging."""

from __future__ import annotations

import unittest

from planner.clock import merge_intervals
from tests.helpers import at


class MergeTests(unittest.TestCase):
    def test_overlapping_and_touching_intervals_merge(self):
        self.assertEqual(merge_intervals([(at(14), at(16)), (at(10), at(12)), (at(11), at(13))]),
                         [(at(10), at(13)), (at(14), at(16))])
        self.assertEqual(merge_intervals([(600, 700), (700, 760)]), [(600, 760)])
