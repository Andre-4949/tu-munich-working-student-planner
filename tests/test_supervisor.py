"""The supervisor output."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import MONDAY, SUNDAY, make_config
from planner.planning import build_plan
from planner.clock import half_hours
from planner.supervisor import boss_blocks, boss_rows, write_boss_csv


class BossReportTests(unittest.TestCase):
    def test_half_hour_rounding(self):
        self.assertEqual([half_hours(m) for m in (0, 14, 15, 100, 105, 480)], [0, 0, 30, 90, 120, 480])

    def test_rows_show_only_planned_days_and_exam_days(self):
        cfg = make_config(schedule={"weekly_target_hours": 4},
                          holidays={"no_work_durations": ["2026-12-09 10:00..10:30"]})
        result = build_plan([], cfg, MONDAY, SUNDAY)
        planned = {d.day.strftime("%d.%m.%Y") for w in result.weeks for d in w.days if d.status == "planned"}
        rows = boss_rows(result, cfg)
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
        result = build_plan([], cfg, MONDAY, SUNDAY)
        blocks = boss_blocks(result, cfg)["blocks"]
        visits = [leave - arrive for w in result.weeks for d in w.days
                  if d.status == "planned" and d.drawn is not None for arrive, leave in d.drawn.visits]
        self.assertTrue(visits)
        self.assertEqual([b["minutes"] for b in blocks], [half_hours(v - 30) for v in visits])

    def test_csv_is_semicolon_separated_with_bom(self):
        cfg = make_config(schedule={"weekly_target_hours": 4})
        result = build_plan([], cfg, MONDAY, SUNDAY)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "office.csv"
            write_boss_csv(result, cfg, path)
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            lines = raw.decode("utf-8-sig").splitlines()
        self.assertEqual(lines[0], "Date;Weekday;Office start;Work hours;Exam")
