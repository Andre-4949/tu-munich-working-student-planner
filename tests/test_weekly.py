"""The weekly choice of days."""

from __future__ import annotations

import unittest

from planner.days import day_candidates
from tests.helpers import MONDAY, SUNDAY, at, make_config
from planner.planning import build_plan
from planner.weekly import select_week


class SelectWeekTests(unittest.TestCase):
    def week_events(self, lectures_by_day):
        events = []
        for day, lectures in lectures_by_day.items():
            for start, end in lectures:
                events.append({"date": day.isoformat(), "start_min": start, "end_min": end,
                               "skipped": False})
        return events

    def test_target_is_reached_with_the_fewest_company_days(self):
        # Five free days: one day of 9h20 is not enough for 10h, so two days of 5h each are
        # planned (two days of travel) instead of three (three days of travel).
        cfg = make_config(schedule={"weekly_target_hours": 10, "min_time_at_company": 120})
        cands = [day_candidates(MONDAY.replace(day=7 + i), [], cfg) for i in range(5)]
        chosen = select_week(cands, 600, 600, 120)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(sum(work for _, _, work in chosen.values()), 600)

    def test_no_target_means_no_planned_days(self):
        cfg = make_config()
        events = self.week_events({MONDAY: [(at(10), at(12))]})
        built = build_plan(events, cfg, MONDAY, MONDAY)
        self.assertEqual(built.weeks[0].planned, 0)
        self.assertTrue(all(d.status != "planned" for d in built.weeks[0].days))

    def test_planned_and_fallback_days_do_not_overlap(self):
        cfg = make_config(schedule={"weekly_target_hours": 10, "min_time_at_company": 120})
        events = self.week_events({MONDAY: [(at(10), at(12))]})
        built = build_plan(events, cfg, MONDAY, SUNDAY)
        week = built.weeks[0]
        planned = {d.day for d in week.days if d.status == "planned"}
        fallback = {d.day for d in week.days if d.status == "fallback"}
        self.assertFalse(planned & fallback)
        self.assertGreaterEqual(week.planned, 600)
        self.assertGreater(len(fallback), 0)

    def test_limit_is_never_exceeded(self):
        cfg = make_config(schedule={"weekly_target_hours": 10, "max_hours_per_week": 10,
                                    "min_time_at_company": 120})
        events = self.week_events({MONDAY: [(at(10), at(12))]})
        built = build_plan(events, cfg, MONDAY, SUNDAY)
        self.assertLessEqual(built.weeks[0].planned, 600)
