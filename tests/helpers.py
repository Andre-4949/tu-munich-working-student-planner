"""Shared fixtures and builders for the tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.clock import merge_intervals
from planner.config import config_from_dict
from planner.constants import HOME, JOB, TRANSIT, TUM
from planner.timing import build_specs, day_limits, schedule_gap


ROOT = Path(__file__).resolve().parents[1]


MONDAY = date(2026, 12, 7)


FRIDAY = date(2026, 12, 11)


SUNDAY = date(2026, 12, 13)


def make_config(schedule=None, travel=None, car=None, lectures=None, holidays=None,
                day_overrides=None, calendar=None):
    """Config with the test values: transit home->TUM 40, TUM->job 30, job->TUM 30, home->job 70,
    job->home 70; wake 06:30; latest 17:00; minimum 60 minutes; no buffer."""
    raw = {
        "travel": {"home_to_tum": 40, "tum_to_job": 30, **(travel or {})},
        "schedule": {"earliest_wake_up": "06:30", "latest_at_job": "17:00",
                     "min_time_at_company": 60, **(schedule or {})},
    }
    if car is not None:
        raw["car"] = car
    for key, value in (("lectures", lectures), ("holidays", holidays),
                       ("day_overrides", day_overrides), ("calendar", calendar)):
        if value is not None:
            raw[key] = value
    return config_from_dict(raw)


CAR_TABLE = {"home_to_tum": 25, "home_to_job": 45, "tum_to_job": 45}


def at(hours, minutes=0):
    return hours * 60 + minutes


def direct_transit_visit(day, spec, cfg):
    """The single visit on the direct transit route of one stretch (the old slot rules)."""
    if spec.src == HOME and spec.end == HOME:
        legs = [(HOME, JOB, TRANSIT), (JOB, HOME, TRANSIT)]
    elif spec.src == HOME:
        legs = [(HOME, JOB, TRANSIT), (JOB, TUM, TRANSIT)]
    elif spec.end == HOME:
        legs = [(TUM, JOB, TRANSIT), (JOB, HOME, TRANSIT)]
    else:
        legs = [(TUM, JOB, TRANSIT), (JOB, TUM, TRANSIT)]
    opening, latest = day_limits(day, cfg)
    gap = schedule_gap(day, spec, tuple(legs), cfg, opening, latest)
    return None if gap is None else gap.visit


def transit_windows(day, lectures, cfg):
    """Visit windows of a day when only the direct transit routes are used."""
    specs = build_specs(merge_intervals(lectures), cfg)
    return [direct_transit_visit(day, spec, cfg) for spec in specs]
