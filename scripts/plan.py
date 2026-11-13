#!/usr/bin/env python3
"""Work out when the working student can work, and write the JSON used by calendar.typ.

Inputs
    * a TUMonline calendar export (TUMonline > Personal calendar > Export > Download as CSV UTF-8)
    * a config.toml (see config.example.toml for every key)

Output
    * a JSON file (default data/plan.json) with the lectures, the travel legs,
      the possible work slots and the weekly totals
    * a text summary on stdout

Usage
    python -I scripts/plan.py path/to/personal_XXXX.csv --config config.toml [-o data/plan.json]

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

REQUIRED_CSV_COLUMNS = ("DATUM", "VON", "BIS", "TITEL")
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # index = date.weekday()
SHORT_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# A "module code" like IN2005, MA3305 or CSE... (used to strip clutter from titles).
_CODE = re.compile(r"^[A-Z]{2,4}\d{3,5}$")
# "<room code>, <room name> (<TUM building id>)", e.g. "01.02.003, Lecture Hall B (9999.EG.003)"
_ROOM = re.compile(r"^(?P<code>[^,]+),\s*(?P<name>.*?)\s*(?:\((?P<id>\d{4}\.[\w.]+)\))?$")


# ------------------------------------------------------------------ helpers ---

def hm(minutes: int) -> str:
    """Minutes after midnight -> "HH:MM"."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


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
    """TUMonline CSV rows -> event dicts (sorted, de-duplicated, with lanes)."""
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
_TOP_LEVEL = {"travel", "schedule", "lectures", "holidays", "day_overrides"}
_TRAVEL = {"home_to_tum", "tum_to_job", "job_to_tum", "home_to_job", "job_to_home"}
_SCHEDULE = {"earliest_wake_up", "ready_minutes", "latest_at_job", "earliest_at_job",
             "min_time_at_company", "max_shift_minutes", "buffer_minutes", "work_days",
             "weekly_target_hours"}
_LECTURES = {"not_attended", "sessions_not_attended", "show_skipped"}
_HOLIDAYS = {"no_work"}
_OVERRIDE = {"latest_at_job", "earliest_at_job"}


@dataclass(frozen=True)
class Config:
    # travel, all in minutes
    home_to_tum: int
    tum_to_job: int
    job_to_tum: int
    home_to_job: int
    job_to_home: int
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
    # lectures
    not_attended: frozenset[str]                       # normalized LV numbers
    sessions_not_attended: frozenset[tuple[str, str]]  # (normalized LV number, LV_ART)
    show_skipped: bool
    # holidays: inclusive date ranges without work
    no_work: tuple[tuple[date, date], ...]
    # per weekday (date.weekday()) overrides of latest/earliest_at_job
    day_overrides: dict[int, dict[str, int]]


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


def _parse_date(text: str, name: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ConfigError(f'{name}: expected a date like "2026-12-24", got {text!r}') from None


def _parse_no_work(value, name: str) -> tuple[tuple[date, date], ...]:
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

    schedule = _table(raw, "schedule", _SCHEDULE)
    earliest_wake_up = _get(schedule, "schedule", "earliest_wake_up", _parse_clock)
    ready_minutes = _get(schedule, "schedule", "ready_minutes", _parse_minutes, 0)
    latest_at_job = _get(schedule, "schedule", "latest_at_job", _parse_clock)
    earliest_at_job = _get(schedule, "schedule", "earliest_at_job", _parse_clock, None)
    min_time = _get(schedule, "schedule", "min_time_at_company", _parse_minutes)
    max_shift = _get(schedule, "schedule", "max_shift_minutes", _parse_minutes, None)
    buffer_minutes = _get(schedule, "schedule", "buffer_minutes", _parse_minutes, 0)
    work_days = _get(schedule, "schedule", "work_days", _parse_weekdays,
                     frozenset(range(5)))
    target = _get(schedule, "schedule", "weekly_target_hours", _parse_hours, None)

    lectures = _table(raw, "lectures", _LECTURES)
    not_attended = _get(lectures, "lectures", "not_attended",
                        lambda v, n: _str_list(v, n), [])
    sessions_raw = _get(lectures, "lectures", "sessions_not_attended",
                        lambda v, n: _str_list(v, n), [])
    sessions = set()
    for item in sessions_raw:
        number, sep, kind = item.partition(":")
        if not sep or not normalize_lv(number) or not kind.strip():
            raise ConfigError(f'lectures.sessions_not_attended: expected "LV_NUMMER:LV_ART", got {item!r}')
        sessions.add((normalize_lv(number), kind.strip().upper()))
    show_skipped = _get(lectures, "lectures", "show_skipped",
                        lambda v, n: _bool(v, n), True)

    holidays = _table(raw, "holidays", _HOLIDAYS)
    no_work = _get(holidays, "holidays", "no_work", _parse_no_work, ())

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
        home_to_job=home_to_job, job_to_home=job_to_home,
        earliest_wake_up=earliest_wake_up, ready_minutes=ready_minutes,
        latest_at_job=latest_at_job, earliest_at_job=earliest_at_job,
        min_time_at_company=min_time, max_shift_minutes=max_shift,
        buffer_minutes=buffer_minutes, work_days=work_days,
        weekly_target_minutes=None if target is None else target,
        not_attended=frozenset(normalize_lv(n) for n in not_attended if normalize_lv(n)),
        sessions_not_attended=frozenset(sessions),
        show_skipped=show_skipped,
        no_work=no_work,
        day_overrides=overrides,
    )


def _str_list(value, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f'{name}: expected a list of strings like ["0000000101"]')
    return value


def _bool(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name}: expected true or false, got {value!r}")
    return value


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
        "earliest_wake_up": hm(cfg.earliest_wake_up),
        "ready_minutes": cfg.ready_minutes,
        "latest_at_job": hm(cfg.latest_at_job),
        "earliest_at_job": None if cfg.earliest_at_job is None else hm(cfg.earliest_at_job),
        "min_time_at_company": cfg.min_time_at_company,
        "max_shift_minutes": cfg.max_shift_minutes,
        "buffer_minutes": cfg.buffer_minutes,
        "work_days": sorted(day + 1 for day in cfg.work_days),  # ISO: 1 = Monday
        "weekly_target_minutes": cfg.weekly_target_minutes,
        "not_attended": sorted(cfg.not_attended),
        "sessions_not_attended": sorted(f"{n}:{k}" for n, k in cfg.sessions_not_attended),
        "show_skipped": cfg.show_skipped,
        "no_work": [a.isoformat() if a == b else f"{a.isoformat()}..{b.isoformat()}"
                    for a, b in cfg.no_work],
        "day_overrides": {
            WEEKDAY_NAMES[day]: {k: hm(v) for k, v in values.items()}
            for day, values in sorted(cfg.day_overrides.items())
        },
    }


# ------------------------------------------------------------ the algorithm ---

def merge_intervals(intervals) -> list[tuple[int, int]]:
    """Sort (start, end) pairs and merge the ones that overlap or touch."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


@dataclass(frozen=True)
class Slot:
    """A time window in which the user can work at the job."""

    day: date
    start: int          # minutes after midnight, time of arrival at the job
    end: int            # time of leaving the job
    arrive_from: str    # "home" (no lecture before) or "tum"
    leave_to: str       # "home" (no lecture after) or "tum"

    @property
    def minutes(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Leg:
    """A travel block drawn in the timetable."""

    day: date
    start: int
    end: int
    kind: str           # home_to_tum, home_to_job, tum_to_job, job_to_tum, job_to_home, tum_to_home


def work_slots(day: date, lectures: list[tuple[int, int]], cfg: Config) -> list[Slot]:
    """All possible work slots of one day.

    `lectures` are the (start, end) minutes of the attended lectures on that day.
    """
    if day.weekday() not in cfg.work_days:
        return []
    if any(first <= day <= last for first, last in cfg.no_work):
        return []

    override = cfg.day_overrides.get(day.weekday(), {})
    latest = override.get("latest_at_job", cfg.latest_at_job)
    opening = override.get("earliest_at_job", cfg.earliest_at_job)
    opening = 0 if opening is None else opening
    buffer = cfg.buffer_minutes
    leave_home = cfg.earliest_wake_up + cfg.ready_minutes

    blocks = merge_intervals(lectures)
    windows: list[tuple[int, int, str, str]]  # (start, end, arrive_from, leave_to)
    if not blocks:
        windows = [(leave_home + cfg.home_to_job, latest, "home", "home")]
    else:
        windows = [(leave_home + cfg.home_to_job, blocks[0][0] - cfg.job_to_tum - buffer,
                    "home", "tum")]
        for (_, previous_end), (next_start, _) in pairwise(blocks):
            windows.append((previous_end + cfg.tum_to_job + buffer,
                            next_start - cfg.job_to_tum - buffer, "tum", "tum"))
        windows.append((blocks[-1][1] + cfg.tum_to_job + buffer, latest, "tum", "home"))

    slots = []
    for start, end, arrive_from, leave_to in windows:
        start = max(start, opening)
        end = min(end, latest)
        if cfg.max_shift_minutes is not None:
            end = min(end, start + cfg.max_shift_minutes)
        if end - start >= cfg.min_time_at_company:
            slots.append(Slot(day, start, end, arrive_from, leave_to))
    return slots


def travel_legs(day: date, blocks: list[tuple[int, int]], slots: list[Slot],
                cfg: Config) -> list[Leg]:
    """Travel blocks of one day, matching the slots and the lectures."""
    legs: list[Leg] = []
    for slot in slots:
        if slot.arrive_from == "home":
            legs.append(Leg(day, slot.start - cfg.home_to_job, slot.start, "home_to_job"))
        else:
            legs.append(Leg(day, slot.start - cfg.tum_to_job, slot.start, "tum_to_job"))
        if slot.leave_to == "home":
            legs.append(Leg(day, slot.end, slot.end + cfg.job_to_home, "job_to_home"))
        else:
            legs.append(Leg(day, slot.end, slot.end + cfg.job_to_tum, "job_to_tum"))
    if blocks:
        if not any(s.arrive_from == "home" and s.leave_to == "tum" for s in slots):
            first = blocks[0][0]
            legs.append(Leg(day, first - cfg.home_to_tum, first, "home_to_tum"))
        if not any(s.arrive_from == "tum" and s.leave_to == "home" for s in slots):
            last = blocks[-1][1]
            legs.append(Leg(day, last, last + cfg.home_to_tum, "tum_to_home"))
    return legs


@dataclass
class Plan:
    slots: list[Slot]
    legs: list[Leg]
    weeks: list[dict]   # one dict per Monday-to-Sunday week
    first_day: date
    last_day: date


def build_plan(events: list[dict], cfg: Config) -> Plan:
    attended: dict[date, list[tuple[int, int]]] = {}
    for event in events:
        if not event["skipped"]:
            day = date.fromisoformat(event["date"])
            attended.setdefault(day, []).append((event["start_min"], event["end_min"]))

    first = date.fromisoformat(min(e["date"] for e in events))
    last = date.fromisoformat(max(e["date"] for e in events))
    start = monday_of(first)
    end = monday_of(last) + timedelta(days=6)

    slots: list[Slot] = []
    legs: list[Leg] = []
    weeks: list[dict] = []
    week_start = start
    while week_start <= end:
        week_slots: list[Slot] = []
        lecture_minutes = 0
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            blocks = merge_intervals(attended.get(day, []))
            lecture_minutes += sum(e - s for s, e in blocks)
            day_slots = work_slots(day, attended.get(day, []), cfg)
            week_slots.extend(day_slots)
            legs.extend(travel_legs(day, blocks, day_slots, cfg))
        slots.extend(week_slots)
        possible = sum(s.minutes for s in week_slots)
        weeks.append({
            "monday": week_start,
            "lecture_minutes": lecture_minutes,
            "work_minutes": possible,
            "target_minutes": cfg.weekly_target_minutes,
            "days_with_work": len({s.day for s in week_slots}),
        })
        week_start += timedelta(days=7)

    return Plan(slots=slots, legs=legs, weeks=weeks, first_day=first, last_day=last)


# --------------------------------------------------------------- output ---

def plan_to_json(events: list[dict], plan: Plan, cfg: Config) -> dict:
    return {
        "config": config_for_output(cfg),
        "events": events,
        "slots": [
            {
                "date": s.day.isoformat(),
                "weekday": s.day.isoweekday(),
                "start": hm(s.start), "end": hm(s.end),
                "start_min": s.start, "end_min": s.end,
                "minutes": s.minutes,
                "arrive_from": s.arrive_from, "leave_to": s.leave_to,
            }
            for s in plan.slots
        ],
        "travel": [
            {"date": leg.day.isoformat(), "start_min": leg.start,
             "end_min": leg.end, "kind": leg.kind}
            for leg in plan.legs
        ],
        "weeks": [
            {
                "monday": w["monday"].isoformat(),
                "week": w["monday"].isocalendar().week,
                "lecture_minutes": w["lecture_minutes"],
                "work_minutes": w["work_minutes"],
                "target_minutes": w["target_minutes"],
                "days_with_work": w["days_with_work"],
            }
            for w in plan.weeks
        ],
    }


def hours(minutes: int) -> str:
    return f"{minutes // 60}h{minutes % 60:02d}"


def print_summary(events: list[dict], plan: Plan, cfg: Config) -> None:
    attended = sum(1 for e in events if not e["skipped"])
    print(f"{len(events)} sessions ({plan.first_day.isoformat()} .. {plan.last_day.isoformat()}), "
          f"{attended} attended, {len(events) - attended} skipped")
    if cfg.no_work:
        print("no work: " + ", ".join(f"{a:%d.%m.%Y}..{b:%d.%m.%Y}" for a, b in cfg.no_work))
    for week in plan.weeks:
        monday = week["monday"]
        sunday = monday + timedelta(days=6)
        line = (f"\nKW {monday.isocalendar().week:02d}  {monday:%d.%m.}-{sunday:%d.%m.%Y}   "
                f"possible work {hours(week['work_minutes'])}")
        if cfg.weekly_target_minutes is not None:
            delta = week["work_minutes"] - cfg.weekly_target_minutes
            sign = "+" if delta >= 0 else "-"
            line += (f"   (target {hours(cfg.weekly_target_minutes)}: "
                     f"{sign}{hours(abs(delta))})")
        print(line)
        for offset in range(7):
            day = monday + timedelta(days=offset)
            if day.weekday() not in cfg.work_days:
                continue
            day_slots = [s for s in plan.slots if s.day == day]
            text = ", ".join(f"{hm(s.start)}-{hm(s.end)} ({hours(s.minutes)})" for s in day_slots)
            print(f"  {SHORT_DAYS[day.weekday()]} {day:%d.%m.}  {text or '-'}")


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

    mark_skipped(events, config)
    layout_lanes(events)
    plan = build_plan(events, config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = plan_to_json(events, plan, config)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print_summary(events, plan, config)
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
