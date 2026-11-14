import json, os, sys, time
from pathlib import Path

row = {'timestamp': time.time(), 'host': os.uname().nodename, 'cpu_affinity': sorted(os.sched_getaffinity(0))}
for line in Path('/proc/self/cgroup').read_text().splitlines():
    _, kinds, group = line.split(':', 2)
    if 'memory' in kinds.split(','):
        p = Path('/sys/fs/cgroup/memory') / group.lstrip('/')
        row['cgroup'] = str(p)
        row['memory'] = {}
        for candidate in [p, *p.parents]:
            if candidate.name.startswith('job_'):
                for name in ['memory.limit_in_bytes','memory.usage_in_bytes','memory.max_usage_in_bytes','memory.failcnt','memory.stat']:
                    f = candidate / name
                    if f.exists(): row['memory'][name] = f.read_text().strip()
                break
print(json.dumps(row), flush=True)
