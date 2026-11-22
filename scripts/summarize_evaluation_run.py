"""Summarize one planned HTTP evaluation run per tenant and phase (task C04).

Usage:
    python3 scripts/summarize_evaluation_run.py RUN_DIR [--baseline EQUAL_RUN_DIR] [--out REPORT.json]

RUN_DIR holds the records specified in docs/evaluation/EVALUATION_SPEC.md section 7:
manifest.json, requests.jsonl, observations.jsonl and quota_updates.jsonl. With
--baseline (the equal-allocation run on the same trace) it also reports the W16 harm ratio.

No such run exists yet; until then this is exercised only on synthetic fixtures.
Cache-hit attribution is checked separately by check_request_attribution.py.
Exit status 0 means the automatic validity gates passed; 2 means Needs review.
"""
import argparse
import json
import sys
from pathlib import Path

P95_MIN_SAMPLES = 100          # W18
RATE_TOLERANCE = 0.05          # spec section 8, gate 3
OBSERVATION_FIELDS = ('tenant_id', 'window_end_s', 'eligible_input_tokens', 'retained_bytes',
                      'retrieved_tokens', 'errors')
INTEGER_FIELDS = ('eligible_input_tokens', 'retained_bytes', 'retrieved_tokens', 'errors')


def percentile(values, q):
    """Linear interpolation between closest ranks (the common 'type 7' definition)."""
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def load_run(run):
    return {'manifest': json.loads((run / 'manifest.json').read_text()),
            'requests': read_jsonl(run / 'requests.jsonl'),
            'observations': read_jsonl(run / 'observations.jsonl'),
            'quota_updates': read_jsonl(run / 'quota_updates.jsonl')}


def phase_of(manifest, submitted):
    start, end = manifest['warmup_end_s'], manifest['measured_end_s']
    if not start <= submitted < end:
        return None
    boundary = manifest.get('shift_at_s')
    if boundary is None:
        boundary = (start + end) / 2.0
    return 'phase1' if submitted < boundary else 'phase2'


def latency_stats(requests):
    ok = [r for r in requests if r['status'] == 'ok' and r.get('first_token_at_s') is not None]
    ttft = [r['first_token_at_s'] - r['submitted_at_s'] for r in ok]
    completion = [r['finished_at_s'] - r['submitted_at_s'] for r in ok]
    tpot = [(r['finished_at_s'] - r['first_token_at_s']) / (r['output_tokens'] - 1)
            for r in ok if r['output_tokens'] > 1]
    return {'submitted': len(requests), 'completed': len(ok), 'failed': len(requests) - len(ok),
            'median_ttft_s': percentile(ttft, 0.5),
            'p95_ttft_s': percentile(ttft, 0.95) if len(ttft) >= P95_MIN_SAMPLES else None,
            'p95_note': None if len(ttft) >= P95_MIN_SAMPLES else
            'insufficient samples (%d < %d)' % (len(ttft), P95_MIN_SAMPLES),
            'median_completion_s': percentile(completion, 0.5),
            'median_tpot_s': percentile(tpot, 0.5)}


def observation_problems(observations):
    problems = []
    for i, row in enumerate(observations):
        missing = [f for f in OBSERVATION_FIELDS if f not in row]
        if missing:
            problems.append('observation %d missing %s' % (i, ', '.join(missing)))
            continue
        for field in INTEGER_FIELDS:
            if not isinstance(row[field], int) or isinstance(row[field], bool) or row[field] < 0:
                problems.append('observation %d: %s must be a non-negative integer' % (i, field))
    return problems


def quota_problems(updates, budget, tenants):
    """Replay accepted updates; effective quotas must never exceed the budget."""
    problems, effective = [], {}
    counts = {'accepted': 0, 'deferred': 0, 'error': 0}
    for update in sorted(updates, key=lambda u: u['applied_at_s']):
        status = update['status']
        counts[status] = counts.get(status, 0) + 1
        if status == 'error':
            problems.append('quota update %s returned error' % update['update_id'])
        if status != 'accepted':
            continue
        unknown = set(update['quotas']) - set(tenants)
        if unknown:
            problems.append('quota update %s names unknown tenants %s' % (update['update_id'], sorted(unknown)))
        effective.update(update['quotas'])
        total = sum(effective.values())
        if total > budget:
            problems.append('after update %s quotas sum %d > budget %d' % (update['update_id'], total, budget))
    return counts, problems


def summarize(data):
    manifest, requests = data['manifest'], data['requests']
    tenants = manifest['tenants']
    window = manifest['measured_end_s'] - manifest['warmup_end_s']
    measured = [dict(r, phase=phase_of(manifest, r['submitted_at_s'])) for r in requests]
    measured = [r for r in measured if r['phase']]
    per_tenant = {}
    for tenant in tenants:
        mine = [r for r in measured if r['tenant'] == tenant]
        per_tenant[tenant] = {'measured': latency_stats(mine),
                              'phase1': latency_stats([r for r in mine if r['phase'] == 'phase1']),
                              'phase2': latency_stats([r for r in mine if r['phase'] == 'phase2'])}
    problems = []
    unknown = sorted({r['tenant'] for r in requests} - set(tenants))
    if unknown:
        problems.append('requests from tenants not in manifest: %s' % unknown)
    realized = len(measured) / window
    target = manifest['target_rate_rps']
    if abs(realized - target) > RATE_TOLERANCE * target:
        problems.append('realized rate %.3f req/s outside +/-5%% of target %.3f' % (realized, target))
    problems += observation_problems(data['observations'])
    counts, quota_issues = quota_problems(data['quota_updates'], manifest['budget_bytes'], tenants)
    problems += quota_issues
    for field in ('trace_sha256', 'seed', 'policy'):
        if not manifest.get(field) and manifest.get(field) != 0:
            problems.append('manifest missing %s' % field)
    completed = sum(1 for r in measured if r['status'] == 'ok')
    return {'run_id': manifest.get('run_id'), 'policy': manifest.get('policy'), 'seed': manifest.get('seed'),
            'trace_sha256': manifest.get('trace_sha256'),
            'measured_seconds': window, 'target_rate_rps': target, 'realized_rate_rps': realized,
            'throughput_rps': completed / window,
            'failure_rate': (len(measured) - completed) / len(measured) if measured else None,
            'quota_updates': counts, 'per_tenant': per_tenant, 'problems': problems,
            'automatic_gates': 'passed' if not problems else 'Needs review',
            'note': 'Attribution (gate 1) and independent reproduction (gate 7) are checked separately.'}


def harm_ratio(policy, equal):
    """W16: max over tenants of median TTFT(policy) / median TTFT(equal), same trace."""
    if policy['trace_sha256'] != equal['trace_sha256']:
        raise ValueError('harm ratio needs the same trace (trace_sha256 differs)')
    result = {}
    for scope in ('measured', 'phase1', 'phase2'):
        ratios = {}
        for tenant, stats in policy['per_tenant'].items():
            mine = stats[scope]['median_ttft_s']
            ref = equal['per_tenant'].get(tenant, {}).get(scope, {}).get('median_ttft_s')
            if mine is not None and ref:
                ratios[tenant] = mine / ref
        worst = max(ratios, key=ratios.get) if ratios else None
        result[scope] = {'harm_ratio': ratios[worst] if worst else None, 'worst_tenant': worst,
                         'ratios': ratios}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path)
    parser.add_argument('--baseline', type=Path, help='equal-allocation run on the same trace')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = summarize(load_run(args.run))
    if args.baseline:
        report['versus_equal'] = harm_ratio(report, summarize(load_run(args.baseline)))
    text = json.dumps(report, indent=2)
    if args.out:
        if args.out.resolve().parent == args.run.resolve():
            parser.error('--out must not be inside the run directory')
        args.out.write_text(text)
    else:
        print(text)
    sys.exit(0 if report['automatic_gates'] == 'passed' else 2)


if __name__ == '__main__':
    main()
