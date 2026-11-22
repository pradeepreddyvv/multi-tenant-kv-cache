"""Pure offline allocation controller; does not apply quotas to a cache."""

from copy import deepcopy
from fractions import Fraction
import math

from policy.allocation import (
    adaptive_target,
    as_weight,
    equal_allocation,
    validate_budget,
    validate_tenants,
)


CONFIG = {
    "alpha": "0.5",
    "floor_fraction": "0.20",
    "threshold_fraction": "0.05",
    "transfer_fraction": "0.10",
    "interval_s": 5,
    "max_gap_s": 10,
}

COUNTERS = (
    "eligible_input_tokens",
    "retained_bytes",
    "retrieved_tokens",
    "errors",
)


def initial_state(tenant_ids, budget_bytes):
    """Begin an episode; membership and budget remain fixed within it."""
    validate_budget(budget_bytes)
    tenants = validate_tenants(tenant_ids)
    return {
        "tenants": list(tenants),
        "budget_bytes": budget_bytes,
        "config": dict(CONFIG),
        "quotas": equal_allocation(tenants, budget_bytes),
        "demand": {t: "0" for t in tenants},
        "last_window_end_s": None,
        "reason": "initialized_equal",
        "moved_bytes": 0,
    }


def _finite_timestamp(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_state(state, budget_bytes):
    validate_budget(budget_bytes)
    tenants = validate_tenants(state["tenants"])
    if state["budget_bytes"] != budget_bytes:
        raise ValueError("budget changed; initialize a new episode")
    if state["config"] != CONFIG:
        raise ValueError("unsupported or changed controller configuration")
    if set(state["quotas"]) != set(tenants):
        raise ValueError("state quota membership mismatch")
    if set(state["demand"]) != set(tenants):
        raise ValueError("state demand membership mismatch")

    quotas = state["quotas"]
    if any(type(q) is not int or q < 0 for q in quotas.values()):
        raise ValueError("invalid state quotas")
    if sum(quotas.values()) != budget_bytes:
        raise ValueError("state quotas do not preserve budget")

    floors = equal_allocation(tenants, budget_bytes // 5)
    if any(quotas[t] < floors[t] for t in tenants):
        raise ValueError("state violates minimum allocations")
    for value in state["demand"].values():
        as_weight(value)

    last = state["last_window_end_s"]
    if last is not None and not _finite_timestamp(last):
        raise ValueError("invalid previous timestamp")
    return tenants


def _hold(state, reason):
    next_state = deepcopy(state)
    next_state["reason"] = reason
    next_state["moved_bytes"] = 0
    return dict(next_state["quotas"]), next_state


def _observations(observations, tenants):
    """Return validated observations or a telemetry failure reason."""
    if not isinstance(observations, (list, tuple)):
        return None, "invalid_observation_container"

    by_tenant = {}
    for row in observations:
        if not isinstance(row, dict):
            return None, "invalid_observation"
        tenant = row.get("tenant_id")
        if not isinstance(tenant, str) or not tenant.strip():
            return None, "invalid_tenant_id"
        if tenant in by_tenant:
            raise ValueError("duplicate observation tenant IDs")
        if tenant not in tenants:
            raise ValueError("new tenant; register a new episode")
        by_tenant[tenant] = row

    if set(by_tenant) != set(tenants):
        return None, "missing_tenant"

    for row in by_tenant.values():
        if not _finite_timestamp(row.get("window_end_s")):
            return None, "invalid_timestamp"
        for field in COUNTERS:
            value = row.get(field)
            if type(value) is not int or value < 0:
                return None, "invalid_counter:" + field
        if row["retrieved_tokens"] > row["eligible_input_tokens"]:
            return None, "retrieved_exceeds_eligible"
        if row["errors"] != 0:
            return None, "telemetry_errors"

    times = {row["window_end_s"] for row in by_tenant.values()}
    if len(times) != 1:
        return None, "unequal_window_timestamps"
    return by_tenant, None


def _transfer(previous, target, cap):
    """Greedily approach target, counting each transferred byte once."""
    quotas = dict(previous)
    donors = sorted(
        (t for t in previous if previous[t] > target[t]),
        key=lambda t: (-(previous[t] - target[t]), t),
    )
    receivers = sorted(
        (t for t in previous if previous[t] < target[t]),
        key=lambda t: (-(target[t] - previous[t]), t),
    )

    moved = 0
    donor_index = 0
    for receiver in receivers:
        while quotas[receiver] < target[receiver] and moved < cap:
            if donor_index >= len(donors):
                return quotas, moved
            donor = donors[donor_index]
            amount = min(
                quotas[donor] - target[donor],
                target[receiver] - quotas[receiver],
                cap - moved,
            )
            quotas[donor] -= amount
            quotas[receiver] += amount
            moved += amount
            if quotas[donor] == target[donor]:
                donor_index += 1
    return quotas, moved


def policy(observations, budget_bytes, state):
    """Return requested quotas and new state; never mutate caller inputs."""
    tenants = _validate_state(state, budget_bytes)
    rows, failure = _observations(observations, tenants)
    if failure:
        return _hold(state, failure)

    timestamp = rows[tenants[0]]["window_end_s"]
    last = state["last_window_end_s"]
    if last is not None:
        elapsed = timestamp - last
        if elapsed <= 0:
            return _hold(state, "stale_or_repeated_window")
        if elapsed > CONFIG["max_gap_s"]:
            return _hold(state, "observation_gap")
        if elapsed < CONFIG["interval_s"]:
            return _hold(state, "window_too_early")

    alpha = Fraction(CONFIG["alpha"])
    demand = {
        t: alpha * rows[t]["eligible_input_tokens"]
        + (1 - alpha) * as_weight(state["demand"][t])
        for t in tenants
    }
    target = adaptive_target(demand, budget_bytes, CONFIG["floor_fraction"])
    needed = sum(max(target[t] - state["quotas"][t], 0) for t in tenants)

    next_state = deepcopy(state)
    next_state["demand"] = {t: str(demand[t]) for t in tenants}
    next_state["last_window_end_s"] = timestamp
    next_state["moved_bytes"] = 0

    if needed == 0:
        next_state["reason"] = "at_target"
    elif needed < Fraction(CONFIG["threshold_fraction"]) * budget_bytes:
        next_state["reason"] = "below_threshold"
    else:
        cap = budget_bytes // 10
        if cap == 0:
            next_state["reason"] = "integer_transfer_cap_zero"
        else:
            quotas, moved = _transfer(state["quotas"], target, cap)
            next_state["quotas"] = quotas
            next_state["moved_bytes"] = moved
            next_state["reason"] = "transferred"

    return dict(next_state["quotas"]), next_state
