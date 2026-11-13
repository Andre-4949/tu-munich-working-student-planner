"""The settings from config.toml as typed objects, with their validation."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from planner.clock import hm
from planner.config_parse import get_value, parse_blocked_times, parse_bool, parse_clock, parse_date, parse_hours, parse_minutes, parse_positive, parse_ranges, parse_str_list, parse_weekdays, table_section
from planner.constants import WEEKDAY_NAMES
from planner.errors import ConfigError
from planner.tumonline import normalize_lv


_TOP_LEVEL = {"travel", "car", "schedule", "lectures", "holidays", "calendar", "day_overrides"}


_TRAVEL = {"home_to_tum", "tum_to_job", "job_to_tum", "home_to_job", "job_to_home"}


_CAR = {"home_to_tum", "home_to_job", "tum_to_job", "job_to_tum", "job_to_home", "tum_to_home",
        "distance_in_km", "liters_per_100km", "fuel_price_per_liter"}


_FUEL_KEYS = ("distance_in_km", "liters_per_100km", "fuel_price_per_liter")


_SCHEDULE = {"earliest_wake_up", "ready_minutes", "latest_at_job", "earliest_at_job",
             "min_time_at_company", "max_shift_minutes", "break_minutes", "buffer_minutes", "work_days",
             "weekly_target_hours", "max_hours_per_week"}


_LECTURES = {"not_attended", "sessions_not_attended", "show_skipped"}


_HOLIDAYS = {"no_work", "company_closed", "no_work_durations"}


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
    # fuel estimate: every car leg drives distance_km; all three are needed, or none
    distance_km: float | None = None
    liters_per_100km: float | None = None
    fuel_price: float | None = None


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
    min_time_at_company: int       # minimum length of a visit, break included
    break_minutes: int             # break taken during each visit; not paid work time
    max_shift_minutes: int | None
    buffer_minutes: int
    work_days: frozenset[int]      # date.weekday() values, 0 = Monday
    weekly_target_minutes: int | None
    max_week_minutes: int | None   # never plan more than this per week (defaults to the target)
    # lectures
    not_attended: frozenset[str]                       # normalized LV numbers
    sessions_not_attended: frozenset[tuple[str, str]]  # (normalized LV number, LV_ART)
    show_skipped: bool
    # no work at the job: inclusive date ranges (company closures and personal days off)
    no_work: tuple[tuple[date, date], ...]
    # single days with a timed blocker (day, start, end in minutes): no work before `end` that day
    no_work_durations: tuple[tuple[date, int, int], ...]
    # per weekday (date.weekday()) overrides of latest/earliest_at_job
    day_overrides: dict[int, dict[str, int]]
    # the planned range; None means "from the first to the last session of the export"
    calendar_start: date | None
    calendar_end: date | None


def config_from_dict(raw: dict) -> Config:
    """Validate the parsed TOML and build the Config. A ConfigError names the key that is wrong."""
    unknown = sorted(set(raw) - _TOP_LEVEL)
    if unknown:
        raise ConfigError(f"unknown section(s): {', '.join(unknown)} (typo?)")
    travel = _travel(raw)
    car = _car(raw)
    schedule = _schedule(raw)
    _check_schedule(schedule)
    return Config(
        car=car,
        day_overrides=_day_overrides(raw),
        **travel,
        **schedule,
        **_lectures(raw),
        **_holidays(raw),
        **_calendar(raw),
    )


def _travel(raw: dict) -> dict:
    travel = table_section(raw, "travel", _TRAVEL)
    home_to_tum = get_value(travel, "travel", "home_to_tum", parse_minutes)
    tum_to_job = get_value(travel, "travel", "tum_to_job", parse_minutes)
    home_to_job = get_value(travel, "travel", "home_to_job", parse_minutes, home_to_tum + tum_to_job)
    return {
        "home_to_tum": home_to_tum,
        "tum_to_job": tum_to_job,
        "job_to_tum": get_value(travel, "travel", "job_to_tum", parse_minutes, tum_to_job),
        "home_to_job": home_to_job,
        "job_to_home": get_value(travel, "travel", "job_to_home", parse_minutes, home_to_job),
    }


def _car(raw: dict) -> CarConfig | None:
    if "car" not in raw:
        return None
    table = table_section(raw, "car", _CAR)
    home_to_tum = get_value(table, "car", "home_to_tum", parse_minutes)
    home_to_job = get_value(table, "car", "home_to_job", parse_minutes)
    tum_to_job = get_value(table, "car", "tum_to_job", parse_minutes)
    fuel_given = [key for key in _FUEL_KEYS if key in table]
    if fuel_given and len(fuel_given) != len(_FUEL_KEYS):
        raise ConfigError("[car]: the fuel estimate needs all of distance_in_km, "
                          "liters_per_100km and fuel_price_per_liter (or none of them)")
    return CarConfig(
        home_to_tum=home_to_tum,
        home_to_job=home_to_job,
        tum_to_job=tum_to_job,
        job_to_tum=get_value(table, "car", "job_to_tum", parse_minutes, tum_to_job),
        job_to_home=get_value(table, "car", "job_to_home", parse_minutes, home_to_job),
        tum_to_home=get_value(table, "car", "tum_to_home", parse_minutes, home_to_tum),
        distance_km=get_value(table, "car", "distance_in_km", parse_positive, None),
        liters_per_100km=get_value(table, "car", "liters_per_100km", parse_positive, None),
        fuel_price=get_value(table, "car", "fuel_price_per_liter", parse_positive, None),
    )


def _schedule(raw: dict) -> dict:
    schedule = table_section(raw, "schedule", _SCHEDULE)
    target = get_value(schedule, "schedule", "weekly_target_hours", parse_hours, None)
    max_week = get_value(schedule, "schedule", "max_hours_per_week", parse_hours, None)
    if max_week is None:
        max_week = target
    if target is not None and max_week is not None and max_week < target:
        raise ConfigError("schedule.max_hours_per_week must not be below schedule.weekly_target_hours")
    return {
        "earliest_wake_up": get_value(schedule, "schedule", "earliest_wake_up", parse_clock),
        "ready_minutes": get_value(schedule, "schedule", "ready_minutes", parse_minutes, 0),
        "latest_at_job": get_value(schedule, "schedule", "latest_at_job", parse_clock),
        "earliest_at_job": get_value(schedule, "schedule", "earliest_at_job", parse_clock, None),
        "min_time_at_company": get_value(schedule, "schedule", "min_time_at_company", parse_minutes),
        "break_minutes": get_value(schedule, "schedule", "break_minutes", parse_minutes, 0),
        "max_shift_minutes": get_value(schedule, "schedule", "max_shift_minutes", parse_minutes, None),
        "buffer_minutes": get_value(schedule, "schedule", "buffer_minutes", parse_minutes, 0),
        "work_days": get_value(schedule, "schedule", "work_days", parse_weekdays, frozenset(range(5))),
        "weekly_target_minutes": target,
        "max_week_minutes": max_week,
    }


def _check_schedule(schedule: dict) -> None:
    if schedule["min_time_at_company"] < 1:
        raise ConfigError("schedule.min_time_at_company: must be at least 1 minute")
    if schedule["break_minutes"] > schedule["min_time_at_company"]:
        raise ConfigError("schedule.break_minutes: cannot be longer than schedule.min_time_at_company")
    if not schedule["work_days"]:
        raise ConfigError("schedule.work_days: list at least one weekday")


def _lectures(raw: dict) -> dict:
    lectures = table_section(raw, "lectures", _LECTURES)
    not_attended = get_value(lectures, "lectures", "not_attended", parse_str_list, [])
    sessions = set()
    for item in get_value(lectures, "lectures", "sessions_not_attended", parse_str_list, []):
        number, sep, kind = item.partition(":")
        if not sep or not normalize_lv(number) or not kind.strip():
            raise ConfigError(f'lectures.sessions_not_attended: expected "LV_NUMMER:LV_ART", got {item!r}')
        sessions.add((normalize_lv(number), kind.strip().upper()))
    return {
        "not_attended": frozenset(normalize_lv(n) for n in not_attended if normalize_lv(n)),
        "sessions_not_attended": frozenset(sessions),
        "show_skipped": get_value(lectures, "lectures", "show_skipped", parse_bool, True),
    }


def _holidays(raw: dict) -> dict:
    holidays = table_section(raw, "holidays", _HOLIDAYS)
    no_work = get_value(holidays, "holidays", "no_work", parse_ranges, ())
    closed = get_value(holidays, "holidays", "company_closed", parse_ranges, ())
    return {
        "no_work": tuple(no_work) + tuple(closed),
        "no_work_durations": get_value(holidays, "holidays", "no_work_durations", parse_blocked_times, ()),
    }


def _calendar(raw: dict) -> dict:
    calendar = table_section(raw, "calendar", _CALENDAR)
    start = get_value(calendar, "calendar", "start", parse_date, None)
    end = get_value(calendar, "calendar", "end", parse_date, None)
    if start and end and end < start:
        raise ConfigError("calendar.end is before calendar.start")
    return {"calendar_start": start, "calendar_end": end}


def _day_overrides(raw: dict) -> dict[int, dict[str, int]]:
    block = raw.get("day_overrides", {})
    if not isinstance(block, dict):
        raise ConfigError("[day_overrides] must contain tables such as [day_overrides.fri]")
    overrides: dict[int, dict[str, int]] = {}
    for day_name, table in block.items():
        if day_name not in WEEKDAY_NAMES:
            raise ConfigError(f"[day_overrides.{day_name}]: unknown weekday (use {', '.join(WEEKDAY_NAMES)})")
        if not isinstance(table, dict):
            raise ConfigError(f"[day_overrides.{day_name}] must be a table")
        unknown_keys = sorted(set(table) - _OVERRIDE)
        if unknown_keys:
            raise ConfigError(f"unknown key(s) in [day_overrides.{day_name}]: {', '.join(unknown_keys)}")
        overrides[WEEKDAY_NAMES.index(day_name)] = {
            key: parse_clock(table[key], f"day_overrides.{day_name}.{key}")
            for key in ("latest_at_job", "earliest_at_job") if key in table
        }
    return overrides


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
            "distance_in_km": cfg.car.distance_km,
            "liters_per_100km": cfg.car.liters_per_100km,
            "fuel_price_per_liter": cfg.car.fuel_price,
        },
        "earliest_wake_up": hm(cfg.earliest_wake_up),
        "ready_minutes": cfg.ready_minutes,
        "latest_at_job": hm(cfg.latest_at_job),
        "earliest_at_job": None if cfg.earliest_at_job is None else hm(cfg.earliest_at_job),
        "min_time_at_company": cfg.min_time_at_company,
        "break_minutes": cfg.break_minutes,
        "max_shift_minutes": cfg.max_shift_minutes,
        "buffer_minutes": cfg.buffer_minutes,
        "work_days": sorted(day + 1 for day in cfg.work_days),  # ISO: 1 = Monday
        "weekly_target_minutes": cfg.weekly_target_minutes,
        "max_week_minutes": cfg.max_week_minutes,
        "not_attended": sorted(cfg.not_attended),
        "sessions_not_attended": sorted(f"{n}:{k}" for n, k in cfg.sessions_not_attended),
        "show_skipped": cfg.show_skipped,
        "no_work": [a.isoformat() if a == b else f"{a.isoformat()}..{b.isoformat()}"
                    for a, b in cfg.no_work],
        "no_work_durations": [f"{d.isoformat()} {hm(s)}..{hm(e)}" for d, s, e in cfg.no_work_durations],
        "day_overrides": {
            WEEKDAY_NAMES[day]: {k: hm(v) for k, v in values.items()}
            for day, values in sorted(cfg.day_overrides.items())
        },
        "calendar_start": cfg.calendar_start.isoformat() if cfg.calendar_start else None,
        "calendar_end": cfg.calendar_end.isoformat() if cfg.calendar_end else None,
    }
