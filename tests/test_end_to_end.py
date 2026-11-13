"""A whole run from CSV to plan."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from planner.cli import main


CALENDAR_WEEK = '[calendar]\nstart = "2026-12-07"\nend = "2026-12-13"\n'


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
            code = main([str(tmp / "in.csv"), "--config", str(tmp / "config.toml"),
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
        config_text = self.CONFIG + '[calendar]\nstart = "2026-12-15"\nend = "2026-12-20"\n'
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(stderr):
                self.run_main(Path(tmp), config_text)
            self.assertEqual(caught.exception.code, 2)  # argparse error: no session in the range
            self.assertIn("no sessions between", stderr.getvalue())

    def test_missing_config_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "in.csv"
            csv_path.write_text("DATUM,VON,BIS,TITEL\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    main([str(csv_path), "--config", str(Path(tmp) / "nope.toml")])
