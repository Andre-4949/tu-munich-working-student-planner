"""Compiling the PDF."""

from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tests.helpers import ROOT
from planner.pdf import compile_pdf


class CompileTests(unittest.TestCase):
    def test_json_outside_the_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "plan.json"
            outside.write_text("{}", encoding="utf-8")
            with unittest.mock.patch("planner.pdf.shutil.which", return_value="typst"):
                with self.assertRaisesRegex(ValueError, "inside the project folder"):
                    compile_pdf(outside)

    def test_missing_typst_is_reported(self):
        with unittest.mock.patch("planner.pdf.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "typst"):
                compile_pdf(ROOT / "data" / "plan.json")
