"""Break and work time."""

from __future__ import annotations

import unittest
from datetime import date

from planner.days import day_candidates
from planner.errors import ConfigError
from tests.helpers import MONDAY, make_config
from planner.weekly import select_week


class BreakTests(unittest.TestCase):
    def test_break_is_not_paid_work(self):
        cfg = make_config(schedule={"break_minutes": 30})
        best = min(day_candidates(MONDAY, [], cfg).visits, key=lambda o: o.travel)
        self.assertEqual(best.visit_minutes, 560)  # 07:40 to 17:00 at the job
        self.assertEqual(best.work, 530)

    def test_max_shift_is_work_time_so_the_visit_gets_the_break_on_top(self):
        cfg = make_config(schedule={"break_minutes": 30, "max_shift_minutes": 200})
        best = min(day_candidates(MONDAY, [], cfg).visits, key=lambda o: o.travel)
        self.assertEqual(best.visit_minutes, 230)
        self.assertEqual(best.work, 200)

    def test_weekly_target_counts_work_not_visit_time(self):
        cfg = make_config(schedule={"break_minutes": 30, "min_time_at_company": 120})
        cands = [day_candidates(date(2026, 12, 7 + i), [], cfg) for i in range(5)]
        chosen = select_week(cands, 600, 600, 120, 30)
        self.assertEqual(sum(work for _, _, work in chosen.values()), 600)
        for option, visit, work in chosen.values():
            self.assertEqual(visit - work, 30)  # every visit keeps its break

    def test_break_longer_than_the_minimum_visit_is_rejected(self):
        with self.assertRaisesRegex(ConfigError, "break_minutes"):
            make_config(schedule={"break_minutes": 150})
