"""Compare paired, fully validated live runs without pooling unlike experiments."""
import argparse
import json
from pathlib import Path
import statistics
from analyze_live import summarize

MATCH_FIELDS = ('tenants', 'prefix_tokens', 'scenario', 'working_set_bytes', 'model', 'revision', 'budget_bytes', 'warmup_end_s', 'measured_end_s',
                'shift_at_s', 'target_rate', 'trace_sha256', 'max_model_len',
                'max_num_seqs', 'gpu_memory_utilization', 'source_sha256',
                'prefix_pool_per_tenant', 'kv_bytes_per_token', 'physical_cache_capacity_gib')


def compare(runs):
    groups = {}
    for run in runs:
        manifest = json.loads((run / 'manifest.json').read_text())
        result = summarize(run)
        if not result['valid']:
            raise ValueError(str(run) + ': invalid evidence')
        group = groups.setdefault(manifest['seed'], {})
        if manifest['policy'] in group:
            raise ValueError('Duplicate policy for a seed')
        group[manifest['policy']] = (manifest, result, str(run))
    pairs = []
    for seed, group in sorted(groups.items()):
        if set(group) != {'equal', 'fixed', 'adaptive'}:
            raise ValueError('Each seed requires equal, fixed and adaptive runs')
        reference = group['equal'][0]
        for policy, (manifest, _, _) in group.items():
            changed = [field for field in MATCH_FIELDS if manifest.get(field) != reference.get(field)]
            if changed:
                raise ValueError('%s seed %s mismatch: %s' % (policy, seed, changed))
        for phase in ('before_shift', 'after_shift'):
            for baseline in ('equal', 'fixed'):
                adaptive = group['adaptive'][1]['phase_tenant'][phase]['ALL']
                control = group[baseline][1]['phase_tenant'][phase]['ALL']
                if not adaptive['valid'] or not control['valid']:
                    raise ValueError('No valid requests in a comparison window')
                pairs.append(dict(seed=seed, phase=phase, baseline=baseline,
                    median_ttft_change_fraction=adaptive['median_ttft_s']/control['median_ttft_s']-1,
                    reuse_change_points=100*(adaptive['reuse_fraction']-control['reuse_fraction']),
                    adaptive=adaptive, control=control))
    aggregates = []
    for phase in ('before_shift', 'after_shift'):
        for baseline in ('equal', 'fixed'):
            selected = [p for p in pairs if p['phase']==phase and p['baseline']==baseline]
            if selected:
                values=[p['median_ttft_change_fraction'] for p in selected]
                aggregates.append(dict(phase=phase, baseline=baseline, paired_seeds=len(values),
                    median_paired_ttft_change_fraction=statistics.median(values),
                    min_paired_ttft_change_fraction=min(values), max_paired_ttft_change_fraction=max(values)))
    return dict(pairs=pairs, aggregate=aggregates,
        interpretation='Negative TTFT change favors adaptive. Ranges show seed variability, not confidence intervals. '
        'Aggregate benefits can hide tenant regressions; inspect per-tenant analyses. Synthetic loopback workload only.')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('runs',nargs='+',type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();a.out.write_text(json.dumps(compare(a.runs),indent=2))
