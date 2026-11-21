"""Deterministic CPU retained-KV byte allocations; no serving dependencies."""

from fractions import Fraction


def validate_budget(budget_bytes):
    if type(budget_bytes) is not int or budget_bytes < 0:
        raise ValueError("budget_bytes must be a nonnegative integer")


def validate_tenants(tenant_ids):
    tenants = tuple(tenant_ids)
    if not tenants:
        raise ValueError("at least one tenant is required")
    if any(not isinstance(t, str) or not t.strip() for t in tenants):
        raise ValueError("tenant IDs must be nonempty strings")
    if len(set(tenants)) != len(tenants):
        raise ValueError("duplicate tenant IDs")
    return tuple(sorted(tenants))


def as_weight(value):
    if isinstance(value, bool):
        raise ValueError("boolean weights are invalid")
    try:
        weight = Fraction(str(value))
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("weights must be finite numbers") from exc
    if weight < 0:
        raise ValueError("weights must be nonnegative")
    return weight


def proportional_allocation(weights, budget_bytes):
    """Largest-remainder rounding; ties use lexicographic tenant IDs."""
    validate_budget(budget_bytes)
    tenants = validate_tenants(weights.keys())
    weights = {t: as_weight(weights[t]) for t in tenants}
    total = sum(weights.values(), Fraction(0))

    if total == 0:
        weights = {t: Fraction(1) for t in tenants}
        total = Fraction(len(tenants))

    exact = {t: budget_bytes * weights[t] / total for t in tenants}
    quotas = {
        t: exact[t].numerator // exact[t].denominator
        for t in tenants
    }

    remaining = budget_bytes - sum(quotas.values())
    order = sorted(
        tenants,
        key=lambda t: (-(exact[t] - quotas[t]), t),
    )
    for tenant in order[:remaining]:
        quotas[tenant] += 1

    return quotas


def equal_allocation(tenant_ids, budget_bytes):
    tenants = validate_tenants(tenant_ids)
    return proportional_allocation({t: 1 for t in tenants}, budget_bytes)


def fixed_unequal_allocation(initial_weights, budget_bytes):
    """Caller freezes initial_weights before replay; no future demand input."""
    return proportional_allocation(initial_weights, budget_bytes)


def adaptive_target(smoothed_demand, budget_bytes, floor_fraction="0.20"):
    """Compute a target only; hysteresis and transfer caps are separate."""
    validate_budget(budget_bytes)
    tenants = validate_tenants(smoothed_demand.keys())
    fraction = as_weight(floor_fraction)
    if fraction > 1:
        raise ValueError("minimum-share pool exceeds the budget")

    demand = {t: as_weight(smoothed_demand[t]) for t in tenants}
    if sum(demand.values(), Fraction(0)) == 0:
        return equal_allocation(tenants, budget_bytes)

    exact_pool = budget_bytes * fraction
    floor_pool = exact_pool.numerator // exact_pool.denominator
    floors = equal_allocation(tenants, floor_pool)
    extra = proportional_allocation(demand, budget_bytes - floor_pool)
    return {t: floors[t] + extra[t] for t in tenants}
