"""Check request-to-log attribution and retained-byte accounting in a saved run (task C03).

Usage:
    python3 scripts/check_request_attribution.py RUN_DIR [RUN_DIR ...] [--out REPORT.json]

RUN_DIR is a tenant, quota or scale run directory. Its engine log is RUN_DIR/run.log
or the adjacent RUN_DIR.log. Nothing in RUN_DIR is modified.

Each request is classified as defined in docs/evaluation/METRICS.md:
  hit           a retrieval line matched by request ID with N > 0 tokens
  miss          a lookup line with 0 hit tokens and no retrieval line
  unattributed  anything else: no lookup line, lookup hit without retrieval,
                retrieval without lookup hit, or conflicting values
Missing evidence is never a hit. Exit status 0 means Valid; 2 means Needs review.
"""
import argparse
import json
import re
import sys
from pathlib import Path

CHUNK_TOKENS = 256
KV_BYTES_PER_TOKEN = 56 * 1024        # Qwen2.5-7B, BF16 (docs/evaluation/METRICS.md)
CHUNK_BYTES = CHUNK_TOKENS * KV_BYTES_PER_TOKEN
SCALE_PROBES = 4                      # gpu_scale.py: two oldest, two newest

# Deliberately looser than the historical analyzers' regex, which requires
# "computed tokens: 0" and would silently skip any other line.
LOOKUP = re.compile(r'Reqid: (\S+), Total tokens (\d+), Inference Engine computed tokens: (\d+), '
                    r'LMCache hit tokens: (\d+)')
RETRIEVE = re.compile(r'\[req_id=([^\]]+)\] Retrieved (\d+) out of (\d+) required tokens'
                      r'(?: \(from \d+ total tokens\)\. size: ([0-9.]+) gb)?')


def eligible(prompt_tokens):
    return prompt_tokens // CHUNK_TOKENS * CHUNK_TOKENS


def parse_log(raw):
    lookups, retrieves = {}, {}
    for rid, total, computed, hits in LOOKUP.findall(raw):
        lookups.setdefault(rid.split('-')[0], []).append(
            {'total_tokens': int(total), 'engine_computed': int(computed), 'hit_tokens': int(hits)})
    for rid, got, required, size in RETRIEVE.findall(raw):
        retrieves.setdefault(rid.split('-')[0], []).append(
            {'retrieved': int(got), 'required': int(required),
             'size_gb': float(size) if size else None})
    return lookups, retrieves


def classify(record, lookups, retrieves):
    """Return (outcome, problems) for one request record."""
    rid = record['request_id']
    found, got = lookups.get(rid, []), retrieves.get(rid, [])
    problems = []
    if not found:
        return 'unattributed', ['no lookup line']
    if len(found) > 1:
        problems.append('%d lookup lines' % len(found))
    look = found[0]
    if look['total_tokens'] != record['prompt_tokens']:
        problems.append('log total %d != record prompt %d' % (look['total_tokens'], record['prompt_tokens']))
    if look['engine_computed']:
        problems.append('engine computed %d tokens (native cache involved)' % look['engine_computed'])
    if len(got) > 1:
        problems.append('%d retrieval lines' % len(got))
    limit = eligible(record['prompt_tokens'])
    for r in got:
        if r['retrieved'] > limit:
            problems.append('retrieved %d > eligible %d' % (r['retrieved'], limit))
        if r['size_gb'] is not None and abs(r['retrieved'] * KV_BYTES_PER_TOKEN / 2 ** 30 - r['size_gb']) > 5e-5:
            problems.append('size %.4f gb != %d tokens x 56 KiB' % (r['size_gb'], r['retrieved']))
    if got and got[0]['retrieved'] > 0:
        if look['hit_tokens'] != got[0]['retrieved']:
            problems.append('lookup %d != retrieved %d' % (look['hit_tokens'], got[0]['retrieved']))
        outcome = 'hit'
    elif look['hit_tokens'] == 0 and not got:
        outcome = 'miss'
    else:
        return 'unattributed', problems + ['lookup %d tokens without matching retrieval' % look['hit_tokens']]
    return ('unattributed' if problems else outcome), problems


def failed(record):
    return not record.get('text') or not record.get('output_tokens')


def snapshot_problems(label, tenants):
    """Retained bytes must be whole 14 MiB chunks and match the chunk count."""
    out = []
    for tenant, row in tenants.items():
        if row['tensor_bytes'] != row['chunks'] * CHUNK_BYTES:
            out.append('%s %s: %d bytes != %d chunks x 14 MiB'
                       % (label, tenant, row['tensor_bytes'], row['chunks']))
    return out


def load_records(run):
    path = run / 'requests.jsonl'
    if path.exists():
        return 'requests', [json.loads(line) for line in path.read_text().splitlines()]
    completed = json.loads((run / 'completed.json').read_text())
    n = completed['requests'] + SCALE_PROBES
    tokens = completed['prompt_tokens_each']
    # The scale workload writes no per-request file; IDs follow submission order.
    return 'scale', [{'request_id': str(i), 'prompt_tokens': tokens, 'output_tokens': 1, 'text': '-',
                      'phase': 'probe' if i >= completed['requests'] else 'population'}
                     for i in range(n)]


def retained_checks(run):
    problems, checked = [], 0
    occupancy = run / 'occupancy.json'
    if occupancy.exists():
        for state in json.loads(occupancy.read_text()):
            for worker in state['workers']:
                for engine in worker:
                    checked += 1
                    problems += snapshot_problems('%s/%s' % (state['mode'], state['repetition']),
                                                  engine['tenants'])
    scale = run / 'occupancy.jsonl'
    if scale.exists():
        for line in scale.read_text().splitlines():
            state = json.loads(line)
            for worker in state['workers']:
                for engine in worker:
                    checked += 1
                    problems += snapshot_problems(state['label'], engine['tenants'])
    completed = run / 'completed.json'
    if completed.exists():
        data = json.loads(completed.read_text())
        for key in ('before', 'after'):
            for worker in data.get(key, []):
                for engine in worker:
                    checked += 1
                    problems += snapshot_problems(key, engine['tenants'])
    quota = run / 'quota-state.json'
    if quota.exists():
        for state in json.loads(quota.read_text()):
            for sample in state['samples']:
                checked += 1
                for tenant, value in sample['bytes'].items():
                    if value % CHUNK_BYTES:
                        problems.append('quota sample %s: %d bytes not whole chunks' % (tenant, value))
    return checked, problems


def check_run(run):
    log = run / 'run.log'
    raw = (log if log.exists() else Path(str(run) + '.log')).read_text()
    lookups, retrieves = parse_log(raw)
    kind, records = load_records(run)
    rows, problems = [], []
    for record in records:
        outcome, why = classify(record, lookups, retrieves)
        rows.append({'request_id': record['request_id'], 'tenant': record.get('tenant'),
                     'phase': record.get('phase', record.get('mode')), 'outcome': outcome,
                     'retrieved_tokens': sum(r['retrieved'] for r in retrieves.get(record['request_id'], [])),
                     'eligible_tokens': eligible(record['prompt_tokens']),
                     'failed': failed(record), 'problems': why})
        problems += ['request %s: %s' % (record['request_id'], p) for p in why]
    known = {r['request_id'] for r in records}
    orphans = sorted((set(lookups) | set(retrieves)) - known, key=lambda x: (len(x), x))
    problems += ['log request %s has no record' % rid for rid in orphans]
    snapshots, byte_problems = retained_checks(run)
    problems += byte_problems

    def count(selected):
        return {k: sum(r['outcome'] == k for r in selected) for k in ('hit', 'miss', 'unattributed')}

    by_tenant = {}
    for row in rows:
        if row['tenant'] is not None:
            by_tenant.setdefault(row['tenant'], []).append(row)
    return {
        'run': run.name, 'record_source': kind, 'requests': len(rows),
        'lookup_lines': sum(len(v) for v in lookups.values()),
        'retrieval_lines': sum(len(v) for v in retrieves.values()),
        'outcomes': count(rows),
        'failed_requests': sum(r['failed'] for r in rows),
        'retrieved_tokens': sum(r['retrieved_tokens'] for r in rows),
        'eligible_tokens': sum(r['eligible_tokens'] for r in rows),
        'orphan_log_ids': orphans,
        'snapshots_checked': snapshots,
        'by_tenant': {t: dict(count(v), requests=len(v)) for t, v in sorted(by_tenant.items())},
        'problems': problems,
        'metric_validity': 'Valid' if not problems else 'Needs review',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--out', type=Path, help='write the JSON report here (outside any run dir)')
    args = parser.parse_args()
    report = {'note': 'Saved-log check; no inference.', 'runs': [check_run(r) for r in args.runs]}
    text = json.dumps(report, indent=2)
    if args.out:
        if any(args.out.resolve().parent == r.resolve() for r in args.runs):
            parser.error('--out must not be inside a run directory')
        args.out.write_text(text)
    for run in report['runs']:
        print('%-26s %-12s requests=%-4d hit=%-4d miss=%-4d unattributed=%-3d failed=%-3d problems=%d'
              % (run['run'], run['metric_validity'], run['requests'], run['outcomes']['hit'],
                 run['outcomes']['miss'], run['outcomes']['unattributed'], run['failed_requests'],
                 len(run['problems'])))
    sys.exit(0 if all(r['metric_validity'] == 'Valid' for r in report['runs']) else 2)


if __name__ == '__main__':
    main()
