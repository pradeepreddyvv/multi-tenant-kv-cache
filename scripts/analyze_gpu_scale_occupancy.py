"""Summarize actual retained bytes and independent job-memory evidence."""
import json
import re
import sys
from pathlib import Path


def main():
    out = Path(sys.argv[1])
    root = out.parent
    job = out.name[len('gpu-scale-'):] if out.name.startswith('gpu-scale-') else out.name
    completed = json.loads((out / 'completed.json').read_text())
    snapshots = [json.loads(line) for line in (out / 'occupancy.jsonl').read_text().splitlines()]
    measured = []
    for snapshot in snapshots:
        entries = [entry for worker in snapshot['workers'] for engine in worker
                   for entry in engine['tenants'].values()]
        measured.append({'label': snapshot['label'],
            'elapsed_seconds': snapshot['elapsed_seconds'],
            'chunks': sum(e['chunks'] for e in entries),
            'tensor_bytes': sum(e['tensor_bytes'] for e in entries),
            'physical_bytes': sum(e['physical_bytes'] for e in entries)})
    memory_path = out / 'memory.jsonl'
    log_path = out / 'run.log'
    if not memory_path.exists():
        memory_path = root / f'gpu-scale-{job}-memory.jsonl'
    if not log_path.exists():
        log_path = root / f'gpu-scale-{job}.log'
    memory = [json.loads(line)['memory'] for line in memory_path.read_text().splitlines()]
    raw = log_path.read_text()
    lookups = {}
    for rid, hits in re.findall(
            r'Reqid: (\S+), Total tokens \d+, Inference Engine computed tokens: 0, LMCache hit tokens: (\d+)', raw):
        lookups.setdefault(rid.split('-')[0], set()).add(int(hits))
    retrieves = {}
    for rid, tokens in re.findall(r'\[req_id=([^\]]+)\] Retrieved (\d+) out of', raw):
        retrieves.setdefault(rid.split('-')[0], []).append(int(tokens))
    result = {'job': job, 'completed': completed, 'occupancy': measured,
        'peak_retained_GiB': max(r['tensor_bytes'] for r in measured) / 2**30,
        'max_sampled_cgroup_highwater_GiB': max(int(m['memory.max_usage_in_bytes']) for m in memory) / 2**30,
        'job_limit_GiB': sorted({int(m['memory.limit_in_bytes']) / 2**30 for m in memory}),
        'max_memory_failcnt': max(int(m['memory.failcnt']) for m in memory),
        'oldest_probe_hits': [sorted(lookups.get(str(i), set())) for i in [600, 601]],
        'newest_probe_retrieves': [retrieves.get(str(i), []) for i in [602, 603]],
        'cache_full_warning_count': len(re.findall(r'Failed to allocate memory block of size \d+ because no memory is available', raw)),
        'note': 'Retained bytes are under-lock sums of live cache objects; cgroup memory includes overhead. No tenant quotas tested.'}
    (out / 'occupancy-analysis.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
