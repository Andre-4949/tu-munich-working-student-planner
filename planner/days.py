"""The options of one day: every walk combination, its visit and its extra travel."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from planner.config import Config
from planner.constants import CAR, CAR_HOME, JOB, STEP
from planner.timing import Gap, GapSpec, build_specs, day_limits, schedule_gap
from planner.travel import Leg, enumerate_walks


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
        self.visit_minutes = sum(leave - arrive for arrive, leave in self.visits)
        # paid work = time at the company minus the break taken in each visit
        self.work = sum(leave - arrive - cfg.break_minutes for arrive, leave in self.visits)
        self.extra = 0                # travel above the cheapest commute without work

    @property
    def cost(self) -> int:
        """Extra travel of the day, in minutes. A visit adds its trips, so visit days cost more."""
        return self.extra

    @property
    def fuel_eur(self) -> float | None:
        """Estimated fuel for the car legs of this option; None without a fuel estimate."""
        car = self.cfg.car
        if car is None or car.distance_km is None:
            return None
        car_legs = sum(1 for leg in self.legs if leg.mode == CAR)
        return round(car_legs * car.distance_km * car.liters_per_100km / 100 * car.fuel_price, 2)

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
        result.extra = self.extra
        return result


def combine_stretches(day, specs, index, car, cfg, opening, latest, allow_visit):
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
        for rest in combine_stretches(day, specs, index + 1, car_end, cfg, opening, latest, allow_visit):
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
    for combo in combine_stretches(day, specs, 0, CAR_HOME, cfg, opening, latest, allow_visit):
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
    """Possible visit lengths (break included): the full length, or shorter in steps of STEP."""
    if len(option.visits) != 1:
        return [option.visit_minutes]
    full = option.visit_minutes
    first = math.ceil(min_time / STEP) * STEP
    return [full] + [minutes for minutes in range(first, full, STEP)]
