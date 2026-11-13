import contextlib
import io
import json
import sys
import tempfile
import tomllib
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plan  # noqa: E402
from plan import ConfigError, config_from_dict, merge_intervals, travel_legs, work_slots  # noqa: E402

MONDAY = date(2026, 12, 7)   # a Monday
FRIDAY = date(2026, 12, 11)


def make_config(schedule=None, travel=None, lectures=None, holidays=None, day_overrides=None):
    """Config with the default test values: home->TUM 40, TUM->job 30, wake 06:30, latest 17:00.

    Derived: job->TUM 30, home->job 70 (40+30), buffer 0, min 60 minutes.
    """
    base_travel = {"home_to_tum": 40, "tum_to_job": 30}
    base_schedule = {"earliest_wake_up": "06:30", "latest_at_job": "17:00",
                     "min_time_at_company": 60}
    raw = {
        "travel": {**base_travel, **(travel or {})},
        "schedule": {**base_schedule, **(schedule or {})},
    }
    if lectures is not None:
        raw["lectures"] = lectures
    if holidays is not None:
        raw["holidays"] = holidays
    if day_overrides is not None:
        raw["day_overrides"] = day_overrides
    return config_from_dict(raw)


def window(slots):
    return [(s.start, s.end) for s in slots]


# Clock helper so tests read naturally: at(10, 0) == 600
def at(hours, minutes=0):
    return hours * 60 + minutes


class MergeTests(unittest.TestCase):
    def test_overlapping_and_touching_intervals_merge(self):
        self.assertEqual(merge_intervals([(at(14), at(16)), (at(10), at(12)), (at(11), at(13))]),
                         [(at(10), at(13)), (at(14), at(16))])
        self.assertEqual(merge_intervals([(600, 700), (700, 760)]), [(600, 760)])

    def test_empty(self):
        self.assertEqual(merge_intervals([]), [])


class WorkSlotTests(unittest.TestCase):
    def test_free_day_gives_one_slot_from_earliest_arrival_to_latest(self):
        slots = work_slots(MONDAY, [], make_config())
        self.assertEqual(window(slots), [(at(6, 30) + 70, at(17))])
        self.assertEqual((slots[0].arrive_from, slots[0].leave_to), ("home", "home"))

    def test_gap_between_lectures_uses_both_travel_times(self):
        cfg = make_config()
        lectures = [(at(10), at(12)), (at(14), at(16))]
        # before: 07:40 .. 10:00-30 = 09:30 (110 min)
        # between: 12:00+30 = 12:30 .. 14:00-30 = 13:30 (60 min, exactly the minimum)
        # after: 16:30 .. 17:00 (30 min, too short)
        self.assertEqual(window(work_slots(MONDAY, lectures, cfg)),
                         [(at(7, 40), at(9, 30)), (at(12, 30), at(13, 30))])

    def test_minimum_is_inclusive_and_one_minute_more_drops_the_slot(self):
        lectures = [(at(10), at(12)), (at(14), at(16))]
        self.assertEqual(len(work_slots(MONDAY, lectures, make_config(schedule={"min_time_at_company": 60}))), 2)
        self.assertEqual(len(work_slots(MONDAY, lectures, make_config(schedule={"min_time_at_company": 61}))), 1)

    def test_lecture_at_eight_makes_morning_impossible(self):
        # wake 06:30 + 70 = 07:40 earliest arrival, but leaving for an 08:00 lecture is at 07:30
        slots = work_slots(MONDAY, [(at(8), at(10))], make_config())
        self.assertEqual(window(slots), [(at(10, 30), at(17))])

    def test_early_wake_up_makes_the_morning_possible(self):
        cfg = make_config(schedule={"earliest_wake_up": "05:00"})
        # 05:00 + 70 = 06:10 earliest arrival; 08:00 - 30 = 07:30 latest leave
        self.assertEqual(window(work_slots(MONDAY, [(at(8), at(10))], cfg))[0], (at(6, 10), at(7, 30)))

    def test_late_wake_up_removes_the_morning(self):
        cfg = make_config(schedule={"earliest_wake_up": "06:45"})
        # 06:45 + 70 = 07:55 > 07:30 -> no morning slot; only the slot after the 08:00-09:00 lecture
        self.assertEqual(window(work_slots(MONDAY, [(at(8), at(9))], cfg)), [(at(9, 30), at(17))])

    def test_lecture_running_past_latest_removes_the_after_slot(self):
        slots = work_slots(MONDAY, [(at(15), at(18, 20))], make_config())
        self.assertEqual(window(slots), [(at(7, 40), at(14, 30))])

    def test_first_lecture_after_latest_clips_morning_slot_to_latest(self):
        slots = work_slots(MONDAY, [(at(18), at(19))], make_config())
        self.assertEqual(window(slots), [(at(7, 40), at(17))])

    def test_overlapping_lectures_are_merged(self):
        lectures = [(at(10), at(11)), (at(10, 30), at(12)), (at(12), at(13))]
        self.assertEqual(window(work_slots(MONDAY, lectures, make_config())),
                         [(at(7, 40), at(9, 30)), (at(13, 30), at(17))])

    def test_earliest_at_job_clips_the_start(self):
        cfg = make_config(schedule={"earliest_at_job": "08:00"})
        self.assertEqual(window(work_slots(MONDAY, [], cfg)), [(at(8), at(17))])

    def test_max_shift_caps_the_block(self):
        cfg = make_config(schedule={"max_shift_minutes": 200})
        self.assertEqual(window(work_slots(MONDAY, [], cfg)), [(at(7, 40), at(7, 40) + 200)])

    def test_buffer_is_applied_next_to_lectures_only(self):
        cfg = make_config(schedule={"buffer_minutes": 10})
        lectures = [(at(10), at(12)), (at(14), at(16))]
        # before 07:40..09:20; between 12:40..13:20 (40 min, dropped); after 16:40..17:00 (dropped)
        self.assertEqual(window(work_slots(MONDAY, lectures, cfg)), [(at(7, 40), at(9, 20))])

    def test_ready_minutes_move_the_morning_start(self):
        cfg = make_config(schedule={"ready_minutes": 30})
        # up 06:30 + 30 min getting ready + 70 min to the job = 08:10
        self.assertEqual(window(work_slots(MONDAY, [], cfg)), [(at(8, 10), at(17))])

    def test_weekday_not_in_work_days_gives_nothing(self):
        cfg = make_config()
        self.assertEqual(work_slots(date(2026, 12, 12), [], cfg), [])  # Saturday

    def test_no_work_date_and_range(self):
        cfg = make_config(holidays={"no_work": ["2026-12-07", "2026-12-09..2026-12-10"]})
        self.assertEqual(work_slots(MONDAY, [], cfg), [])
        self.assertNotEqual(work_slots(date(2026, 12, 8), [], cfg), [])
        self.assertEqual(work_slots(date(2026, 12, 9), [], cfg), [])
        self.assertEqual(work_slots(date(2026, 12, 10), [], cfg), [])
        self.assertNotEqual(work_slots(date(2026, 12, 11), [], cfg), [])

    def test_day_override_changes_latest_time_for_that_weekday_only(self):
        cfg = make_config(day_overrides={"fri": {"latest_at_job": "14:00"}})
        self.assertEqual(window(work_slots(FRIDAY, [], cfg)), [(at(7, 40), at(14))])
        self.assertEqual(window(work_slots(MONDAY, [], cfg)), [(at(7, 40), at(17))])

    def test_slots_never_overlap_lectures(self):
        cfg = make_config(schedule={"buffer_minutes": 5})
        lectures = [(at(9), at(10)), (at(11), at(11, 30)), (at(13), at(15))]
        for slot in work_slots(MONDAY, lectures, cfg):
            for start, end in lectures:
                self.assertTrue(slot.end <= start or slot.start >= end, (slot, start, end))


class LaneTests(unittest.TestCase):
    def test_overlapping_attended_sessions_share_the_column(self):
        events = [
            {"date": "2026-12-07", "start_min": 600, "end_min": 720, "skipped": False},
            {"date": "2026-12-07", "start_min": 650, "end_min": 750, "skipped": False},
        ]
        plan.layout_lanes(events)
        self.assertEqual([(e["lane"], e["lanes"]) for e in events], [(0, 2), (1, 2)])

    def test_skipped_sessions_take_no_lane(self):
        events = [
            {"date": "2026-12-07", "start_min": 600, "end_min": 720, "skipped": False},
            {"date": "2026-12-07", "start_min": 630, "end_min": 700, "skipped": True},
        ]
        plan.layout_lanes(events)
        self.assertEqual([(e["lane"], e["lanes"]) for e in events], [(0, 1), (0, 1)])


class TravelTests(unittest.TestCase):
    def test_legs_for_a_split_day(self):
        cfg = make_config()
        lectures = [(at(10), at(12)), (at(14), at(16))]
        slots = work_slots(MONDAY, lectures, cfg)
        legs = [(leg.start, leg.end, leg.kind)
                for leg in travel_legs(MONDAY, merge_intervals(lectures), slots, cfg)]
        self.assertEqual(sorted(legs), sorted([
            (at(6, 30), at(7, 40), "home_to_job"),
            (at(9, 30), at(10), "job_to_tum"),
            (at(12), at(12, 30), "tum_to_job"),
            (at(13, 30), at(14), "job_to_tum"),
            (at(16), at(16, 40), "tum_to_home"),
        ]))

    def test_no_slot_means_commute_home_and_to_tum(self):
        cfg = make_config(schedule={"min_time_at_company": 600})
        lectures = [(at(10), at(12))]
        legs = travel_legs(MONDAY, lectures, [], cfg)
        self.assertEqual(sorted((l.start, l.end, l.kind) for l in legs),
                         [(at(9, 20), at(10), "home_to_tum"), (at(12), at(12, 40), "tum_to_home")])


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = make_config()
        self.assertEqual((cfg.job_to_tum, cfg.home_to_job, cfg.job_to_home), (30, 70, 70))
        self.assertEqual(cfg.work_days, frozenset(range(5)))
        self.assertEqual((cfg.ready_minutes, cfg.buffer_minutes, cfg.max_shift_minutes), (0, 0, None))
        self.assertIsNone(cfg.earliest_at_job)
        self.assertIsNone(cfg.weekly_target_minutes)
        self.assertEqual(cfg.not_attended, frozenset())

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
        with self.assertRaisesRegex(ConfigError, "25:00"):
            make_config(schedule={"latest_at_job": "25:00"})
        self.assertEqual(make_config(schedule={"latest_at_job": "6:05"}).latest_at_job, at(6, 5))

    def test_minutes_must_be_integers(self):
        with self.assertRaisesRegex(ConfigError, "home_to_tum"):
            make_config(travel={"home_to_tum": "40"})

    def test_weekdays(self):
        cfg = make_config(schedule={"work_days": ["mon", "sat"]})
        self.assertEqual(cfg.work_days, frozenset({0, 5}))
        with self.assertRaisesRegex(ConfigError, "funday"):
            make_config(schedule={"work_days": ["funday"]})

    def test_no_work_range_must_be_ordered(self):
        with self.assertRaisesRegex(ConfigError, "ends before"):
            make_config(holidays={"no_work": ["2026-12-10..2026-12-01"]})

    def test_sessions_and_lv_numbers_are_normalized(self):
        cfg = make_config(lectures={"not_attended": ["0000000103"],
                                    "sessions_not_attended": ["0000000104:ue"]})
        self.assertEqual(cfg.not_attended, frozenset({"103"}))
        self.assertEqual(cfg.sessions_not_attended, frozenset({("104", "UE")}))
        with self.assertRaisesRegex(ConfigError, "LV_NUMMER:LV_ART"):
            make_config(lectures={"sessions_not_attended": ["0000000104"]})

    def test_hours_target_is_converted_to_minutes(self):
        self.assertEqual(make_config(schedule={"weekly_target_hours": 7.5}).weekly_target_minutes, 450)

    def test_example_config_loads(self):
        with (ROOT / "config.example.toml").open("rb") as handle:
            cfg = config_from_dict(tomllib.load(handle))
        self.assertEqual(cfg.latest_at_job, at(17))


class EndToEndTests(unittest.TestCase):
    def test_main_writes_json_and_summary(self):
        csv_text = (
            '﻿"WOCHENTAG","DATUM","VON","BIS","DAUER_IN_MINUTEN","LV_NUMMER","TITEL",'
            '"LV_ART","LV_GRUPPE","ORT","LERNEINHEIT","UNTERRICHTSEINHEIT","EREIGNIS_TYP",'
            '"TERMIN_TYP","VORTRAGENDER_KONTAKTPERSON","ANMERKUNG"\r\n'
            '"MO","07.12.2026","10:00","12:00","120","0000000101","Imaginary Algebra 1 (XY1001)",'
            '"VO","Standardgruppe","90.01.001, Lecture Hall A (9999.EG.011)","","","Abhaltung","fix","",""\r\n'
            '"MO","07.12.2026","14:00","16:00","120","0000000103","Made-Up Systems (XY3003)",'
            '"VO","Standardgruppe","90.03.003, Lecture Hall C (9999.EG.011)","","","Abhaltung","fix","",""\r\n'
        )
        config_text = (
            '[travel]\nhome_to_tum = 40\ntum_to_job = 30\n'
            '[schedule]\nearliest_wake_up = "06:30"\nlatest_at_job = "17:00"\nmin_time_at_company = 60\n'
            '[lectures]\nnot_attended = ["0000000103"]\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "in.csv").write_bytes(csv_text.encode("utf-8"))
            (tmp / "config.toml").write_text(config_text, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = plan.main([str(tmp / "in.csv"), "--config", str(tmp / "config.toml"),
                                  "-o", str(tmp / "plan.json")])
            self.assertEqual(code, 0)
            data = json.loads((tmp / "plan.json").read_text(encoding="utf-8"))

        # Skipped 14:00 course does not block the afternoon: the slot from 12:30 runs to 17:00.
        monday = [(s["start"], s["end"]) for s in data["slots"] if s["date"] == "2026-12-07"]
        self.assertEqual(monday, [("07:40", "09:30"), ("12:30", "17:00")])
        # Tuesday to Friday have no lectures in this file: one full-day slot each (07:40-17:00).
        self.assertEqual(len(data["slots"]), 2 + 4)
        self.assertEqual(data["weeks"][0]["work_minutes"], 110 + 270 + 4 * 560)
        self.assertEqual([e["skipped"] for e in data["events"]], [False, True])
        self.assertIn("KW 50", out.getvalue())

    def test_missing_config_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "in.csv"
            csv_path.write_text("DATUM,VON,BIS,TITEL\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    plan.main([str(csv_path), "--config", str(Path(tmp) / "nope.toml")])


if __name__ == "__main__":
    unittest.main()
