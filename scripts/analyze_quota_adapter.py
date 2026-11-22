"""Validate retained bytes and actual request-matched retrieval evidence."""
import json
import re
import sys
from pathlib import Path


def analyze(out):
    data = json.loads((out / 'completed.json').read_text())
    rows = [json.loads(s) for s in (out / 'requests.jsonl').read_text().splitlines()]
    log = (out / 'run.log').read_text()
    hits, retrieved = {}, {}
    for request, count in re.findall(r'Reqid: (\S+), Total tokens \d+, Inference Engine computed tokens: 0, LMCache hit tokens: (\d+)', log):
        hits.setdefault(request.split('-')[0], set()).add(int(count))
    for request, count in re.findall(r'\[req_id=([^\]]+)\] Retrieved (\d+) out of', log):
        retrieved.setdefault(request.split('-')[0], []).append(int(count))
    obs = data['observations']
    zero = [r for r in rows if r['phase'] == 'zero_quota' and r['tenant'] == 'A']
    peers = [r for r in rows if r['phase'] == 'zero_quota' and r['tenant'] != 'A']
    unit = data['unit_bytes']
    checks = {
        'invalid_update_rejected_atomically': data['rejected_update']['status'] == 'error' and obs['after_rejected_update']['update_id'] == 0 and obs['after_rejected_update']['quota_bytes'] == obs['initial']['quota_bytes'],
        'runs_beyond_30_seconds': data['duration_s'] >= 35 and obs['after_35_seconds']['running'],
        'lowered_to_zero': obs['lowered']['latest']['retained_bytes']['A'] == 0,
        'zero_quota_requests_miss': len(zero) == 5 and all(hits.get(r['request_id']) == {0} and not retrieved.get(r['request_id']) for r in zero),
        'peers_retrieve_during_zero_quota': len(peers) == 15 and all(retrieved.get(r['request_id']) == [768] for r in peers),
        'grows_to_three_prefixes': obs['grown']['latest']['retained_bytes']['A'] == 3 * unit,
        'peer_bytes_preserved': all(s['latest']['retained_bytes'].get(t) == unit for s in obs.values() for t in ['B', 'C', 'D']),
        'no_adapter_errors': all(s['error'] is None for s in obs.values()) and data['stopped']['error'] is None and data['restart_state']['error'] is None,
        'stops_and_restarts': data['stopped']['closed'] and not data['stopped']['running'] and data['restarted']['status'] == 'started' and data['restart_state']['latest'] is not None and data['restart_state']['closed'],
        'quota_updates_acknowledged': [x['update_id'] for x in data['acknowledgements']] == [1, 2],
    }
    return {'checks': checks, 'pass': all(checks.values()), 'requests': len(rows),
            'duration_s': data['duration_s'], 'unit_bytes': unit,
            'note': 'Pinned-version soft retention adapter; synthetic offline batches, no adaptive-policy or latency-benefit claim.'}

if __name__ == '__main__':
    out = Path(sys.argv[1])
    result = analyze(out)
    (out / 'analysis.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['pass'] else 1)
