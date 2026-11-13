"""Timing of visits in one stretch of a day."""

from __future__ import annotations

import unittest

from planner.clock import merge_intervals
from planner.constants import CAR, HOME, JOB, TRANSIT, TUM
from tests.helpers import CAR_TABLE, FRIDAY, MONDAY, at, make_config, transit_windows
from planner.timing import GapSpec, schedule_gap


class TransitSlotRulesTests(unittest.TestCase):
    """The rules of the first version, now expressed as the direct transit route."""

    def test_free_day_visit_runs_from_earliest_arrival_to_latest(self):
        self.assertEqual(transit_windows(MONDAY, [], make_config()), [(at(7, 40), at(17))])

    def test_gap_between_lectures(self):
        cfg = make_config()
        windows = transit_windows(MONDAY, [(at(10), at(12)), (at(14), at(16))], cfg)
        # morning 07:40-09:30, between 12:30-13:30 (exactly 60 min), evening 16:30-17:00 is dropped
        self.assertEqual(windows, [(at(7, 40), at(9, 30)), (at(12, 30), at(13, 30)), None])

    def test_minimum_is_inclusive(self):
        cfg_60 = make_config(schedule={"min_time_at_company": 60})
        cfg_61 = make_config(schedule={"min_time_at_company": 61})
        lectures = [(at(10), at(12)), (at(14), at(16))]
        self.assertIsNotNone(transit_windows(MONDAY, lectures, cfg_60)[1])
        self.assertIsNone(transit_windows(MONDAY, lectures, cfg_61)[1])

    def test_lecture_at_eight_makes_morning_impossible(self):
        self.assertEqual(transit_windows(MONDAY, [(at(8), at(10))], make_config()),
                         [None, (at(10, 30), at(17))])

    def test_early_wake_up_makes_the_morning_possible(self):
        cfg = make_config(schedule={"earliest_wake_up": "05:00"})
        self.assertEqual(transit_windows(MONDAY, [(at(8), at(10))], cfg)[0], (at(6, 10), at(7, 30)))

    def test_late_wake_up_removes_the_morning(self):
        cfg = make_config(schedule={"earliest_wake_up": "06:45"})
        self.assertEqual(transit_windows(MONDAY, [(at(8), at(9))], cfg)[0], None)

    def test_lecture_past_latest_removes_the_evening(self):
        windows = transit_windows(MONDAY, [(at(15), at(18, 20))], make_config())
        self.assertEqual(windows, [(at(7, 40), at(14, 30)), None])

    def test_first_lecture_after_latest_clips_morning_to_latest(self):
        windows = transit_windows(MONDAY, [(at(18), at(19))], make_config())
        self.assertEqual(windows[0], (at(7, 40), at(17)))

    def test_overlapping_lectures_are_merged(self):
        lectures = [(at(10), at(11)), (at(10, 30), at(12)), (at(12), at(13))]
        windows = transit_windows(MONDAY, lectures, make_config())
        # one block 10:00-13:00: morning 07:40-09:30, evening 13:30-17:00
        self.assertEqual(windows, [(at(7, 40), at(9, 30)), (at(13, 30), at(17))])
        self.assertEqual(len(merge_intervals(lectures)), 1)

    def test_earliest_at_job_clips_the_start(self):
        cfg = make_config(schedule={"earliest_at_job": "08:00"})
        self.assertEqual(transit_windows(MONDAY, [], cfg), [(at(8), at(17))])

    def test_max_shift_caps_the_block(self):
        cfg = make_config(schedule={"max_shift_minutes": 200})
        self.assertEqual(transit_windows(MONDAY, [], cfg), [(at(7, 40), at(7, 40) + 200)])

    def test_buffer_is_applied_next_to_lectures(self):
        cfg = make_config(schedule={"buffer_minutes": 10})
        windows = transit_windows(MONDAY, [(at(10), at(12)), (at(14), at(16))], cfg)
        # morning ends at 10:00-30-10 = 09:20; between is 40 min and dropped; evening is 20 min
        self.assertEqual(windows, [(at(7, 40), at(9, 20)), None, None])

    def test_ready_minutes_move_the_morning_start(self):
        cfg = make_config(schedule={"ready_minutes": 30})
        self.assertEqual(transit_windows(MONDAY, [], cfg), [(at(8, 10), at(17))])

    def test_day_override_changes_latest_for_that_weekday_only(self):
        cfg = make_config(day_overrides={"fri": {"latest_at_job": "14:00"}})
        self.assertEqual(transit_windows(FRIDAY, [], cfg), [(at(7, 40), at(14))])
        self.assertEqual(transit_windows(MONDAY, [], cfg), [(at(7, 40), at(17))])


class ScheduleGapTests(unittest.TestCase):
    def test_visit_is_as_long_as_the_window_allows(self):
        cfg = make_config()
        spec = GapSpec(TUM, TUM, at(12), at(14))
        legs = ((TUM, JOB, TRANSIT), (JOB, TUM, TRANSIT))
        gap = schedule_gap(MONDAY, spec, legs, cfg, 0, 1020)
        self.assertEqual(gap.visit, (at(12, 30), at(13, 30)))
        self.assertEqual([(l.start, l.end) for l in gap.legs],
                         [(at(12), at(12, 30)), (at(13, 30), at(14))])

    def test_shortened_visit_leaves_later_and_keeps_legs_timed(self):
        cfg = make_config()
        spec = GapSpec(TUM, TUM, at(12), at(14))
        legs = ((TUM, JOB, TRANSIT), (JOB, TUM, TRANSIT))
        gap = schedule_gap(MONDAY, spec, legs, cfg, 0, 1020, visit_len=120)
        self.assertEqual(gap.visit, (at(12, 30), at(14, 30)))  # arrive 12:30, 120 min at the job

    def test_car_is_faster_from_home(self):
        cfg = make_config(car=CAR_TABLE)
        spec = GapSpec(HOME, HOME, at(6, 30), None)
        car_gap = schedule_gap(MONDAY, spec, ((HOME, JOB, CAR), (JOB, HOME, CAR)), cfg, 0, 1020)
        bus_gap = schedule_gap(MONDAY, spec, ((HOME, JOB, TRANSIT), (JOB, HOME, TRANSIT)), cfg, 0, 1020)
        self.assertEqual(car_gap.visit[0], at(6, 30) + 45)
        self.assertEqual(bus_gap.visit[0], at(6, 30) + 70)
