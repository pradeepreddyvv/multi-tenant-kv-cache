"""Offline allocation arithmetic checks; no measured inference claims."""

import unittest

from policy.allocation import (
    adaptive_target,
    equal_allocation,
    fixed_unequal_allocation,
)


class AllocationTests(unittest.TestCase):
    def test_equal_rounding_is_deterministic(self):
        self.assertEqual(
            equal_allocation(["D", "B", "A", "C"], 11),
            {"A": 3, "B": 3, "C": 3, "D": 2},
        )

    def test_declared_fixed_weights(self):
        self.assertEqual(
            fixed_unequal_allocation({"A": 7, "B": 1, "C": 1, "D": 1}, 100),
            {"A": 70, "B": 10, "C": 10, "D": 10},
        )

    def test_zero_fixed_weights_use_equal_split(self):
        self.assertEqual(
            fixed_unequal_allocation({"A": 0, "B": 0}, 5),
            {"A": 3, "B": 2},
        )

    def test_worked_adaptive_target(self):
        self.assertEqual(
            adaptive_target({"A": 70, "B": 10, "C": 10, "D": 10}, 100),
            {"A": 61, "B": 13, "C": 13, "D": 13},
        )

    def test_zero_demand_target_is_equal(self):
        self.assertEqual(
            adaptive_target({"A": 0, "B": 0}, 101),
            {"A": 51, "B": 50},
        )

    def test_budget_and_floors_for_4_8_16_tenants(self):
        for count in (4, 8, 16):
            demand = {f"T{i:02d}": i * i for i in range(count)}
            for budget in (0, 1, 7, 101, 2**31):
                with self.subTest(tenants=count, budget=budget):
                    quotas = adaptive_target(demand, budget)
                    floors = equal_allocation(demand, budget // 5)
                    self.assertEqual(sum(quotas.values()), budget)
                    self.assertEqual(set(quotas), set(demand))
                    self.assertTrue(all(type(q) is int for q in quotas.values()))
                    self.assertTrue(all(quotas[t] >= floors[t] for t in demand))

    def test_inputs_are_not_mutated(self):
        weights = {"B": 1, "A": 9}
        before = dict(weights)
        adaptive_target(weights, 103)
        self.assertEqual(weights, before)

    def test_invalid_budgets(self):
        for budget in (-1, 1.5, True):
            with self.subTest(budget=budget):
                with self.assertRaises(ValueError):
                    equal_allocation(["A"], budget)

    def test_invalid_tenants(self):
        for tenants in ([], ["A", "A"], [""], ["  "], [1]):
            with self.subTest(tenants=tenants):
                with self.assertRaises(ValueError):
                    equal_allocation(tenants, 100)

    def test_invalid_weights(self):
        for weight in (-1, "nan", "inf", True, None):
            with self.subTest(weight=weight):
                with self.assertRaises(ValueError):
                    fixed_unequal_allocation({"A": weight}, 100)

    def test_impossible_floor_pool(self):
        with self.assertRaises(ValueError):
            adaptive_target({"A": 1}, 100, floor_fraction="1.01")


if __name__ == "__main__":
    unittest.main()
