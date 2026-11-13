"""The options of one day."""

from __future__ import annotations

import unittest
from datetime import date

from planner.constants import CAR
from planner.days import day_candidates
from tests.helpers import CAR_TABLE, FRIDAY, MONDAY, at, make_config


class DayCandidateTests(unittest.TestCase):
    def test_short_gap_with_buffer_still_has_a_commute_baseline(self):
        # 14:00-14:15 between two lectures, with a 10 min buffer: no visit fits,
        # but the day still needs its commute, so the baseline must exist
        cfg = make_config(schedule={"buffer_minutes": 10})
        cand = day_candidates(MONDAY, [(at(10), at(14)), (at(14, 15), at(15, 45))], cfg)
        self.assertIsNotNone(cand.baseline)
        self.assertEqual(cand.baseline.travel, 80)  # transit 40 + 40

    def test_free_day_prefers_the_car_from_home(self):
        cfg = make_config(car=CAR_TABLE)
        cand = day_candidates(MONDAY, [], cfg)
        best = min(cand.visits, key=lambda o: o.travel)
        self.assertEqual(best.modes, "car")
        self.assertEqual(best.travel, 90)

    def test_baseline_is_the_cheapest_commute_without_work(self):
        cfg = make_config(car=CAR_TABLE)
        cand = day_candidates(MONDAY, [(at(10), at(12))], cfg)
        # commute without work: by car 25 + 25 is cheaper than by transit 40 + 40
        self.assertEqual(cand.baseline.travel, 50)
        self.assertEqual(cand.baseline.modes, "car")
        self.assertEqual(cand.baseline.extra, 0)
        for option in cand.visits:
            self.assertGreaterEqual(option.extra, 0)
            self.assertEqual(option.cost, option.extra)  # no flat penalty: cost is the day's extra travel

    def test_split_day_with_car_starts_with_work_from_home(self):
        cfg = make_config(car=CAR_TABLE)
        cand = day_candidates(MONDAY, [(at(14), at(16))], cfg)
        cheapest = cand.visits[0]
        self.assertEqual(cheapest.visits[0][0], at(6, 30) + 45)  # arrival by car from home
        self.assertEqual(cheapest.legs[0].mode, CAR)

    def test_company_closed_day_has_no_visit(self):
        cfg = make_config(holidays={"company_closed": ["2026-12-07"]})
        self.assertEqual(day_candidates(MONDAY, [], cfg).visits, [])

    def test_weekend_is_not_a_work_day(self):
        cfg = make_config()
        self.assertEqual(day_candidates(date(2026, 12, 12), [], cfg).visits, [])

    def test_timed_block_means_no_work_before_it_ends(self):
        # an exam 10:00-10:30 on Monday: no visit may arrive before 10:30 that day, Friday is unaffected
        cfg = make_config(holidays={"no_work_durations": ["2026-12-07 10:00..10:30"]})
        monday = day_candidates(MONDAY, [], cfg)
        self.assertTrue(monday.visits)
        self.assertGreaterEqual(min(arrive for o in monday.visits for arrive, _ in o.visits), at(10, 30))
        friday = day_candidates(FRIDAY, [], cfg)
        self.assertLess(min(arrive for o in friday.visits for arrive, _ in o.visits), at(10, 30))

    def test_timed_block_before_a_lecture_keeps_the_morning_commute(self):
        # the exam is followed by a lecture at 12:00: a visit between 10:30 and the lecture still fits
        cfg = make_config(holidays={"no_work_durations": ["2026-12-07 10:00..10:30"]})
        cand = day_candidates(MONDAY, [(at(12), at(13))], cfg)
        self.assertTrue(cand.visits)
        self.assertTrue(all(arrive >= at(10, 30) for o in cand.visits for arrive, _ in o.visits))
