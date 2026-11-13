"""The short output for the supervisor: office days, rough start, work hours and exam days."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from planner.clock import half_hours, hm
from planner.config import Config
from planner.constants import SHORT_DAYS
from planner.planning import Plan


BOSS_COLUMNS = ["Date", "Weekday", "Office start", "Work hours", "Exam"]


def boss_blocks(plan: Plan, cfg: Config) -> dict:
    """What the supervisor sees: the office blocks of planned days and the exam days.

    Each block has its day, the rough start and the rounded length in minutes (both to the half hour).
    A day with a timed blocker in `no_work_durations` is an exam day; its time is not shown.
    """
    exam_days = {d for d, _, _ in cfg.no_work_durations}
    blocks: list[dict] = []
    exams: list[str] = []
    for week in plan.weeks:
        for day in week.days:
            if day.status == "outside":
                continue
            if day.day in exam_days:
                exams.append(day.day.isoformat())
            if day.status == "planned" and day.drawn is not None:
                for arrive, leave in day.drawn.visits:
                    # actual work time: the visit without the unpaid break
                    blocks.append({"date": day.day.isoformat(), "start": hm(half_hours(arrive)),
                                   "minutes": half_hours(leave - arrive - cfg.break_minutes)})
    return {"blocks": blocks, "exams": exams}


def boss_rows(plan: Plan, cfg: Config) -> list[list[str]]:
    """The supervisor CSV rows: one row per office block, plus one row per exam day without work."""
    info = boss_blocks(plan, cfg)
    exams = set(info["exams"])
    rows: list[list[str]] = []
    for block in info["blocks"]:
        day = date.fromisoformat(block["date"])
        exam = "yes" if block["date"] in exams else ""
        rows.append(boss_date_cells(day) + [block["start"], f"{block['minutes'] / 60:.1f}".replace(".", ","), exam])
    with_work = {block["date"] for block in info["blocks"]}
    for iso in info["exams"]:
        if iso not in with_work:
            rows.append(boss_date_cells(date.fromisoformat(iso)) + ["", "", "yes"])
    rows.sort(key=lambda row: (row[0][6:], row[0][3:5], row[0][:2]))  # dd.mm.yyyy -> by date
    return rows


def boss_date_cells(day: date) -> list[str]:
    return [day.strftime("%d.%m.%Y"), SHORT_DAYS[day.weekday()]]


def write_boss_csv(plan: Plan, cfg: Config, path: Path) -> None:
    """Semicolon-separated CSV with a byte-order mark, so Excel opens it with the columns split."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(BOSS_COLUMNS)
        writer.writerows(boss_rows(plan, cfg))
