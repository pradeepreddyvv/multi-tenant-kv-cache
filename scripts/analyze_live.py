"""Summarize saved live pilot records; missing evidence fails validity."""
import argparse
import json
from pathlib import Path
import statistics

from check_request_attribution import classify, parse_log


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def summarize(run):
    manifest=json.loads((run/'manifest.json').read_text())
    rows=read_rows(run/'requests.jsonl')
    lookups,retrieves=parse_log((run/'run.log').read_text(errors='replace'))
    problems=[]
    if manifest['status']!='completed': problems.append('run did not complete')
    if len(rows)!=len(json.loads((run/'trace.json').read_text())): problems.append('trace not fully dispatched/completed')
    ids=[r['request_id'] for r in rows]
    if len(ids)!=len(set(ids)): problems.append('duplicate request ID')
    for row in rows:
        outcome,issues=classify(row,lookups,retrieves,manifest.get('kv_bytes_per_token',56*1024))
        row['attribution']=outcome
        row['retrieved_tokens']=sum(v['retrieved'] for v in retrieves.get(row['request_id'],[]))
        if outcome=='unattributed' or issues: problems.append(row['request_id']+': '+str(issues))
        if row['status']!='ok': problems.append(row['request_id']+': request failed')
        first=row.get('first_token_at_s')
        if first is None or not row['submitted_at_s']<=first<=row['finished_at_s']:
            problems.append(row['request_id']+': invalid first-token timing')
    windows=[('before_shift',manifest['warmup_end_s'],manifest['shift_at_s']),
             ('after_shift',manifest['shift_at_s'],manifest['measured_end_s'])]
    summary={}
    for phase,start,end in windows:
        summary[phase]={}
        for tenant in [*manifest['tenants'],'ALL']:
            subset=[r for r in rows if start<=r['submitted_at_s']<end and (tenant=='ALL' or r['tenant']==tenant)]
            valid=[r for r in subset if r['status']=='ok' and r.get('first_token_at_s') is not None]
            ttft=sorted(r['first_token_at_s']-r['submitted_at_s'] for r in valid)
            completed=[r for r in rows if start<=r['finished_at_s']<end and r['status']=='ok' and (tenant=='ALL' or r['tenant']==tenant)]
            eligible=sum(r['prompt_tokens']//256*256 for r in valid)
            summary[phase][tenant]=dict(requests=len(subset),valid=len(valid),
                median_ttft_s=statistics.median(ttft) if ttft else None,
                p95_ttft_s=ttft[int(.95*(len(ttft)-1))] if len(ttft)>=100 else None,
                reuse_fraction=sum(r['retrieved_tokens'] for r in valid)/eligible if eligible else None,
                completion_throughput_rps=len(completed)/(end-start),
                offered_rps=len(subset)/(end-start),
                mean_completion_latency_s=statistics.mean(r['finished_at_s']-r['submitted_at_s'] for r in valid) if valid else None,
                max_dispatch_lag_s=max((r['submitted_at_s']-r['scheduled_at_s'] for r in subset),default=None))
    updates=read_rows(run/'quota_updates.jsonl')
    for update in updates:
        if sum(update['quotas'].values())!=manifest['budget_bytes']: problems.append('quota budget not preserved')
        if update['status'] not in ('initialized','accepted'):problems.append('quota update not accepted')
    snapshots=read_rows(run/'occupancy.jsonl')
    if not snapshots:problems.append('no independent occupancy samples')
    decisions=read_rows(run/'decisions.jsonl')
    result=dict(valid=not problems,problems=problems,requests=len(rows),
        policy=manifest['policy'],seed=manifest['seed'],trace_sha256=manifest['trace_sha256'],
        phase_tenant=summary,quota_updates=len(updates)-1,
        peak_retained_bytes=max((sum(s['retained_bytes'].values()) for s in snapshots),default=0),
        controller_cpu_s=sum(d['controller_cpu_s'] for d in decisions),
        note='Loopback streaming pilot; 5-second completion-window demand; per-phase p95 withheld below 100 requests.')
    (run/'live-analysis.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    result=summarize(a.run)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['valid'] else 2)
