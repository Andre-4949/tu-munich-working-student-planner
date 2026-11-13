"""Compiling the PDF with Typst."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compile_pdf(json_path: Path, pdf_path: Path | None = None,
                extra_inputs: dict[str, str] | None = None) -> Path:
    """Run Typst on calendar.typ with the given JSON and return the PDF path.

    Typst only reads files inside the project root, so the JSON must be inside it.
    `extra_inputs` are passed on as `--input key=value` (e.g. audience=boss).
    """
    typst = shutil.which("typst")
    if typst is None:
        raise RuntimeError("--compile needs the 'typst' command on the PATH "
                           "(https://github.com/typst/typst#installation)")
    try:
        data = Path(os.path.relpath(json_path.resolve(), PROJECT_ROOT)).as_posix()
    except ValueError:  # different drive on Windows
        data = ""
    if not data or data.startswith(".."):
        raise ValueError(f"{json_path} must be inside the project folder for --compile")
    pdf = (pdf_path or PROJECT_ROOT / "plan.pdf").resolve()
    command = [typst, "compile", "calendar.typ", str(pdf), "--root", str(PROJECT_ROOT),
               "--input", f"data={data}"]
    for key, value in (extra_inputs or {}).items():
        command += ["--input", f"{key}={value}"]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"typst failed:\n{result.stderr.strip()}")
    return pdf
