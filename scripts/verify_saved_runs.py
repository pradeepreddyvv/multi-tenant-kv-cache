"""Regression-check analyzers against private saved evidence, without inference.

Usage: python3 scripts/verify_saved_runs.py /path/to/original/results
Only temporary copies are modified. Raw evidence is not copied into this repo.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence_root', type=Path)
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    cases = [
        ('gpu-tenants-run3', 'analyze_gpu_tenant_probe.py', 'analysis.json',
         'tagged_isolation_and_reuse_pass'),
        ('gpu-primary-quota-run1', 'analyze_primary_quota_probe.py', 'analysis.json',
         'feasibility_pass'),
        ('gpu-scale-976316', 'analyze_gpu_scale_occupancy.py', 'occupancy-analysis.json', None),
    ]
    checks = []
    with tempfile.TemporaryDirectory(prefix='kv-cache-replay-') as temporary:
        for run, analyzer, filename, pass_key in cases:
            original = args.evidence_root / run
            out = Path(temporary) / run
            shutil.copytree(str(original), str(out))
            shutil.copy2(str(args.evidence_root / (run + '.log')), str(out / 'run.log'))
            if run.startswith('gpu-scale-'):
                shutil.copy2(str(args.evidence_root / (run + '-memory.jsonl')),
                             str(out / 'memory.jsonl'))
            command = [sys.executable, str(scripts / analyzer), str(out)]
            subprocess.check_output(command)
            expected = json.loads((original / filename).read_text())
            actual = json.loads((out / filename).read_text())
            if actual != expected:
                raise RuntimeError('Saved analysis differs for ' + run)
            check = {'run': run, 'analysis_matches_original': True}
            if pass_key:
                # A success summary must depend on the actual retrieval logs.
                (out / 'run.log').write_text('')
                subprocess.check_output(command)
                negative = json.loads((out / filename).read_text())
                if negative[pass_key]:
                    raise RuntimeError('Missing logs incorrectly passed for ' + run)
                check['empty_log_cannot_pass'] = True
            checks.append(check)
    print(json.dumps({'checks': checks, 'live_inference': False}, indent=2))


if __name__ == '__main__':
    main()
