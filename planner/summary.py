"""The text summary printed after planning."""

from __future__ import annotations

from datetime import timedelta

from planner.clock import dur, hm
from planner.config import Config
from planner.constants import SHORT_DAYS
from planner.planning import Plan


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
            if result.status == "outside":
                continue
            day_label = f"  {SHORT_DAYS[result.day.weekday()]} {result.day:%d.%m.}"
            if result.status in ("planned", "fallback"):
                option = result.drawn
                visits = ", ".join(f"{hm(a)}-{hm(b)} ({dur(b - a - cfg.break_minutes)} work)"
                                   for a, b in option.visits)
                fuel = "" if option.fuel_eur is None else f", fuel ~{option.fuel_eur:.2f} EUR"
                print(f"{day_label}  {result.status.upper():8} {visits}  by {option.modes}, "
                      f"travel {dur(option.travel)} (extra {dur(option.extra)}), cost {option.cost}{fuel}")
            elif result.best is not None:
                b = result.best
                print(f"{day_label}  available  best {dur(b.work)} by {b.modes}, "
                      f"travel {dur(b.travel)} (extra {dur(b.extra)}), cost {b.cost}")
            elif result.drawn is not None:
                print(f"{day_label}  no work     commute {dur(result.drawn.travel)} by {result.drawn.modes}")
            else:
                print(f"{day_label}  -")
