"""Synthetic controller checks; no cache or inference performance claims."""

from copy import deepcopy
import json
import random
import unittest

from policy.allocation import equal_allocation
from policy.controller import initial_state, policy


def observations(demand, timestamp=5):
    return [
        {
            "tenant_id": tenant,
            "window_end_s": timestamp,
            "eligible_input_tokens": tokens,
            "retained_bytes": 0,
            "retrieved_tokens": 0,
            "errors": 0,
        }
        for tenant, tokens in demand.items()
    ]


class ControllerTests(unittest.TestCase):
    def test_first_transfer_matches_worked_example(self):
        state = initial_state(["A", "B", "C", "D"], 100)
        quotas, new = policy(
            observations({"A": 70, "B": 10, "C": 10, "D": 10}),
            100, state,
        )
        self.assertEqual(quotas, {"A": 35, "B": 15, "C": 25, "D": 25})
        self.assertEqual(new["moved_bytes"], 10)
        self.assertEqual(new["demand"]["A"], "35")

    def test_hysteresis_holds_small_change(self):
        state = initial_state(["A", "B"], 100)
        quotas, new = policy(observations({"A": 51, "B": 49}), 100, state)
        self.assertEqual(quotas, {"A": 50, "B": 50})
        self.assertEqual(new["reason"], "below_threshold")
        self.assertEqual(new["last_window_end_s"], 5)

    def test_invalid_telemetry_preserves_valid_state(self):
        state = initial_state(["A", "B"], 100)
        _, state = policy(observations({"A": 9, "B": 1}), 100, state)

        cases = []
        cases.append(observations({"A": 9}, 10))
        for field, value in [
            ("eligible_input_tokens", -1),
            ("retained_bytes", None),
            ("retrieved_tokens", 100),
            ("errors", 1),
            ("window_end_s", float("nan")),
        ]:
            rows = observations({"A": 9, "B": 1}, 10)
            rows[0][field] = value
            cases.append(rows)

        unequal = observations({"A": 9, "B": 1}, 10)
        unequal[0]["window_end_s"] = 11
        cases.append(unequal)

        for rows in cases:
            with self.subTest(rows=rows):
                quotas, new = policy(rows, 100, state)
                self.assertEqual(quotas, state["quotas"])
                self.assertEqual(new["demand"], state["demand"])
                self.assertEqual(
                    new["last_window_end_s"], state["last_window_end_s"]
                )
                self.assertEqual(new["moved_bytes"], 0)

    def test_missing_field_holds(self):
        state = initial_state(["A"], 100)
        rows = observations({"A": 10})
        del rows[0]["retained_bytes"]
        _, new = policy(rows, 100, state)
        self.assertEqual(new["reason"], "invalid_counter:retained_bytes")

    def test_timing_failures_hold(self):
        state = initial_state(["A"], 100)
        _, state = policy(observations({"A": 1}, 5), 100, state)
        for timestamp, reason in [
            (5, "stale_or_repeated_window"),
            (4, "stale_or_repeated_window"),
            (7, "window_too_early"),
            (20, "observation_gap"),
        ]:
            with self.subTest(timestamp=timestamp):
                _, new = policy(observations({"A": 1}, timestamp), 100, state)
                self.assertEqual(new["reason"], reason)
                self.assertEqual(new["last_window_end_s"], 5)

    def test_membership_and_budget_changes_require_reset(self):
        state = initial_state(["A"], 100)
        with self.assertRaises(ValueError):
            policy(observations({"A": 1, "B": 1}), 100, state)
        with self.assertRaises(ValueError):
            policy(observations({"A": 1}), 101, state)
        with self.assertRaises(ValueError):
            policy(observations({"A": 1}) * 2, 100, state)
        reset = initial_state(["A", "B"], 100)
        self.assertEqual(reset["quotas"], {"A": 50, "B": 50})

    def test_inputs_and_returned_quotas_are_independent(self):
        state = initial_state(["A", "B"], 100)
        rows = observations({"A": 90, "B": 10})
        before_state, before_rows = deepcopy(state), deepcopy(rows)
        quotas, new = policy(rows, 100, state)
        self.assertEqual(state, before_state)
        self.assertEqual(rows, before_rows)
        quotas["A"] = -1
        self.assertGreaterEqual(new["quotas"]["A"], 0)

    def test_zero_demand_and_tiny_budget(self):
        state = initial_state(["A", "B"], 7)
        quotas, new = policy(observations({"A": 0, "B": 0}), 7, state)
        self.assertEqual(quotas, {"A": 4, "B": 3})
        self.assertEqual(new["reason"], "at_target")
        quotas, new = policy(observations({"A": 0, "B": 100}, 10), 7, new)
        self.assertEqual(quotas, {"A": 4, "B": 3})
        self.assertEqual(new["reason"], "integer_transfer_cap_zero")

    def test_recovers_toward_shifted_demand(self):
        state = initial_state(["A", "B", "C", "D"], 1000)
        for step in range(1, 41):
            hot = "A" if step <= 20 else "B"
            demand = {t: 1000 if t == hot else 0 for t in state["tenants"]}
            _, state = policy(observations(demand, step * 5), 1000, state)
            if step == 20:
                self.assertGreater(state["quotas"]["A"], state["quotas"]["B"])
        self.assertGreater(state["quotas"]["B"], state["quotas"]["A"])

    def test_long_sequences_preserve_invariants(self):
        for count in (4, 8, 16):
            rng = random.Random(11)
            tenants = [f"T{i:02d}" for i in range(count)]
            budget = 10003
            state = initial_state(tenants, budget)
            floors = equal_allocation(tenants, budget // 5)
            for step in range(1, 201):
                demand = {t: rng.randrange(10001) for t in tenants}
                if step % 20 == 0:
                    demand = {t: 0 for t in tenants}
                rows = observations(demand, step * 5)
                before = deepcopy(state)
                quotas, new = policy(rows, budget, state)
                again = policy(rows, budget, state)
                self.assertEqual((quotas, new), again)
                self.assertEqual(state, before)
                self.assertEqual(sum(quotas.values()), budget)
                self.assertTrue(all(type(q) is int for q in quotas.values()))
                self.assertTrue(all(quotas[t] >= floors[t] for t in tenants))
                moved = sum(
                    max(quotas[t] - state["quotas"][t], 0) for t in tenants
                )
                self.assertEqual(moved, new["moved_bytes"])
                self.assertLessEqual(moved, budget // 10)
                state = json.loads(json.dumps(new))


if __name__ == "__main__":
    unittest.main()
