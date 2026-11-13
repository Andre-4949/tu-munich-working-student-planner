"""Choosing the days of a week: the lowest total travel that reaches the target hours."""

from __future__ import annotations


from planner.days import DayCandidates, visit_choices


def select_week(cands: list[DayCandidates], target: int, limit: int, min_time: int,
                break_minutes: int = 0):
    """Pick one option per day (and a visit length) that reaches `target` work at least cost.

    Dynamic programme over the paid work planned so far (in STEP minutes, never above `limit`).
    Returns {day: (option, visit_minutes, work_minutes)} for the days that get a planned visit.
    """
    states: dict[int, tuple[int, tuple]] = {0: (0, ())}
    for cand in cands:
        # (option, visit length, work length, cost); the baseline has no visit and no work
        choices = [(None, 0, 0, 0)]
        for option in cand.visits:
            for visit in visit_choices(option, min_time):
                work = visit - break_minutes if len(option.visits) == 1 else option.work
                choices.append((option, visit, work, option.cost))
        nxt: dict[int, tuple[int, tuple]] = {}
        for hours, (cost, chosen) in states.items():
            for option, visit, work, extra in choices:
                total = hours + work
                if total > limit:
                    continue
                new_cost = cost + extra
                if total not in nxt or new_cost < nxt[total][0]:
                    nxt[total] = (new_cost, chosen + ((cand.day, option, visit, work),))
        states = nxt

    reached = [(cost, -hours, chosen) for hours, (cost, chosen) in states.items() if hours >= target]
    if reached:
        _, _, chosen = min(reached, key=lambda r: (r[0], r[1]))
    else:
        best_hours = max(states)
        chosen = states[best_hours][1]
    return {day: (option, visit, work) for day, option, visit, work in chosen if option is not None}
