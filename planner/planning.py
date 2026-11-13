"""Building the plan for the calendar range: day candidates, the weekly choice and fallback days."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from planner.clock import merge_intervals, monday_of
from planner.config import Config
from planner.days import DayCandidates, Option, day_candidates
from planner.weekly import select_week


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
    """Plan every week that touches the calendar range [first, last]."""
    attended: dict[date, list[tuple[int, int]]] = {}
    for event in events:
        if not event["skipped"]:
            day = date.fromisoformat(event["date"])
            attended.setdefault(day, []).append((event["start_min"], event["end_min"]))

    end = monday_of(last) + timedelta(days=6)
    weeks: list[WeekResult] = []
    monday = monday_of(first)
    while monday <= end:
        weeks.append(_plan_week(monday, first, last, attended, cfg))
        monday += timedelta(days=7)
    return Plan(first_day=first, last_day=last, weeks=weeks)


def _plan_week(monday: date, first: date, last: date, attended: dict, cfg: Config) -> WeekResult:
    days = [monday + timedelta(days=offset) for offset in range(7)]
    blocks = {d: merge_intervals(attended.get(d, [])) for d in days}
    # days outside the calendar range keep their place in the week but are not planned
    cands = {d: day_candidates(d, blocks[d], cfg) if first <= d <= last
             else DayCandidates(d, None, []) for d in days}
    chosen = _weekly_choice(days, cands, cfg)
    fallback = fallback_days(cands, chosen, cfg.weekly_target_minutes)
    results = [_day_result(d, cands[d], chosen, fallback, first, last) for d in days]
    lecture_minutes = sum(sum(e - s for s, e in blocks[d]) for d in days)
    return WeekResult(monday, results, lecture_minutes, cfg.weekly_target_minutes, cfg.max_week_minutes)


def _weekly_choice(days: list[date], cands: dict[date, DayCandidates], cfg: Config) -> dict:
    """The planned days of a week, as {day: (option, visit, work)}; empty without a target."""
    if cfg.weekly_target_minutes is None:
        return {}
    limit = cfg.max_week_minutes if cfg.max_week_minutes is not None else cfg.weekly_target_minutes
    return select_week([cands[d] for d in days], cfg.weekly_target_minutes, limit,
                       cfg.min_time_at_company, cfg.break_minutes)


def _day_result(d: date, cand: DayCandidates, chosen: dict, fallback: set[date],
                first: date, last: date) -> DayResult:
    if not (first <= d <= last):
        return DayResult(d, "outside", None, None, 0)
    best = min(cand.visits, key=lambda o: (o.value, -o.work)) if cand.visits else None
    if d in chosen:
        option, visit, work = chosen[d]
        drawn = option if visit == option.visit_minutes else option.shortened(visit)
        return DayResult(d, "planned", drawn, best, work)
    if d in fallback:
        return DayResult(d, "fallback", best, best, best.work)
    status = "available" if cand.visits else "none"
    return DayResult(d, status, cand.baseline or best, best, 0)


def fallback_days(cands: dict[date, DayCandidates], chosen: dict, target: int | None) -> set[date]:
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
