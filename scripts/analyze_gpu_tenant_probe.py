"""Join saved requests with LMCache's lookup and retrieval logs."""
import json
import re
import sys
from pathlib import Path


def main():
    out = Path(sys.argv[1])
    log = out / 'run.log'
    raw = (log if log.exists() else Path(str(out) + '.log')).read_text()
    rows = [json.loads(line) for line in (out / 'requests.jsonl').read_text().splitlines()]
    completed = json.loads((out / 'completed.json').read_text())
    lookups = {}
    retrieved = {}
    for request, hits in re.findall(
            r'Reqid: (\S+), Total tokens \d+, Inference Engine computed tokens: 0, LMCache hit tokens: (\d+)', raw):
        lookups.setdefault(request.split('-')[0], set()).add(int(hits))
    for request, tokens in re.findall(r'\[req_id=([^\]]+)\] Retrieved (\d+) out of', raw):
        retrieved.setdefault(request.split('-')[0], []).append(int(tokens))
    for row in rows:
        row['lookup_hits'] = sorted(lookups.get(row['request_id'], set()))
        row['retrieved_tokens'] = retrieved.get(row['request_id'], [])
    groups = []
    for mode in ['cache_salt', 'lmcache_tag']:
        for repetition in range(2):
            selected = [r for r in rows if r['mode'] == mode and r['repetition'] == repetition]
            groups.append({'mode': mode, 'repetition': repetition, 'requests': len(selected),
                'lookup_misses': sum(r['lookup_hits'] == [0] for r in selected),
                'lookup_hits_768': sum(r['lookup_hits'] == [768] for r in selected),
                'actual_retrieves_768': sum(r['retrieved_tokens'] == [768] for r in selected),
                'total_seconds': sum(r['seconds'] for r in selected)})
    tagged_first = [r for r in rows if r['mode'] == 'lmcache_tag' and r['repetition'] == 0]
    tagged_repeat = [r for r in rows if r['mode'] == 'lmcache_tag' and r['repetition'] == 1]
    salted_first = [r for r in rows if r['mode'] == 'cache_salt' and r['repetition'] == 0]
    result = {
        'completed': completed, 'groups': groups,
        'tagged_isolation_and_reuse_pass': (
            len(tagged_first) == len(tagged_repeat) == 16
            and all(r['lookup_hits'] == [0] and not r['retrieved_tokens'] for r in tagged_first)
            and all(r['lookup_hits'] == [768] and r['retrieved_tokens'] == [768] for r in tagged_repeat)),
        'cache_salt_alone_separates_external_cache': (
            len(salted_first) == 16 and all(r['lookup_hits'] == [0] for r in salted_first)),
        'requests': rows,
    }
    (out / 'analysis.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'requests'}, indent=2))


if __name__ == '__main__':
    main()
