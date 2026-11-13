"""Travel legs, and the walks between places in one stretch of a day (including the car rules)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from planner.config import Config
from planner.constants import CAR, CAR_HOME, CAR_OUT, HOME, JOB, MAX_LEGS, PLACES, TRANSIT, TUM


def leg_minutes(cfg: Config, src: str, dst: str, mode: str) -> int:
    """Duration of one leg. Transit times are symmetric where the config has no separate value."""
    if mode == TRANSIT:
        table = {
            (HOME, TUM): cfg.home_to_tum, (TUM, HOME): cfg.home_to_tum,
            (TUM, JOB): cfg.tum_to_job, (JOB, TUM): cfg.job_to_tum,
            (HOME, JOB): cfg.home_to_job, (JOB, HOME): cfg.job_to_home,
        }
    else:
        car = cfg.car
        if car is None:
            raise ValueError("car leg without [car] configuration")
        table = {
            (HOME, TUM): car.home_to_tum, (TUM, HOME): car.tum_to_home,
            (TUM, JOB): car.tum_to_job, (JOB, TUM): car.job_to_tum,
            (HOME, JOB): car.home_to_job, (JOB, HOME): car.job_to_home,
        }
    return table[(src, dst)]


@dataclass(frozen=True)
class Leg:
    """One travel block with its clock times."""

    day: date
    start: int
    end: int
    src: str
    dst: str
    mode: str

    @property
    def minutes(self) -> int:
        return self.end - self.start


def enumerate_walks(src: str, car: str, end: str, cfg: Config,
                    allow_visit: bool) -> list[tuple[tuple[tuple[str, str, str], ...], str]]:
    """All legs from `src` to `end` that respect the car rules and visit the job at most once.

    Returns (legs, car_state_at_end) pairs. Each leg is (from, to, mode).
    """
    found: list[tuple[tuple[tuple[str, str, str], ...], str]] = []

    def walk(loc: str, car_state: str, legs: list, visited: bool) -> None:
        if loc == end:
            found.append((tuple(legs), car_state))
        if len(legs) >= MAX_LEGS:
            return
        for dst in PLACES:
            if dst == loc:
                continue
            if dst == JOB and (not allow_visit or visited):
                continue
            for mode in (TRANSIT, CAR):
                if mode == TRANSIT:
                    if car_state == CAR_OUT:
                        continue  # the car is with you, you cannot leave it behind
                    new_car = car_state
                else:
                    if cfg.car is None:
                        continue
                    if car_state == CAR_OUT:
                        new_car = CAR_HOME if dst == HOME else CAR_OUT
                    elif loc == HOME:
                        new_car = CAR_OUT  # you take the car from home
                    else:
                        continue  # the car is at home, you are not
                walk(dst, new_car, legs + [(loc, dst, mode)], visited or dst == JOB)

    walk(src, car, [], False)
    return found
