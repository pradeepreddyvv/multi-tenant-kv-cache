"""Deterministic traces and log attribution for the live integration pilot."""
import hashlib
import json
import random

from check_request_attribution import classify, parse_log

TENANTS = ('A', 'B', 'C', 'D')
MODEL_REVISION = 'a09a35458c702b33eeacc393d103063234e8bc28'


def tenant_ids(count):
    """Stable identities keep the original four-tenant trace reproducible."""
    if count not in (4, 8, 16):
        raise ValueError("tenant count must be 4, 8 or 16")
    return tuple(chr(ord('A') + i) for i in range(count))


def build_trace(seed, duration, rate, shift, prefix_tokens=4096, pool=4, scenario="shift", tenants=TENANTS):
    if len(set(tenants)) != len(tenants) or len(tenants) < 2:
        raise ValueError("at least two unique tenants are required")
    rng = random.Random(seed)
    prefixes = {t: [[rng.randrange(100, 20000) for _ in range(prefix_tokens)]
                    for _ in range(pool)] for t in tenants}
    rows, at = [], 0.0
    while True:
        at += rng.expovariate(rate)
        if at >= duration * (1.1 if scenario == "burst" else 1):
            break
        scheduled = at
        if scenario == 'burst':
            # Post-warmup burst: compress 60-80% of base time to twice the rate.
            lo, hi = duration * .6, duration * .8
            scheduled = at if at < lo else (lo + (at-lo)/2 if at < hi else at-(hi-lo)/2)
        hot = (tenants[-1] if scenario == 'scan' else (tenants[0] if scheduled < shift else tenants[1]))
        weights = [3 if t == hot else 1 for t in tenants]
        tenant = rng.choices(tenants, weights=weights)[0]
        variant = rng.randrange(pool)
        if scenario == 'scan' and tenant == tenants[-1]:
            variant = pool + len(rows)
            prefix = [rng.randrange(100,20000) for _ in range(prefix_tokens)]
        else:
            prefix = prefixes[tenant][variant]
        rows.append({'request_id': 'r%06d' % len(rows), 'scheduled_at_s': scheduled,
                     'tenant': tenant, 'variant': variant,
                     'prompt': prefix +
                               [rng.randrange(100, 20000) for _ in range(64)]})
    return rows


def trace_hash(rows):
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def window_observations(records, log_text, retained, end_s, kv_bytes_per_token=56*1024, tenants=TENANTS):
    """Completion-window counters; incomplete log attribution rejects the window."""
    lookups, retrieves = parse_log(log_text)
    stats = {t: dict(tenant_id=t, window_end_s=end_s, eligible_input_tokens=0,
                     retained_bytes=int(retained.get(t, 0)), retrieved_tokens=0,
                     errors=0) for t in tenants}
    for row in records:
        s = stats[row['tenant']]
        if row['status'] != 'ok':
            s['errors'] += 1
            continue
        outcome, problems = classify(row, lookups, retrieves, kv_bytes_per_token)
        if outcome == 'unattributed' or problems:
            s['errors'] += 1
            continue
        s['eligible_input_tokens'] += row['prompt_tokens'] // 256 * 256
        s['retrieved_tokens'] += sum(x['retrieved'] for x in retrieves.get(row['request_id'], []))
    return list(stats.values())
