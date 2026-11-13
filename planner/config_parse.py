"""Parsers for the values in config.toml. Each one names the key it failed on."""

from __future__ import annotations

import re
from datetime import date

from planner.constants import WEEKDAY_NAMES
from planner.errors import ConfigError


_MISSING = object()


def table_section(raw: dict, name: str, allowed: set[str]) -> dict:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"unknown key(s) in [{name}]: {', '.join(unknown)} (typo?)")
    return value


def get_value(table: dict, section: str, key: str, parse, default=_MISSING):
    name = f"{section}.{key}" if section else key
    if key in table:
        return parse(table[key], name)
    if default is _MISSING:
        raise ConfigError(f"missing required key: {name}")
    return default


def parse_minutes(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name}: expected a whole number of minutes, got {value!r}")
    if value < minimum:
        raise ConfigError(f"{name}: must be at least {minimum}, got {value}")
    return value


def parse_positive(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{name}: expected a positive number, got {value!r}")
    return float(value)


def parse_clock(value, name: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,2}:\d{2}", value):
        raise ConfigError(f'{name}: expected a quoted clock time like "17:00", got {value!r}')
    hours, minutes = (int(part) for part in value.split(":"))
    if hours > 23 or minutes > 59:
        raise ConfigError(f"{name}: {value!r} is not a valid clock time")
    return hours * 60 + minutes


def parse_hours(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{name}: expected a number of hours, got {value!r}")
    return round(value * 60)


def parse_weekdays(value, name: str) -> frozenset[int]:
    if not isinstance(value, list):
        raise ConfigError(f'{name}: expected a list like ["mon", "tue"]')
    days = set()
    for item in value:
        if item not in WEEKDAY_NAMES:
            raise ConfigError(f"{name}: unknown weekday {item!r} (use {', '.join(WEEKDAY_NAMES)})")
        days.add(WEEKDAY_NAMES.index(item))
    return frozenset(days)


def parse_date(text, name: str) -> date:
    if not isinstance(text, str):
        raise ConfigError(f'{name}: expected a date like "2026-12-24", got {text!r}')
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ConfigError(f'{name}: expected a date like "2026-12-24", got {text!r}') from None


def parse_ranges(value, name: str) -> tuple[tuple[date, date], ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f'{name}: expected a list of dates or ranges like "2026-12-24..2027-01-06"')
    ranges = []
    for item in value:
        first, _, last = item.partition("..")
        start = parse_date(first, name)
        end = parse_date(last, name) if last else start
        if end < start:
            raise ConfigError(f"{name}: range {item!r} ends before it starts")
        ranges.append((start, end))
    return tuple(ranges)


def parse_blocked_times(value, name: str) -> tuple[tuple[date, int, int], ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f'{name}: expected a list like ["2026-12-15 10:00..10:30"]')
    blocks = []
    for item in value:
        day_text, sep, times = item.strip().partition(" ")
        start_text, dots, end_text = times.partition("..")
        if not sep or not dots:
            raise ConfigError(f'{name}: expected "YYYY-MM-DD HH:MM..HH:MM", got {item!r}')
        day = parse_date(day_text, name)
        start = parse_clock(start_text, name)
        end = parse_clock(end_text, name)
        if end <= start:
            raise ConfigError(f"{name}: {item!r} ends before it starts")
        blocks.append((day, start, end))
    return tuple(blocks)


def parse_str_list(value, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f'{name}: expected a list of strings like ["0000000101"]')
    return value


def parse_bool(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name}: expected true or false, got {value!r}")
    return value
