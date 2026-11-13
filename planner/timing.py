"""Putting one stretch of a day on the clock: a walk with its visit at the job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from planner.config import Config
from planner.constants import HOME, JOB, TUM
from planner.travel import Leg, leg_minutes


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
        # staying where you are needs no window: a gap shorter than the buffers is still
        # a gap at TUM; only travel has to fit between the lectures
        if legs and spec.t1 is not None and spec.t0 + total > spec.t1:
            return None
        return Gap(chain_legs(day, legs, durations, spec.t0), None)

    before = sum(durations[:visit_index + 1])
    after = sum(durations[visit_index + 1:])
    arrive = max(spec.t0 + before, opening)
    if visit_len is None:
        leave = latest
        if spec.t1 is not None:
            leave = min(leave, spec.t1 - after)
        if cfg.max_shift_minutes is not None:
            # max_shift_minutes is work time; the break is added on top of it
            leave = min(leave, arrive + cfg.max_shift_minutes + cfg.break_minutes)
        if leave - arrive < cfg.min_time_at_company:
            return None
    else:
        leave = arrive + visit_len
    # wait at the origin so that the arrival is exactly `arrive`; leave the job as late as allowed
    before_legs = chain_legs(day, legs[:visit_index + 1], durations[:visit_index + 1], arrive - before)
    after_legs = chain_legs(day, legs[visit_index + 1:], durations[visit_index + 1:], leave)
    return Gap(tuple(before_legs + after_legs), (arrive, leave))


def chain_legs(day: date, legs, durations, start: int) -> list[Leg]:
    out = []
    clock = start
    for (src, dst, mode), minutes in zip(legs, durations):
        out.append(Leg(day, clock, clock + minutes, src, dst, mode))
        clock += minutes
    return out


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
    # a timed blocker (e.g. an exam): no work on that day before the blocker ends
    for block_day, _, end in cfg.no_work_durations:
        if block_day == day:
            opening = end if opening is None else max(opening, end)
    return (0 if opening is None else opening), latest
