#!/usr/bin/env python3
"""Work out how and when the working student can work, and write the JSON used by calendar.typ.

Inputs
    * a TUMonline calendar export (TUMonline > Personal calendar > Export > Download as CSV UTF-8)
    * a config.toml (see config.example.toml for every key)

Output
    * a JSON file (default data/plan.json): lectures, travel legs, the planned and fallback
      work visits, a per-day evaluation and weekly totals
    * a text summary on stdout

Usage
    python -I scripts/plan.py path/to/personal_XXXX.csv --config config.toml [-o data/plan.json]

Only the Python standard library is used.

Model
    A day is a walk through three places: H (home), T (TUM, lectures) and J (the job).
    Every leg is made by transit or by car. The car starts at home; once it leaves home it
    stays with you until you are home again, so transit is not possible while the car is out.
    Between two lectures you may make at most one visit to the job. Each day gets its
    cheapest option; the cost is the extra travel compared with the cheapest commute without
    work, plus a penalty per company day. For the week, a small dynamic programme picks one
    option per day so that the target hours are reached at the lowest total cost.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

REQUIRED_CSV_COLUMNS = ("DATUM", "VON", "BIS", "TITEL")
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # index = date.weekday()
SHORT_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

HOME, TUM, JOB = "H", "T", "J"
PLACES = (HOME, TUM, JOB)
TRANSIT, CAR = "transit", "car"
CAR_HOME, CAR_OUT = "home", "out"  # where the car is: parked at home, or with the user
MAX_LEGS = 4       # longest walk between two lectures: TUM-home-job-home-TUM
STEP = 15          # planned visits are chosen in steps of this many minutes

# A "module code" like IN2005, MA3305 or CSE... (used to strip clutter from titles).
_CODE = re.compile(r"^[A-Z]{2,4}\d{3,5}$")
# "<room code>, <room name> (<TUM building id>)", e.g. "01.02.003, Lecture Hall B (9999.EG.003)"
_ROOM = re.compile(r"^(?P<code>[^,]+),\s*(?P<name>.*?)\s*(?:\((?P<id>\d{4}\.[\w.]+)\))?$")


# ------------------------------------------------------------------ helpers ---

def hm(minutes: int) -> str:
    """Minutes after midnight -> "HH:MM"."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def dur(minutes: int) -> str:
    """Minutes -> "4h05"."""
    return f"{minutes // 60}h{minutes % 60:02d}"


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def normalize_lv(number: str) -> str:
    """TUMonline writes LV numbers with leading zeros ("0000000101"); "101" is the same course."""
    return number.strip().lstrip("0")


# ---------------------------------------------------------------- CSV input ---

def _squash(text: str) -> str:
    """Collapse runs of whitespace (the export contains double spaces)."""
    return re.sub(r"\s+", " ", text).strip()


def short_title(title: str) -> str:
    """Drop module-code groups such as '[MA3305, IN2156]' or '(IN2005)' from a title."""

    def strip_if_codes(match: re.Match[str]) -> str:
        items = [item.strip() for item in match.group(1).split(",")]
        return "" if all(_CODE.match(item) for item in items) else match.group(0)

    title = re.sub(r"\s*\[([^\]]*)\]", strip_if_codes, title)
    title = re.sub(r"\s*\(([^)]*)\)", strip_if_codes, title)
    return _squash(title)


def parse_room(raw: str) -> dict[str, str]:
    """Split a TUMonline location string into name, room code and building id."""
    raw = _squash(raw)
    match = _ROOM.match(raw)
    if not raw or not match:
        return {"room": raw, "room_code": "", "room_id": ""}
    return {
        "room": match.group("name") or match.group("code"),
        "room_code": match.group("code").strip(),
        "room_id": match.group("id") or "",
    }


def _minutes_of_clock(clock: str) -> int:
    hours, minutes = clock.split(":")[:2]
    return int(hours) * 60 + int(minutes)


def assign_lanes(events: list[dict]) -> None:
    """Give overlapping events of the same day side-by-side lanes (in place).

    Adds `lane` (0-based column) and `lanes` (number of columns in the overlap cluster).
    """
    by_day: dict[str, list[dict]] = {}
    for event in events:
        by_day.setdefault(event["date"], []).append(event)

    for day_events in by_day.values():
        day_events.sort(key=lambda e: (e["start_min"], e["end_min"]))
        cluster: list[dict] = []
        lane_ends: list[int] = []
        cluster_end = -1

        def close_cluster() -> None:
            for member in cluster:
                member["lanes"] = max(len(lane_ends), 1)

        for event in day_events:
            if cluster and event["start_min"] >= cluster_end:
                close_cluster()
                cluster, lane_ends, cluster_end = [], [], -1
            for lane, end in enumerate(lane_ends):
                if end <= event["start_min"]:
                    lane_ends[lane] = event["end_min"]
                    event["lane"] = lane
                    break
            else:
                event["lane"] = len(lane_ends)
                lane_ends.append(event["end_min"])
            cluster.append(event)
            cluster_end = max(cluster_end, event["end_min"])
        close_cluster()


def convert(rows: list[dict[str, str]]) -> list[dict]:
    """TUMonline CSV rows -> event dicts (sorted and de-duplicated; lanes are set later)."""
    events: list[dict] = []
    seen: set[tuple] = set()

    for number, row in enumerate(rows, start=2):  # line 1 is the header
        start, end = (row.get("VON") or "").strip(), (row.get("BIS") or "").strip()
        if not start or not end:
            print(f"warning: line {number}: no start/end time, skipped "
                  f"({row.get('TITEL', '?')!r})", file=sys.stderr)
            continue
        try:
            day = datetime.strptime(row["DATUM"].strip(), "%d.%m.%Y").date()
        except ValueError:
            print(f"warning: line {number}: unreadable date {row['DATUM']!r}, skipped",
                  file=sys.stderr)
            continue

        full_title = _squash(row["TITEL"])
        event = {
            "date": day.isoformat(),
            "start": start[:5],
            "end": end[:5],
            "start_min": _minutes_of_clock(start),
            "end_min": _minutes_of_clock(end),
            "lv_number": (row.get("LV_NUMMER") or "").strip(),
            "title": short_title(full_title),
            "full_title": full_title,
            "type": (row.get("LV_ART") or "").strip(),
            "group": _squash(row.get("LV_GRUPPE") or ""),
            "kind": (row.get("EREIGNIS_TYP") or "").strip(),
            **parse_room(row.get("ORT") or ""),
        }
        key = (event["date"], event["start"], event["end"], event["lv_number"],
               event["title"], event["group"])
        if key in seen:
            continue
        seen.add(key)
        events.append(event)

    events.sort(key=lambda e: (e["date"], e["start_min"], e["end_min"], e["title"]))
    return events


def mark_skipped(events: list[dict], config: Config) -> None:
    """Flag the sessions the user does not attend (in place)."""
    for event in events:
        lv = normalize_lv(event["lv_number"])
        event["skipped"] = bool(lv) and (
            lv in config.not_attended or (lv, event["type"].upper()) in config.sessions_not_attended
        )


def layout_lanes(events: list[dict]) -> None:
    """Lanes for the attended sessions only (in place).

    Skipped sessions do not take a lane: they are drawn as a narrow strip on top,
    so they never squeeze the sessions the user really attends.
    """
    for event in events:
        event["lane"], event["lanes"] = 0, 1
    assign_lanes([e for e in events if not e["skipped"]])


# ------------------------------------------------------------------ config ---

class ConfigError(ValueError):
    """A config.toml that cannot be used. The message names the offending key."""


_MISSING = object()
_TOP_LEVEL = {"travel", "car", "schedule", "lectures", "holidays", "calendar", "day_overrides"}
_TRAVEL = {"home_to_tum", "tum_to_job", "job_to_tum", "home_to_job", "job_to_home"}
_CAR = {"home_to_tum", "home_to_job", "tum_to_job", "job_to_tum", "job_to_home", "tum_to_home"}
_SCHEDULE = {"earliest_wake_up", "ready_minutes", "latest_at_job", "earliest_at_job",
             "min_time_at_company", "max_shift_minutes", "buffer_minutes", "work_days",
             "weekly_target_hours", "max_hours_per_week", "company_day_penalty_minutes"}
_LECTURES = {"not_attended", "sessions_not_attended", "show_skipped"}
_HOLIDAYS = {"no_work", "company_closed"}
_CALENDAR = {"start", "end"}
_OVERRIDE = {"latest_at_job", "earliest_at_job"}


@dataclass(frozen=True)
class CarConfig:
    home_to_tum: int
    home_to_job: int
    tum_to_job: int
    job_to_tum: int
    job_to_home: int
    tum_to_home: int


@dataclass(frozen=True)
class Config:
    # transit (bus, U-/S-Bahn), minutes
    home_to_tum: int
    tum_to_job: int
    job_to_tum: int
    home_to_job: int
    job_to_home: int
    car: CarConfig | None          # None: no car, transit only
    # schedule
    earliest_wake_up: int          # minutes after midnight
    ready_minutes: int
    latest_at_job: int
    earliest_at_job: int | None
    min_time_at_company: int
    max_shift_minutes: int | None
    buffer_minutes: int
    work_days: frozenset[int]      # date.weekday() values, 0 = Monday
    weekly_target_minutes: int | None
    max_week_minutes: int | None   # never plan more than this per week (defaults to the target)
    company_day_penalty: int       # cost of one day at the company, in minutes of travel
    # lectures
    not_attended: frozenset[str]                       # normalized LV numbers
    sessions_not_attended: frozenset[tuple[str, str]]  # (normalized LV number, LV_ART)
    show_skipped: bool
    # no work at the job: inclusive date ranges (company closures and personal days off)
    no_work: tuple[tuple[date, date], ...]
    # per weekday (date.weekday()) overrides of latest/earliest_at_job
    day_overrides: dict[int, dict[str, int]]
    # the planned range; None means "from the first to the last session of the export"
    calendar_start: date | None
    calendar_end: date | None


def _table(raw: dict, name: str, allowed: set[str]) -> dict:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"unknown key(s) in [{name}]: {', '.join(unknown)} (typo?)")
    return value


def _get(table: dict, section: str, key: str, parse, default=_MISSING):
    name = f"{section}.{key}" if section else key
    if key in table:
        return parse(table[key], name)
    if default is _MISSING:
        raise ConfigError(f"missing required key: {name}")
    return default


def _parse_minutes(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name}: expected a whole number of minutes, got {value!r}")
    if value < minimum:
        raise ConfigError(f"{name}: must be at least {minimum}, got {value}")
    return value


def _parse_clock(value, name: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,2}:\d{2}", value):
        raise ConfigError(f'{name}: expected a quoted clock time like "17:00", got {value!r}')
    hours, minutes = (int(part) for part in value.split(":"))
    if hours > 23 or minutes > 59:
        raise ConfigError(f"{name}: {value!r} is not a valid clock time")
    return hours * 60 + minutes


def _parse_hours(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{name}: expected a number of hours, got {value!r}")
    return round(value * 60)


def _parse_weekdays(value, name: str) -> frozenset[int]:
    if not isinstance(value, list):
        raise ConfigError(f'{name}: expected a list like ["mon", "tue"]')
    days = set()
    for item in value:
        if item not in WEEKDAY_NAMES:
            raise ConfigError(f"{name}: unknown weekday {item!r} (use {', '.join(WEEKDAY_NAMES)})")
        days.add(WEEKDAY_NAMES.index(item))
    return frozenset(days)


def _parse_date(text, name: str) -> date:
    if not isinstance(text, str):
        raise ConfigError(f'{name}: expected a date like "2026-12-24", got {text!r}')
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ConfigError(f'{name}: expected a date like "2026-12-24", got {text!r}') from None


def _parse_ranges(value, name: str) -> tuple[tuple[date, date], ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f'{name}: expected a list of dates or ranges like "2026-12-24..2027-01-06"')
    ranges = []
    for item in value:
        first, _, last = item.partition("..")
        start = _parse_date(first, name)
        end = _parse_date(last, name) if last else start
        if end < start:
            raise ConfigError(f"{name}: range {item!r} ends before it starts")
        ranges.append((start, end))
    return tuple(ranges)


def _str_list(value, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f'{name}: expected a list of strings like ["0000000101"]')
    return value


def _bool(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name}: expected true or false, got {value!r}")
    return value


def config_from_dict(raw: dict) -> Config:
    unknown = sorted(set(raw) - _TOP_LEVEL)
    if unknown:
        raise ConfigError(f"unknown section(s): {', '.join(unknown)} (typo?)")

    travel = _table(raw, "travel", _TRAVEL)
    home_to_tum = _get(travel, "travel", "home_to_tum", _parse_minutes)
    tum_to_job = _get(travel, "travel", "tum_to_job", _parse_minutes)
    job_to_tum = _get(travel, "travel", "job_to_tum", _parse_minutes, tum_to_job)
    home_to_job = _get(travel, "travel", "home_to_job", _parse_minutes, home_to_tum + tum_to_job)
    job_to_home = _get(travel, "travel", "job_to_home", _parse_minutes, home_to_job)

    car = None
    if "car" in raw:
        table = _table(raw, "car", _CAR)
        c_home_to_tum = _get(table, "car", "home_to_tum", _parse_minutes)
        c_home_to_job = _get(table, "car", "home_to_job", _parse_minutes)
        c_tum_to_job = _get(table, "car", "tum_to_job", _parse_minutes)
        car = CarConfig(
            home_to_tum=c_home_to_tum,
            home_to_job=c_home_to_job,
            tum_to_job=c_tum_to_job,
            job_to_tum=_get(table, "car", "job_to_tum", _parse_minutes, c_tum_to_job),
            job_to_home=_get(table, "car", "job_to_home", _parse_minutes, c_home_to_job),
            tum_to_home=_get(table, "car", "tum_to_home", _parse_minutes, c_home_to_tum),
        )

    schedule = _table(raw, "schedule", _SCHEDULE)
    earliest_wake_up = _get(schedule, "schedule", "earliest_wake_up", _parse_clock)
    ready_minutes = _get(schedule, "schedule", "ready_minutes", _parse_minutes, 0)
    latest_at_job = _get(schedule, "schedule", "latest_at_job", _parse_clock)
    earliest_at_job = _get(schedule, "schedule", "earliest_at_job", _parse_clock, None)
    min_time = _get(schedule, "schedule", "min_time_at_company", _parse_minutes)
    max_shift = _get(schedule, "schedule", "max_shift_minutes", _parse_minutes, None)
    buffer_minutes = _get(schedule, "schedule", "buffer_minutes", _parse_minutes, 0)
    work_days = _get(schedule, "schedule", "work_days", _parse_weekdays, frozenset(range(5)))
    target = _get(schedule, "schedule", "weekly_target_hours", _parse_hours, None)
    max_week = _get(schedule, "schedule", "max_hours_per_week", _parse_hours, None)
    penalty = _get(schedule, "schedule", "company_day_penalty_minutes", _parse_minutes, 60)
    if max_week is None:
        max_week = target
    if target is not None and max_week is not None and max_week < target:
        raise ConfigError("schedule.max_hours_per_week must not be below schedule.weekly_target_hours")

    lectures = _table(raw, "lectures", _LECTURES)
    not_attended = _get(lectures, "lectures", "not_attended", _str_list, [])
    sessions_raw = _get(lectures, "lectures", "sessions_not_attended", _str_list, [])
    sessions = set()
    for item in sessions_raw:
        number, sep, kind = item.partition(":")
        if not sep or not normalize_lv(number) or not kind.strip():
            raise ConfigError(f'lectures.sessions_not_attended: expected "LV_NUMMER:LV_ART", got {item!r}')
        sessions.add((normalize_lv(number), kind.strip().upper()))
    show_skipped = _get(lectures, "lectures", "show_skipped", _bool, True)

    holidays = _table(raw, "holidays", _HOLIDAYS)
    no_work = _get(holidays, "holidays", "no_work", _parse_ranges, ())
    closed = _get(holidays, "holidays", "company_closed", _parse_ranges, ())

    calendar = _table(raw, "calendar", _CALENDAR)
    cal_start = _get(calendar, "calendar", "start", _parse_date, None)
    cal_end = _get(calendar, "calendar", "end", _parse_date, None)
    if cal_start and cal_end and cal_end < cal_start:
        raise ConfigError("calendar.end is before calendar.start")

    overrides: dict[int, dict[str, int]] = {}
    block = raw.get("day_overrides", {})
    if not isinstance(block, dict):
        raise ConfigError("[day_overrides] must contain tables such as [day_overrides.fri]")
    for day_name, table in block.items():
        if day_name not in WEEKDAY_NAMES:
            raise ConfigError(f"[day_overrides.{day_name}]: unknown weekday (use {', '.join(WEEKDAY_NAMES)})")
        if not isinstance(table, dict):
            raise ConfigError(f"[day_overrides.{day_name}] must be a table")
        unknown_keys = sorted(set(table) - _OVERRIDE)
        if unknown_keys:
            raise ConfigError(f"unknown key(s) in [day_overrides.{day_name}]: {', '.join(unknown_keys)}")
        values = {}
        if "latest_at_job" in table:
            values["latest_at_job"] = _parse_clock(table["latest_at_job"], f"day_overrides.{day_name}.latest_at_job")
        if "earliest_at_job" in table:
            values["earliest_at_job"] = _parse_clock(table["earliest_at_job"], f"day_overrides.{day_name}.earliest_at_job")
        overrides[WEEKDAY_NAMES.index(day_name)] = values

    if min_time < 1:
        raise ConfigError("schedule.min_time_at_company: must be at least 1 minute")
    if not work_days:
        raise ConfigError("schedule.work_days: list at least one weekday")

    return Config(
        home_to_tum=home_to_tum, tum_to_job=tum_to_job, job_to_tum=job_to_tum,
        home_to_job=home_to_job, job_to_home=job_to_home, car=car,
        earliest_wake_up=earliest_wake_up, ready_minutes=ready_minutes,
        latest_at_job=latest_at_job, earliest_at_job=earliest_at_job,
        min_time_at_company=min_time, max_shift_minutes=max_shift,
        buffer_minutes=buffer_minutes, work_days=work_days,
        weekly_target_minutes=target, max_week_minutes=max_week,
        company_day_penalty=penalty,
        not_attended=frozenset(normalize_lv(n) for n in not_attended if normalize_lv(n)),
        sessions_not_attended=frozenset(sessions),
        show_skipped=show_skipped,
        no_work=tuple(no_work) + tuple(closed),
        day_overrides=overrides,
        calendar_start=cal_start,
        calendar_end=cal_end,
    )


def load_config(path: Path) -> Config:
    with path.open("rb") as handle:
        return config_from_dict(tomllib.load(handle))


def config_for_output(cfg: Config) -> dict:
    """The resolved values, as shown on the overview page of the PDF."""
    return {
        "home_to_tum": cfg.home_to_tum,
        "tum_to_job": cfg.tum_to_job,
        "job_to_tum": cfg.job_to_tum,
        "home_to_job": cfg.home_to_job,
        "job_to_home": cfg.job_to_home,
        "car": None if cfg.car is None else {
            "home_to_tum": cfg.car.home_to_tum, "home_to_job": cfg.car.home_to_job,
            "tum_to_job": cfg.car.tum_to_job, "job_to_tum": cfg.car.job_to_tum,
            "job_to_home": cfg.car.job_to_home, "tum_to_home": cfg.car.tum_to_home,
        },
        "earliest_wake_up": hm(cfg.earliest_wake_up),
        "ready_minutes": cfg.ready_minutes,
        "latest_at_job": hm(cfg.latest_at_job),
        "earliest_at_job": None if cfg.earliest_at_job is None else hm(cfg.earliest_at_job),
        "min_time_at_company": cfg.min_time_at_company,
        "max_shift_minutes": cfg.max_shift_minutes,
        "buffer_minutes": cfg.buffer_minutes,
        "work_days": sorted(day + 1 for day in cfg.work_days),  # ISO: 1 = Monday
        "weekly_target_minutes": cfg.weekly_target_minutes,
        "max_week_minutes": cfg.max_week_minutes,
        "company_day_penalty": cfg.company_day_penalty,
        "not_attended": sorted(cfg.not_attended),
        "sessions_not_attended": sorted(f"{n}:{k}" for n, k in cfg.sessions_not_attended),
        "show_skipped": cfg.show_skipped,
        "no_work": [a.isoformat() if a == b else f"{a.isoformat()}..{b.isoformat()}"
                    for a, b in cfg.no_work],
        "day_overrides": {
            WEEKDAY_NAMES[day]: {k: hm(v) for k, v in values.items()}
            for day, values in sorted(cfg.day_overrides.items())
        },
        "calendar_start": cfg.calendar_start.isoformat() if cfg.calendar_start else None,
        "calendar_end": cfg.calendar_end.isoformat() if cfg.calendar_end else None,
    }


# ------------------------------------------------------------ travel model ---

def leg_minutes(cfg: Config, src: str, dst: str, mode: str) -> int:
    """Duration of one leg. Transit times are symmetric where the config has no separate value."""
    if mode == TRANSIT:
        table = {
            (HOME, TUM): cfg.home_to_tum, (TUM, HOME): cfg.home_to_tum,
            (TUM, JOB): cfg.tum_to_job, (JOB, TUM): cfg.job_to_tum,
            (HOME, JOB): cfg.home_to_job, (JOB, HOME): cfg.job_to_home,
        }
    else:
        car = cfg.car
        if car is None:
            raise ValueError("car leg without [car] configuration")
        table = {
            (HOME, TUM): car.home_to_tum, (TUM, HOME): car.tum_to_home,
            (TUM, JOB): car.tum_to_job, (JOB, TUM): car.job_to_tum,
            (HOME, JOB): car.home_to_job, (JOB, HOME): car.job_to_home,
        }
    return table[(src, dst)]


@dataclass(frozen=True)
class Leg:
    """One travel block with its clock times."""

    day: date
    start: int
    end: int
    src: str
    dst: str
    mode: str

    @property
    def minutes(self) -> int:
        return self.end - self.start


def enumerate_walks(src: str, car: str, end: str, cfg: Config,
                    allow_visit: bool) -> list[tuple[tuple[tuple[str, str, str], ...], str]]:
    """All legs from `src` to `end` that respect the car rules and visit the job at most once.

    Returns (legs, car_state_at_end) pairs. Each leg is (from, to, mode).
    """
    found: list[tuple[tuple[tuple[str, str, str], ...], str]] = []

    def walk(loc: str, car_state: str, legs: list, visited: bool) -> None:
        if loc == end:
            found.append((tuple(legs), car_state))
        if len(legs) >= MAX_LEGS:
            return
        for dst in PLACES:
            if dst == loc:
                continue
            if dst == JOB and (not allow_visit or visited):
                continue
            for mode in (TRANSIT, CAR):
                if mode == TRANSIT:
                    if car_state == CAR_OUT:
                        continue  # the car is with you, you cannot leave it behind
                    new_car = car_state
                else:
                    if cfg.car is None:
                        continue
                    if car_state == CAR_OUT:
                        new_car = CAR_HOME if dst == HOME else CAR_OUT
                    elif loc == HOME:
                        new_car = CAR_OUT  # you take the car from home
                    else:
                        continue  # the car is at home, you are not
                walk(dst, new_car, legs + [(loc, dst, mode)], visited or dst == JOB)

    walk(src, car, [], False)
    return found


@dataclass(frozen=True)
class GapSpec:
    """Where a stretch of the day starts and ends. `t1` None means "until the end of the day"."""

    src: str
    end: str
    t0: int
    t1: int | None


@dataclass(frozen=True)
class Gap:
    legs: tuple[Leg, ...]
    visit: tuple[int, int] | None   # (arrive, leave) at the job


def schedule_gap(day: date, spec: GapSpec, legs, cfg: Config, opening: int, latest: int,
                 visit_len: int | None = None) -> Gap | None:
    """Put the legs of one walk on the clock. None if it cannot fit in the window."""
    durations = [leg_minutes(cfg, s, d, m) for s, d, m in legs]
    total = sum(durations)
    visit_index = next((i for i, (_, d, _) in enumerate(legs) if d == JOB), None)

    if visit_index is None:
        if spec.t1 is not None and spec.t0 + total > spec.t1:
            return None
        return Gap(_chain(day, legs, durations, spec.t0), None)

    before = sum(durations[:visit_index + 1])
    after = sum(durations[visit_index + 1:])
    arrive = max(spec.t0 + before, opening)
    if visit_len is None:
        leave = latest
        if spec.t1 is not None:
            leave = min(leave, spec.t1 - after)
        if cfg.max_shift_minutes is not None:
            leave = min(leave, arrive + cfg.max_shift_minutes)
        if leave - arrive < cfg.min_time_at_company:
            return None
    else:
        leave = arrive + visit_len
    # wait at the origin so that the arrival is exactly `arrive`; leave the job as late as allowed
    before_legs = _chain(day, legs[:visit_index + 1], durations[:visit_index + 1], arrive - before)
    after_legs = _chain(day, legs[visit_index + 1:], durations[visit_index + 1:], leave)
    return Gap(tuple(before_legs + after_legs), (arrive, leave))


def _chain(day: date, legs, durations, start: int) -> list[Leg]:
    out = []
    clock = start
    for (src, dst, mode), minutes in zip(legs, durations):
        out.append(Leg(day, clock, clock + minutes, src, dst, mode))
        clock += minutes
    return out


class Option:
    """One way to spend a day: the legs of every gap and at most one visit per gap."""

    def __init__(self, day: date, cfg: Config, opening: int, latest: int,
                 inputs: tuple[tuple[GapSpec, tuple], ...], gaps: tuple[Gap, ...]):
        self.day = day
        self.cfg = cfg
        self.opening = opening
        self.latest = latest
        self.inputs = inputs          # (spec, walk legs) per gap, kept to re-time a shortened visit
        self.gaps = gaps
        self.legs: list[Leg] = [leg for gap in gaps for leg in gap.legs]
        self.visits: list[tuple[int, int]] = [gap.visit for gap in gaps if gap.visit]
        self.travel = sum(leg.minutes for leg in self.legs)
        self.work = sum(leave - arrive for arrive, leave in self.visits)
        self.extra = 0                # travel above the cheapest commute without work
        self.penalty = cfg.company_day_penalty if self.visits else 0

    @property
    def cost(self) -> int:
        return self.extra + self.penalty

    @property
    def value(self) -> float:
        """Cost per work hour; the ranking used for fallback days."""
        return self.cost / (self.work / 60) if self.work else math.inf

    @property
    def modes(self) -> str:
        used = {leg.mode for leg in self.legs}
        return used.pop() if len(used) == 1 else "mixed" if used else "none"

    def shortened(self, minutes: int) -> Option:
        """The same option with the (single) visit cut to `minutes`, legs re-timed."""
        index = next(i for i, g in enumerate(self.gaps) if g.visit)
        gaps = list(self.gaps)
        spec, legs = self.inputs[index]
        gaps[index] = schedule_gap(self.day, spec, legs, self.cfg, self.opening, self.latest,
                                   visit_len=minutes)
        result = Option(self.day, self.cfg, self.opening, self.latest, self.inputs, tuple(gaps))
        result.extra, result.penalty = self.extra, self.penalty
        return result


def build_specs(blocks: list[tuple[int, int]], cfg: Config) -> list[GapSpec]:
    """The stretches of a day: morning, between lectures, evening (or one stretch without lectures)."""
    buffer = cfg.buffer_minutes
    wake = cfg.earliest_wake_up + cfg.ready_minutes
    if not blocks:
        return [GapSpec(HOME, HOME, wake, None)]
    specs = [GapSpec(HOME, TUM, wake, blocks[0][0] - buffer)]
    for (_, previous_end), (next_start, _) in pairwise(blocks):
        specs.append(GapSpec(TUM, TUM, previous_end + buffer, next_start - buffer))
    specs.append(GapSpec(TUM, HOME, blocks[-1][1] + buffer, None))
    return specs


def day_limits(day: date, cfg: Config) -> tuple[int, int]:
    """(earliest arrival at the job, latest departure from the job) for this weekday."""
    override = cfg.day_overrides.get(day.weekday(), {})
    latest = override.get("latest_at_job", cfg.latest_at_job)
    opening = override.get("earliest_at_job", cfg.earliest_at_job)
    return (0 if opening is None else opening), latest


def _combine(day, specs, index, car, cfg, opening, latest, allow_visit):
    """Every combination of walks over the stretches of one day, with the car state carried along."""
    if index == len(specs):
        yield ()
        return
    spec = specs[index]
    for legs, car_end in enumerate_walks(spec.src, car, spec.end, cfg, allow_visit):
        visits = any(dst == JOB for _, dst, _ in legs)
        if not visits and len(legs) > 1:
            continue  # walking around without work only adds travel
        gap = schedule_gap(day, spec, legs, cfg, opening, latest)
        if gap is None:
            continue
        for rest in _combine(day, specs, index + 1, car_end, cfg, opening, latest, allow_visit):
            yield ((spec, legs, gap),) + rest


@dataclass
class DayCandidates:
    day: date
    baseline: Option | None       # the cheapest commute without work
    visits: list[Option]          # every option with at least one visit, cheapest first


def day_candidates(day: date, blocks: list[tuple[int, int]], cfg: Config) -> DayCandidates:
    opening, latest = day_limits(day, cfg)
    allow_visit = day.weekday() in cfg.work_days and not any(a <= day <= b for a, b in cfg.no_work)
    specs = build_specs(blocks, cfg)

    baseline: Option | None = None
    visits: list[Option] = []
    for combo in _combine(day, specs, 0, CAR_HOME, cfg, opening, latest, allow_visit):
        option = Option(day, cfg, opening, latest,
                        inputs=tuple((spec, legs) for spec, legs, _ in combo),
                        gaps=tuple(gap for _, _, gap in combo))
        if option.visits:
            visits.append(option)
        elif baseline is None or option.travel < baseline.travel:
            baseline = option

    base_travel = baseline.travel if baseline else 0
    if baseline:
        baseline.extra = 0
    for option in visits:
        option.extra = option.travel - base_travel
    visits.sort(key=lambda o: (o.cost, -o.work))
    return DayCandidates(day, baseline, visits)


def visit_choices(option: Option, min_time: int) -> list[int]:
    """Possible lengths of a planned visit: the full length, or shorter in steps of STEP."""
    if len(option.visits) != 1:
        return [option.work]
    full = option.work
    first = math.ceil(min_time / STEP) * STEP
    return [full] + [minutes for minutes in range(first, full, STEP)]


def select_week(cands: list[DayCandidates], target: int, limit: int, min_time: int):
    """Pick one option per day (and a length for its visit) that reaches `target` at least cost.

    Dynamic programme over the hours planned so far (in STEP minutes, never above `limit`).
    Returns {day: (option, hours)} for the days that get a planned visit.
    """
    states: dict[int, tuple[int, tuple]] = {0: (0, ())}
    for cand in cands:
        choices = [(None, 0, 0)]
        for option in cand.visits:
            for minutes in visit_choices(option, min_time):
                choices.append((option, minutes, option.cost))
        nxt: dict[int, tuple[int, tuple]] = {}
        for hours, (cost, chosen) in states.items():
            for option, minutes, extra in choices:
                total = hours + minutes
                if total > limit:
                    continue
                new_cost = cost + extra
                if total not in nxt or new_cost < nxt[total][0]:
                    nxt[total] = (new_cost, chosen + ((cand.day, option, minutes),))
        states = nxt

    reached = [(cost, -hours, chosen) for hours, (cost, chosen) in states.items() if hours >= target]
    if reached:
        _, _, chosen = min(reached, key=lambda r: (r[0], r[1]))
    else:
        best_hours = max(states)
        chosen = states[best_hours][1]
    return {day: (option, minutes) for day, option, minutes in chosen if option is not None}


# ----------------------------------------------------------- the planning ---

@dataclass
class DayResult:
    day: date
    status: str             # planned | fallback | available | none
    drawn: Option | None    # the plan whose legs and visits are drawn
    best: Option | None     # the cheapest visit option of the day, for the evaluation
    work: int               # minutes of planned or fallback work


@dataclass
class WeekResult:
    monday: date
    days: list[DayResult]
    lecture_minutes: int
    target: int | None
    maximum: int | None

    @property
    def planned(self) -> int:
        return sum(d.work for d in self.days if d.status == "planned")

    @property
    def fallback(self) -> int:
        return sum(d.work for d in self.days if d.status == "fallback")


@dataclass
class Plan:
    first_day: date
    last_day: date
    weeks: list[WeekResult]


def build_plan(events: list[dict], cfg: Config, first: date, last: date) -> Plan:
    attended: dict[date, list[tuple[int, int]]] = {}
    for event in events:
        if not event["skipped"]:
            day = date.fromisoformat(event["date"])
            attended.setdefault(day, []).append((event["start_min"], event["end_min"]))

    start = monday_of(first)
    end = monday_of(last) + timedelta(days=6)
    weeks: list[WeekResult] = []
    monday = start
    while monday <= end:
        days = [monday + timedelta(days=offset) for offset in range(7)]
        blocks = {d: merge_intervals(attended.get(d, [])) for d in days}
        cands = {d: day_candidates(d, blocks[d], cfg) for d in days}
        chosen: dict[date, tuple[Option, int]] = {}
        if cfg.weekly_target_minutes is not None:
            limit = cfg.max_week_minutes if cfg.max_week_minutes is not None else cfg.weekly_target_minutes
            chosen = select_week([cands[d] for d in days], cfg.weekly_target_minutes, limit,
                                 cfg.min_time_at_company)
        fallback = _fallback(cands, chosen, cfg.weekly_target_minutes)

        results = []
        for d in days:
            cand = cands[d]
            best = min(cand.visits, key=lambda o: (o.value, -o.work)) if cand.visits else None
            if d in chosen:
                option, minutes = chosen[d]
                drawn = option if minutes == option.work else option.shortened(minutes)
                results.append(DayResult(d, "planned", drawn, best, minutes))
            elif d in fallback:
                results.append(DayResult(d, "fallback", best, best, best.work))
            else:
                status = "available" if cand.visits else "none"
                results.append(DayResult(d, status, cand.baseline or best, best, 0))
        weeks.append(WeekResult(monday, results, sum(
            sum(e - s for s, e in blocks[d]) for d in days), cfg.weekly_target_minutes,
            cfg.max_week_minutes))
        monday += timedelta(days=7)

    return Plan(first_day=first, last_day=last, weeks=weeks)


def _fallback(cands: dict[date, DayCandidates], chosen: dict, target: int | None) -> set[date]:
    """The next best days (by cost per work hour) that together could cover the target."""
    if target is None:
        return set()
    ranked = sorted(
        ((min(c.visits, key=lambda o: (o.value, -o.work)), d) for d, c in cands.items()
         if c.visits and d not in chosen),
        key=lambda pair: (pair[0].value, -pair[0].work),
    )
    marked: set[date] = set()
    covered = 0
    for option, d in ranked:
        if covered >= target:
            break
        marked.add(d)
        covered += option.work
    return marked


def merge_intervals(intervals) -> list[tuple[int, int]]:
    """Sort (start, end) pairs and merge the ones that overlap or touch."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


# --------------------------------------------------------------- output ---

def _option_json(option: Option | None) -> dict | None:
    if option is None:
        return None
    return {
        "work_minutes": option.work,
        "travel_minutes": option.travel,
        "extra_minutes": option.extra,
        "penalty_minutes": option.penalty,
        "cost": option.cost,
        "cost_per_hour": None if not option.work else round(option.value, 1),
        "modes": option.modes,
        "visits": [{"start": hm(a), "end": hm(b), "start_min": a, "end_min": b,
                    "minutes": b - a} for a, b in option.visits],
    }


def plan_to_json(events: list[dict], plan: Plan, cfg: Config) -> dict:
    days, travel, slots = [], [], []
    for week in plan.weeks:
        for result in week.days:
            option = result.drawn
            if option is not None:
                for leg in option.legs:
                    travel.append({
                        "date": leg.day.isoformat(), "start_min": leg.start, "end_min": leg.end,
                        "src": leg.src, "dst": leg.dst, "mode": leg.mode,
                    })
            if result.status in ("planned", "fallback") and option is not None:
                for arrive, leave in option.visits:
                    slots.append({
                        "date": result.day.isoformat(), "weekday": result.day.isoweekday(),
                        "start": hm(arrive), "end": hm(leave), "start_min": arrive,
                        "end_min": leave, "minutes": leave - arrive, "status": result.status,
                    })
            days.append({
                "date": result.day.isoformat(),
                "weekday": result.day.isoweekday(),
                "status": result.status,
                "work_minutes": result.work,
                "drawn": _option_json(option),
                "best": _option_json(result.best),
            })
    weeks = []
    for week in plan.weeks:
        weeks.append({
            "monday": week.monday.isoformat(),
            "week": week.monday.isocalendar().week,
            "lecture_minutes": week.lecture_minutes,
            "planned_minutes": week.planned,
            "fallback_minutes": week.fallback,
            "target_minutes": week.target,
            "maximum_minutes": week.maximum,
            "travel_minutes": sum(d.drawn.travel for d in week.days
                                  if d.drawn is not None and d.status in ("planned", "fallback")),
        })
    return {
        "config": config_for_output(cfg),
        "calendar": {"start": plan.first_day.isoformat(), "end": plan.last_day.isoformat()},
        "events": events,
        "days": days,
        "slots": slots,
        "travel": travel,
        "weeks": weeks,
    }


def print_summary(events: list[dict], plan: Plan, cfg: Config) -> None:
    attended = sum(1 for e in events if not e["skipped"])
    print(f"{len(events)} sessions, {attended} attended, {len(events) - attended} skipped; "
          f"planning {plan.first_day:%d.%m.%Y} .. {plan.last_day:%d.%m.%Y}")
    if cfg.weekly_target_minutes is not None:
        print(f"target {dur(cfg.weekly_target_minutes)} per week, at most "
              f"{dur(cfg.max_week_minutes or cfg.weekly_target_minutes)}")
    for week in plan.weeks:
        monday = week.monday
        sunday = monday + timedelta(days=6)
        line = (f"\nKW {monday.isocalendar().week:02d}  {monday:%d.%m.}-{sunday:%d.%m.%Y}   "
                f"planned {dur(week.planned)}")
        if week.fallback:
            line += f", fallback {dur(week.fallback)}"
        if week.target is not None:
            line += f"   (target {dur(week.target)}, deficit {dur(max(0, week.target - week.planned))})"
        print(line)
        for result in week.days:
            day_label = f"  {SHORT_DAYS[result.day.weekday()]} {result.day:%d.%m.}"
            if result.status in ("planned", "fallback"):
                option = result.drawn
                visits = ", ".join(f"{hm(a)}-{hm(b)} ({dur(b - a)})" for a, b in option.visits)
                print(f"{day_label}  {result.status.upper():8} {visits}  by {option.modes}, "
                      f"travel {dur(option.travel)} (extra {dur(option.extra)}), cost {option.cost}")
            elif result.best is not None:
                b = result.best
                print(f"{day_label}  available  best {dur(b.work)} by {b.modes}, "
                      f"travel {dur(b.travel)} (extra {dur(b.extra)}), cost {b.cost}")
            elif result.drawn is not None:
                print(f"{day_label}  no work     commute {dur(result.drawn.travel)} by {result.drawn.modes}")
            else:
                print(f"{day_label}  -")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("csv", type=Path, help="CSV file exported from TUMonline")
    parser.add_argument("--config", type=Path, default=Path("config.toml"),
                        help="config file (default: config.toml; start from config.example.toml)")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/plan.json"),
                        help="JSON file to write (default: data/plan.json)")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        parser.error(f"config file {args.config} not found "
                     "(copy config.example.toml to config.toml and adapt it)")
    except (ConfigError, tomllib.TOMLDecodeError) as exc:
        parser.error(f"{args.config}: {exc}")

    # utf-8-sig strips the byte-order mark that TUMonline puts at the start.
    with args.csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            parser.error(f"{args.csv} does not look like a TUMonline export "
                         f"(missing columns: {', '.join(missing)}). "
                         "Make sure the export language is German.")
        events = convert(list(reader))

    if not events:
        parser.error("no usable sessions found in the CSV")

    first = date.fromisoformat(events[0]["date"])
    last = date.fromisoformat(events[-1]["date"])
    first = config.calendar_start or first
    last = config.calendar_end or last
    events = [e for e in events if first.isoformat() <= e["date"] <= last.isoformat()]
    if not events:
        parser.error(f"no sessions between {first} and {last}; check the calendar range in the config")

    mark_skipped(events, config)
    layout_lanes(events)
    plan = build_plan(events, config, first, last)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = plan_to_json(events, plan, config)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print_summary(events, plan, config)
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
