"""The walk rules, including the car."""

from __future__ import annotations

import unittest

from planner.constants import CAR, CAR_HOME, CAR_OUT, HOME, JOB, TRANSIT, TUM
from tests.helpers import CAR_TABLE, make_config
from planner.travel import enumerate_walks


class WalkRuleTests(unittest.TestCase):
    def test_without_car_only_transit(self):
        cfg = make_config()
        for legs, _ in enumerate_walks(HOME, CAR_HOME, TUM, cfg, True):
            self.assertTrue(all(mode == TRANSIT for *_, mode in legs))

    def test_car_legs_follow_the_car_state(self):
        """Simulate the car along every walk: it starts at home, leaves only from home,
        stays out while you are not home, and transit is only used while it is at home."""
        cfg = make_config(car=CAR_TABLE)
        for start, end in ((HOME, HOME), (HOME, TUM), (TUM, HOME), (TUM, TUM)):
            for legs, car_end in enumerate_walks(start, CAR_HOME, end, cfg, True):
                out = False
                for src, dst, mode in legs:
                    if mode == CAR:
                        if not out:
                            self.assertEqual(src, HOME, legs)  # the car is only at home
                        out = dst != HOME
                    else:
                        self.assertFalse(out, legs)  # the car is with you: no transit
                self.assertEqual(car_end, CAR_OUT if out else CAR_HOME, legs)

    def test_at_most_one_visit(self):
        cfg = make_config(car=CAR_TABLE)
        for legs, _ in enumerate_walks(TUM, CAR_HOME, TUM, cfg, True):
            self.assertLessEqual(sum(1 for _, dst, _ in legs if dst == JOB), 1)

    def test_no_visit_when_work_is_not_allowed(self):
        cfg = make_config(car=CAR_TABLE)
        for legs, _ in enumerate_walks(HOME, CAR_HOME, HOME, cfg, False):
            self.assertFalse(any(dst == JOB for _, dst, _ in legs))
