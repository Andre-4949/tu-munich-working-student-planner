import contextlib
import io
import json
import sys
import tempfile
import tomllib
import unittest
import unittest.mock
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plan  # noqa: E402
from plan import (CAR, HOME, JOB, TRANSIT, TUM, ConfigError, GapSpec, config_from_dict,  # noqa: E402
                  day_candidates, enumerate_walks, merge_intervals, schedule_gap, select_week)

MONDAY = date(2026, 12, 7)
FRIDAY = date(2026, 12, 11)
SUNDAY = date(2026, 12, 13)
CAR_HOME = "home"
CAR_OUT = "out"


def make_config(schedule=None, travel=None, car=None, lectures=None, holidays=None,
                day_overrides=None, calendar=None):
    """Config with the test values: transit home->TUM 40, TUM->job 30, job->TUM 30, home->job 70,
    job->home 70; wake 06:30; latest 17:00; minimum 60 minutes; no buffer."""
    raw = {
        "travel": {"home_to_tum": 40, "tum_to_job": 30, **(travel or {})},
        "schedule": {"earliest_wake_up": "06:30", "latest_at_job": "17:00",
                     "min_time_at_company": 60, **(schedule or {})},
    }
    if car is not None:
        raw["car"] = car
    for key, value in (("lectures", lectures), ("holidays", holidays),
                       ("day_overrides", day_overrides), ("calendar", calendar)):
        if value is not None:
            raw[key] = value
    return config_from_dict(raw)


CAR_TABLE = {"home_to_tum": 25, "home_to_job": 45, "tum_to_job": 45}


def at(hours, minutes=0):
    return hours * 60 + minutes


def direct_transit_visit(day, spec, cfg):
    """The single visit on the direct transit route of one stretch (the old slot rules)."""
    if spec.src == HOME and spec.end == HOME:
        legs = [(HOME, JOB, TRANSIT), (JOB, HOME, TRANSIT)]
    elif spec.src == HOME:
        legs = [(HOME, JOB, TRANSIT), (JOB, TUM, TRANSIT)]
    elif spec.end == HOME:
        legs = [(TUM, JOB, TRANSIT), (JOB, HOME, TRANSIT)]
    else:
        legs = [(TUM, JOB, TRANSIT), (JOB, TUM, TRANSIT)]
    opening, latest = plan.day_limits(day, cfg)
    gap = schedule_gap(day, spec, tuple(legs), cfg, opening, latest)
    return None if gap is None else gap.visit


def transit_windows(day, lectures, cfg):
    """Visit windows of a day when only the direct transit routes are used."""
    specs = plan.build_specs(merge_intervals(lectures), cfg)
    return [direct_transit_visit(day, spec, cfg) for spec in specs]


class MergeTests(unittest.TestCase):
    def test_overlapping_and_touching_intervals_merge(self):
        self.assertEqual(merge_intervals([(at(14), at(16)), (at(10), at(12)), (at(11), at(13))]),
                         [(at(10), at(13)), (at(14), at(16))])
        self.assertEqual(merge_intervals([(600, 700), (700, 760)]), [(600, 760)])


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


class WalkRuleTests(unittest.TestCase):
    def test_without_car_only_transit(self):
        cfg = make_config()
        for legs, _ in enumerate_walks(HOME, CAR_HOME, TUM, cfg, True):
            self.assertTrue(all(mode == TRANSIT for *_, mode in legs))

    def test_car_legs_follow_the_car_state(self):
        """Simulate the car along every walk: it starts at home, leaves only from home,
        stays out while you are not home, and transit is only used while it is at home."""
        cfg = make_config(car=CAR_TABLE)
        for start, end in ((HOME, HOME), (HOME, TUM), (TUM, HOME), (TUM, TUM)):
            for legs, car_end in enumerate_walks(start, CAR_HOME, end, cfg, True):
                out = False
                for src, dst, mode in legs:
                    if mode == CAR:
                        if not out:
                            self.assertEqual(src, HOME, legs)  # the car is only at home
                        out = dst != HOME
                    else:
                        self.assertFalse(out, legs)  # the car is with you: no transit
                self.assertEqual(car_end, CAR_OUT if out else CAR_HOME, legs)

    def test_at_most_one_visit(self):
        cfg = make_config(car=CAR_TABLE)
        for legs, _ in enumerate_walks(TUM, CAR_HOME, TUM, cfg, True):
            self.assertLessEqual(sum(1 for _, dst, _ in legs if dst == JOB), 1)

    def test_no_visit_when_work_is_not_allowed(self):
        cfg = make_config(car=CAR_TABLE)
        for legs, _ in enumerate_walks(HOME, CAR_HOME, HOME, cfg, False):
            self.assertFalse(any(dst == JOB for _, dst, _ in legs))


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


class BossReportTests(unittest.TestCase):
    def test_half_hour_rounding(self):
        self.assertEqual([plan._half_hours(m) for m in (0, 14, 15, 100, 105, 480)], [0, 0, 30, 90, 120, 480])

    def test_rows_show_only_planned_days_and_exam_days(self):
        cfg = make_config(schedule={"weekly_target_hours": 4},
                          holidays={"no_work_durations": ["2026-12-09 10:00..10:30"]})
        result = plan.build_plan([], cfg, MONDAY, SUNDAY)
        planned = {d.day.strftime("%d.%m.%Y") for w in result.weeks for d in w.days if d.status == "planned"}
        rows = plan.boss_rows(result, cfg)
        self.assertTrue(planned)
        self.assertLessEqual({r[0] for r in rows}, planned | {"09.12.2026"})
        exam_rows = [r for r in rows if r[0] == "09.12.2026"]
        self.assertTrue(exam_rows)
        self.assertEqual(exam_rows[-1][4], "yes")
        for row in rows:
            if row[2]:  # a planned block: start on a half hour, length in half hours with a decimal comma
                self.assertIn(row[2][-2:], ("00", "30"))
                self.assertRegex(row[3], r"^\d+,[05]$")

    def test_boss_hours_are_the_visit_minus_the_break(self):
        cfg = make_config(schedule={"weekly_target_hours": 4, "break_minutes": 30})
        result = plan.build_plan([], cfg, MONDAY, SUNDAY)
        blocks = plan.boss_blocks(result, cfg)["blocks"]
        visits = [leave - arrive for w in result.weeks for d in w.days
                  if d.status == "planned" and d.drawn is not None for arrive, leave in d.drawn.visits]
        self.assertTrue(visits)
        self.assertEqual([b["minutes"] for b in blocks], [plan._half_hours(v - 30) for v in visits])

    def test_csv_is_semicolon_separated_with_bom(self):
        cfg = make_config(schedule={"weekly_target_hours": 4})
        result = plan.build_plan([], cfg, MONDAY, SUNDAY)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "office.csv"
            plan.write_boss_csv(result, cfg, path)
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            lines = raw.decode("utf-8-sig").splitlines()
        self.assertEqual(lines[0], "Date;Weekday;Office start;Work hours;Exam")


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
        built = plan.build_plan(events, cfg, MONDAY, MONDAY)
        self.assertEqual(built.weeks[0].planned, 0)
        self.assertTrue(all(d.status != "planned" for d in built.weeks[0].days))

    def test_planned_and_fallback_days_do_not_overlap(self):
        cfg = make_config(schedule={"weekly_target_hours": 10, "min_time_at_company": 120})
        events = self.week_events({MONDAY: [(at(10), at(12))]})
        built = plan.build_plan(events, cfg, MONDAY, SUNDAY)
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
        built = plan.build_plan(events, cfg, MONDAY, SUNDAY)
        self.assertLessEqual(built.weeks[0].planned, 600)


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = make_config()
        self.assertEqual((cfg.job_to_tum, cfg.home_to_job, cfg.job_to_home), (30, 70, 70))
        self.assertEqual(cfg.work_days, frozenset(range(5)))
        self.assertIsNone(cfg.car)
        self.assertIsNone(cfg.car)
        self.assertIsNone(cfg.weekly_target_minutes)

    def test_car_defaults_are_symmetric(self):
        cfg = make_config(car=CAR_TABLE)
        self.assertEqual((cfg.car.job_to_tum, cfg.car.job_to_home, cfg.car.tum_to_home),
                         (45, 45, 25))

    def test_fuel_estimate_counts_car_legs(self):
        cfg = make_config(car={**CAR_TABLE, "distance_in_km": 20, "liters_per_100km": 7,
                               "fuel_price_per_liter": 1.8})
        best = min(day_candidates(MONDAY, [], cfg).visits, key=lambda o: o.travel)
        # car home -> job and back: two car legs of 20 km each at 7 l/100 km and 1.80 EUR/l
        self.assertEqual(best.fuel_eur, round(2 * 20 * 7 / 100 * 1.8, 2))

    def test_no_fuel_estimate_without_car_distance(self):
        cfg = make_config(car=CAR_TABLE)
        self.assertTrue(all(o.fuel_eur is None for o in day_candidates(MONDAY, [], cfg).visits))

    def test_fuel_estimate_needs_all_three_values(self):
        with self.assertRaisesRegex(ConfigError, "fuel"):
            make_config(car={**CAR_TABLE, "distance_in_km": 20})

    def test_car_requires_its_times(self):
        with self.assertRaisesRegex(ConfigError, "car.home_to_job"):
            make_config(car={"home_to_tum": 25, "tum_to_job": 45})

    def test_target_and_limit(self):
        cfg = make_config(schedule={"weekly_target_hours": 20})
        self.assertEqual((cfg.weekly_target_minutes, cfg.max_week_minutes), (1200, 1200))
        with self.assertRaisesRegex(ConfigError, "max_hours_per_week"):
            make_config(schedule={"weekly_target_hours": 20, "max_hours_per_week": 15})

    def test_company_closed_is_a_no_work_range(self):
        cfg = make_config(holidays={"company_closed": ["2026-12-24..2027-01-06"],
                                    "no_work": ["2026-11-10"]})
        self.assertEqual(len(cfg.no_work), 2)

    def test_timed_block_is_parsed(self):
        cfg = make_config(holidays={"no_work_durations": ["2026-12-08 10:00..10:30"]})
        self.assertEqual(cfg.no_work_durations, ((date(2026, 12, 8), at(10), at(10, 30)),))

    def test_timed_block_errors_are_named(self):
        for bad in ["2026-12-08", "2026-12-08 11:00..10:00", "2026-12-08 10:00", "2026-13-08 10:00..10:30"]:
            with self.subTest(bad=bad), self.assertRaisesRegex(ConfigError, "no_work_durations|holidays"):
                make_config(holidays={"no_work_durations": [bad]})

    def test_calendar_range(self):
        cfg = make_config(calendar={"start": "2026-11-01", "end": "2027-02-28"})
        self.assertEqual(cfg.calendar_start, date(2026, 11, 1))
        with self.assertRaisesRegex(ConfigError, "calendar.end"):
            make_config(calendar={"start": "2027-02-01", "end": "2027-01-01"})

    def test_missing_required_keys_are_named(self):
        for section, key in [("travel", "home_to_tum"), ("travel", "tum_to_job"),
                             ("schedule", "earliest_wake_up"), ("schedule", "latest_at_job"),
                             ("schedule", "min_time_at_company")]:
            raw = {"travel": {"home_to_tum": 40, "tum_to_job": 30},
                   "schedule": {"earliest_wake_up": "06:30", "latest_at_job": "17:00",
                                "min_time_at_company": 60}}
            del raw[section][key]
            with self.assertRaisesRegex(ConfigError, f"{section}.{key}"):
                config_from_dict(raw)

    def test_typo_in_key_is_an_error(self):
        with self.assertRaisesRegex(ConfigError, "latest_at_jobb"):
            make_config(schedule={"latest_at_jobb": "17:00"})

    def test_clock_format(self):
        with self.assertRaisesRegex(ConfigError, "17.00"):
            make_config(schedule={"latest_at_job": "17.00"})
        self.assertEqual(make_config(schedule={"latest_at_job": "6:05"}).latest_at_job, at(6, 5))

    def test_sessions_and_lv_numbers_are_normalized(self):
        cfg = make_config(lectures={"not_attended": ["0000000103"],
                                    "sessions_not_attended": ["0000000104:ue"]})
        self.assertEqual(cfg.not_attended, frozenset({"103"}))
        self.assertEqual(cfg.sessions_not_attended, frozenset({("104", "UE")}))

    def test_example_config_loads(self):
        with (ROOT / "config.example.toml").open("rb") as handle:
            cfg = config_from_dict(tomllib.load(handle))
        self.assertEqual(cfg.latest_at_job, at(17))
        self.assertIsNotNone(cfg.car)


CALENDAR_WEEK = '[calendar]\nstart = "2026-12-07"\nend = "2026-12-13"\n'


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


class CalendarRangeTests(unittest.TestCase):
    def test_days_outside_the_calendar_are_not_planned(self):
        cfg = make_config()
        events = [{"date": "2026-12-08", "start_min": 600, "end_min": 720, "skipped": False}]
        built = plan.build_plan(events, cfg, date(2026, 12, 8), date(2026, 12, 11))
        statuses = {d.day.day: d.status for d in built.weeks[0].days}
        self.assertEqual(statuses[7], "outside")
        self.assertEqual(statuses[12], "outside")
        self.assertTrue(all(d.drawn is None for d in built.weeks[0].days if d.status == "outside"))


class EndToEndTests(unittest.TestCase):
    CSV = (
        '﻿"WOCHENTAG","DATUM","VON","BIS","DAUER_IN_MINUTEN","LV_NUMMER","TITEL",'
        '"LV_ART","LV_GRUPPE","ORT","LERNEINHEIT","UNTERRICHTSEINHEIT","EREIGNIS_TYP",'
        '"TERMIN_TYP","VORTRAGENDER_KONTAKTPERSON","ANMERKUNG"\r\n'
        '"MO","07.12.2026","10:00","12:00","120","0000000101","Imaginary Algebra 1 (XY1001)",'
        '"VO","Standardgruppe","90.01.001, Lecture Hall A (9999.EG.011)","","","Abhaltung","fix","",""\r\n'
        '"MO","07.12.2026","14:00","16:00","120","0000000103","Made-Up Systems (XY3003)",'
        '"VO","Standardgruppe","90.03.003, Lecture Hall C (9999.EG.011)","","","Abhaltung","fix","",""\r\n'
    )
    CONFIG = (
        '[travel]\nhome_to_tum = 40\ntum_to_job = 30\n'
        '[car]\nhome_to_tum = 25\nhome_to_job = 45\ntum_to_job = 45\n'
        '[schedule]\nearliest_wake_up = "06:30"\nlatest_at_job = "17:00"\nmin_time_at_company = 60\n'
        'weekly_target_hours = 10\n'
        '[lectures]\nnot_attended = ["0000000103"]\n'
    )

    def run_main(self, tmp, config_text=None):
        (tmp / "in.csv").write_bytes(self.CSV.encode("utf-8"))
        (tmp / "config.toml").write_text(config_text or self.CONFIG, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = plan.main([str(tmp / "in.csv"), "--config", str(tmp / "config.toml"),
                              "-o", str(tmp / "plan.json")])
        self.assertEqual(code, 0)
        return json.loads((tmp / "plan.json").read_text(encoding="utf-8")), out.getvalue()

    def test_main_writes_plan_with_modes_and_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, summary = self.run_main(Path(tmp), self.CONFIG + CALENDAR_WEEK)
        self.assertEqual(data["calendar"]["start"], "2026-12-07")
        self.assertEqual(len(data["days"]), 7)
        self.assertTrue(any(d["status"] == "planned" for d in data["days"]))
        planned = [d for d in data["days"] if d["status"] == "planned"]
        self.assertGreaterEqual(sum(d["work_minutes"] for d in planned), 600)
        self.assertTrue(all(leg["mode"] in ("transit", "car") for leg in data["travel"]))
        self.assertIn("KW 50", summary)

    def test_calendar_range_restricts_the_sessions(self):
        config_text = self.CONFIG + '[calendar]\nstart = "2026-12-08"\nend = "2026-12-13"\n'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                with contextlib.redirect_stderr(io.StringIO()):
                    self.run_main(Path(tmp), config_text)
            self.assertEqual(caught.exception.code, 2)  # argparse error: no session in the range

    def test_missing_config_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "in.csv"
            csv_path.write_text("DATUM,VON,BIS,TITEL\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    plan.main([str(csv_path), "--config", str(Path(tmp) / "nope.toml")])


class CompileTests(unittest.TestCase):
    def test_json_outside_the_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "plan.json"
            outside.write_text("{}", encoding="utf-8")
            with unittest.mock.patch.object(plan.shutil, "which", return_value="typst"):
                with self.assertRaisesRegex(ValueError, "inside the project folder"):
                    plan.compile_pdf(outside)

    def test_missing_typst_is_reported(self):
        with unittest.mock.patch.object(plan.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "typst"):
                plan.compile_pdf(ROOT / "data" / "plan.json")


if __name__ == "__main__":
    unittest.main()
