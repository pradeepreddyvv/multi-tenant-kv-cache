"""Assess observed quota effects, traffic overlap and output consistency."""
import json
import re
import sys
from pathlib import Path


def main():
    out = Path(sys.argv[1])
    completed = json.loads((out / 'completed.json').read_text())
    state = json.loads((out / 'quota-state.json').read_text())[0]
    rows = [json.loads(s) for s in (out / 'requests.jsonl').read_text().splitlines()]
    log = out / 'run.log'
    raw = (log if log.exists() else Path(str(out) + '.log')).read_text()
    lookups = {}
    retrieves = {}
    for rid, hits in re.findall(
            r'Reqid: (\S+), Total tokens \d+, Inference Engine computed tokens: 0, LMCache hit tokens: (\d+)', raw):
        lookups.setdefault(rid.split('-')[0], set()).add(int(hits))
    for rid, tokens in re.findall(r'\[req_id=([^\]]+)\] Retrieved (\d+) out of', raw):
        retrieves.setdefault(rid.split('-')[0], []).append(int(tokens))
    lower, raise_event = state['events']
    low_samples = [s for s in state['samples'] if lower['applied_at'] <= s['time'] < raise_event['applied_at']]
    zero_samples = [s for s in low_samples if s['bytes'].get('A', 0) == 0]
    low_rows = [r for r in rows if r['tenant'] == 'A' and
                r['batch_started_at'] > lower['applied_at'] + 0.2 and
                r['batch_finished_at'] < raise_event['applied_at']]
    texts = {}
    for row in rows:
        texts.setdefault((row['tenant'], row['variant']), set()).add(row['text'])
    before = completed['before'][0][0]['tenants']
    after = completed['after'][0][0]['tenants']
    peer_stable = all(all(s['bytes'].get(t, 0) == before[t]['tensor_bytes'] for t in ['B', 'C', 'D'])
                      for s in state['samples'])
    overlaps = [any(r['batch_started_at'] <= event['applied_at'] <= r['batch_finished_at']
                    for r in rows) for event in state['events']]
    result = {'requests': len(rows), 'event_overlap_with_inference_batch': overlaps,
        'before_bytes': {t: x['tensor_bytes'] for t, x in before.items()},
        'after_bytes': {t: x['tensor_bytes'] for t, x in after.items()},
        'seconds_to_first_zero_after_lower': zero_samples[0]['time'] - lower['applied_at'] if zero_samples else None,
        'zero_occupancy_samples_while_lowered': len(zero_samples),
        'low_quota_A_requests': len(low_rows),
        'low_quota_A_lookup_misses': sum(lookups.get(r['request_id']) == {0} for r in low_rows),
        'peer_occupancy_stable': peer_stable,
        'actual_768_token_retrieves': sum(values == [768] for values in retrieves.values()),
        'output_consistency_by_input': all(len(values) == 1 for values in texts.values()),
        'evicted_chunks': state['evicted_chunks'], 'thread_errors': state['errors'],
        'note': 'Custom soft-quota prototype on primary L1; offline inference batches, no HTTP/streaming TTFT or 128 GiB combined test.'}
    result['feasibility_pass'] = (len(rows) > 8 and not state['errors'] and all(overlaps)
        and bool(zero_samples) and peer_stable and len(low_rows) > 0
        and result['low_quota_A_lookup_misses'] == len(low_rows)
        and result['actual_768_token_retrieves'] > 0
        and after['A']['tensor_bytes'] == 3 * before['A']['tensor_bytes']
        and all(t == 'A' for t in state['evicted_chunks'])
        and result['output_consistency_by_input'])
    (out / 'analysis.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
