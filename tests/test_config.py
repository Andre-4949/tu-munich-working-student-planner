"""Reading and validating config.toml."""

from __future__ import annotations

import tomllib
import unittest
from datetime import date

from planner.config import config_from_dict
from planner.days import day_candidates
from planner.errors import ConfigError
from tests.helpers import CAR_TABLE, MONDAY, ROOT, at, make_config
from planner.planning import build_plan


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
        cfg = make_config(holidays={"no_work_durations": ["2026-12-15 10:00..10:30"]})
        self.assertEqual(cfg.no_work_durations, ((date(2026, 12, 15), at(10), at(10, 30)),))

    def test_timed_block_errors_are_named(self):
        for bad in ["2026-12-15", "2026-12-15 11:00..10:00", "2026-12-15 10:00", "2026-13-08 10:00..10:30"]:
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


class CalendarRangeTests(unittest.TestCase):
    def test_days_outside_the_calendar_are_not_planned(self):
        cfg = make_config()
        events = [{"date": "2026-12-09", "start_min": 600, "end_min": 720, "skipped": False}]
        built = build_plan(events, cfg, date(2026, 12, 9), date(2026, 12, 11))
        statuses = {d.day.day: d.status for d in built.weeks[0].days}
        self.assertEqual(statuses[7], "outside")
        self.assertEqual(statuses[12], "outside")
        self.assertTrue(all(d.drawn is None for d in built.weeks[0].days if d.status == "outside"))
