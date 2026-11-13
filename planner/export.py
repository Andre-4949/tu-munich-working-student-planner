"""The plan as JSON, the input of the Typst template."""

from __future__ import annotations


from planner.clock import hm
from planner.config import Config, config_for_output
from planner.days import Option
from planner.planning import DayResult, Plan, WeekResult
from planner.supervisor import boss_blocks


def option_json(option: Option | None) -> dict | None:
    if option is None:
        return None
    return {
        "work_minutes": option.work,
        "visit_minutes": option.visit_minutes,
        "travel_minutes": option.travel,
        "extra_minutes": option.extra,
        "fuel_eur": option.fuel_eur,
        "cost": option.cost,
        "cost_per_hour": None if not option.work else round(option.value, 1),
        "modes": option.modes,
        "visits": [{"start": hm(a), "end": hm(b), "start_min": a, "end_min": b,
                    "minutes": b - a} for a, b in option.visits],
    }


def week_fuel(week: WeekResult) -> float | None:
    """Estimated fuel of the planned and fallback days of a week; None without a fuel estimate."""
    fuel = [d.drawn.fuel_eur for d in week.days
            if d.drawn is not None and d.status in ("planned", "fallback")
            and d.drawn.fuel_eur is not None]
    return round(sum(fuel), 2) if fuel else None


def plan_to_json(events: list[dict], plan: Plan, cfg: Config) -> dict:
    """The whole plan as one JSON document, the input of the Typst template."""
    days, travel, slots = [], [], []
    for week in plan.weeks:
        for result in week.days:
            travel += _travel_json(result)
            slots += _slots_json(result, cfg)
            days.append(_day_json(result))
    return {
        "config": config_for_output(cfg),
        "calendar": {"start": plan.first_day.isoformat(), "end": plan.last_day.isoformat()},
        "events": events,
        "days": days,
        "slots": slots,
        "travel": travel,
        "weeks": [_week_json(week) for week in plan.weeks],
        "boss": boss_blocks(plan, cfg),
    }


def _travel_json(result: DayResult) -> list[dict]:
    if result.drawn is None:
        return []
    return [
        {"date": leg.day.isoformat(), "start_min": leg.start, "end_min": leg.end,
         "src": leg.src, "dst": leg.dst, "mode": leg.mode}
        for leg in result.drawn.legs
    ]


def _slots_json(result: DayResult, cfg: Config) -> list[dict]:
    """The visits of a planned or fallback day; work time is the visit minus the break."""
    option = result.drawn
    if result.status not in ("planned", "fallback") or option is None:
        return []
    return [
        {"date": result.day.isoformat(), "weekday": result.day.isoweekday(),
         "start": hm(arrive), "end": hm(leave), "start_min": arrive,
         "end_min": leave, "minutes": leave - arrive,
         "work_minutes": leave - arrive - cfg.break_minutes,
         "status": result.status}
        for arrive, leave in option.visits
    ]


def _day_json(result: DayResult) -> dict:
    return {
        "date": result.day.isoformat(),
        "weekday": result.day.isoweekday(),
        "status": result.status,
        "work_minutes": result.work,
        "drawn": option_json(result.drawn),
        "best": option_json(result.best),
    }


def _week_json(week: WeekResult) -> dict:
    return {
        "monday": week.monday.isoformat(),
        "week": week.monday.isocalendar().week,
        "lecture_minutes": week.lecture_minutes,
        "planned_minutes": week.planned,
        "fallback_minutes": week.fallback,
        "target_minutes": week.target,
        "maximum_minutes": week.maximum,
        "travel_minutes": sum(d.drawn.travel for d in week.days
                              if d.drawn is not None and d.status in ("planned", "fallback")),
        "fuel_eur": week_fuel(week),
    }
