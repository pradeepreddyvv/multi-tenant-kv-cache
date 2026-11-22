"""Loopback streaming HTTP pilot with real LMCache quota worker RPCs.

This research harness implements only its documented completions request shape;
it is not the full vLLM OpenAI server. All policies use the identical harness.
"""
import argparse
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import time

from policy.candidates import Candidate
from live_common import tenant_ids, build_trace, trace_hash, window_observations
from policy.allocation import equal_allocation, fixed_unequal_allocation
from policy.controller import initial_state, policy
from runtime import MODEL, REVISION


def append(path, value):
    with path.open('a') as stream:
        stream.write(json.dumps(value) + '\n')


async def main(args):
    # Heavy imports occur only inside an allocated GPU container.
    import aiohttp
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    import uvicorn
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.v1.engine.async_llm import AsyncLLM
    from vllm import SamplingParams
    from vllm.sampling_params import RequestOutputKind
    from vllm.config import KVTransferConfig

    out = Path(os.environ['DIS_ML_RESULT_DIR'])
    budget = int(args.budget_gib * 2**30)
    from transformers import AutoConfig
    config = AutoConfig.from_pretrained(args.model, revision=args.revision, local_files_only=True)
    head_dim = getattr(config, 'head_dim', None) or config.hidden_size // config.num_attention_heads
    kv_bytes_per_token = 2 * config.num_hidden_layers * config.num_key_value_heads * head_dim * 2
    capacity = float(os.environ['LMCACHE_MAX_LOCAL_CPU_SIZE'])
    if abs(capacity - args.budget_gib) > 1e-6:
        raise ValueError('Physical cache capacity must match the policy budget')
    tenants = tenant_ids(args.tenant_count)
    trace = build_trace(args.seed, args.duration, args.rate, args.shift, pool=args.prefix_pool, scenario=args.scenario, tenants=tenants, prefix_tokens=args.prefix_tokens)
    (out / 'trace.json').write_text(json.dumps(trace))
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
               for folder in ('scripts', 'policy') for p in sorted(Path(folder).glob('*.py'))}
    manifest = dict(policy=args.policy, seed=args.seed, budget_bytes=budget, tenants=list(tenants),
        warmup_end_s=args.warmup, measured_end_s=args.duration, shift_at_s=args.shift,
        scenario=args.scenario, target_rate=args.rate, trace_sha256=trace_hash(trace), model=args.model, revision=args.revision,
        source_sha256=sources, job=os.environ.get('SLURM_JOB_ID'), host=socket.gethostname(),
        python=platform.python_version(), native_prefix_caching=False,
        max_model_len=args.prefix_tokens + 256, max_num_seqs=args.max_num_seqs, gpu_memory_utilization=args.gpu_utilization,
        workload=f'synthetic token-ID prefixes; {args.prefix_tokens}+64 tokens; 32 output tokens', prefix_tokens=args.prefix_tokens,
        prefix_pool_per_tenant=args.prefix_pool, kv_bytes_per_token=kv_bytes_per_token,
        physical_cache_capacity_gib=capacity, working_set_bytes=len(tenants)*args.prefix_pool*args.prefix_tokens*kv_bytes_per_token,
        observation_semantics='completed requests in each 5-second window; rejected on missing attribution',
        transport='custom loopback HTTP SSE wrapper around AsyncLLM; client and frontend share event loop',
        claim_scope='pilot; not production OpenAI-server benchmark; no saturation calibration unless recorded separately',
        status='starting')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    engine = AsyncLLM.from_engine_args(AsyncEngineArgs(
        model=args.model, revision=args.revision, tokenizer_revision=args.revision, dtype='bfloat16',
        max_model_len=args.prefix_tokens + 256, max_num_seqs=args.max_num_seqs, gpu_memory_utilization=args.gpu_utilization,
        enforce_eager=True, enable_prefix_caching=False,
        worker_extension_cls='tenant_quota.TenantQuotaExtension',
        kv_transfer_config=KVTransferConfig(kv_connector='LMCacheConnectorV1', kv_role='kv_both')))
    app = FastAPI()

    @app.post('/v1/completions')
    async def completions(request: Request):
        payload = await request.json()
        rid, tenant = payload['request_id'], payload['tenant']
        params = SamplingParams(temperature=0, max_tokens=32, ignore_eos=True,
            output_kind=RequestOutputKind.CUMULATIVE,
            extra_args={'kv_transfer_params': {'lmcache.tag.tenant': tenant}})

        async def stream():
            previous = 0
            async for result in engine.generate({'prompt_token_ids': payload['prompt']}, params, rid):
                generated = result.outputs[0]
                count = len(generated.token_ids)
                if count > previous:
                    event = dict(request_id=rid, engine_request_id=result.request_id,
                        output_tokens=count, text=generated.text,
                        prompt_tokens=len(payload['prompt']), finished=result.finished)
                    yield 'data: ' + json.dumps(event) + '\n\n'
                    previous = count
            yield 'data: [DONE]\n\n'
        return StreamingResponse(stream(), media_type='text/event-stream')

    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    for _ in range(300):
        if server.started:
            break
        if serving.done():
            await serving
            raise RuntimeError('HTTP server exited during startup')
        await asyncio.sleep(.1)
    else:
        raise RuntimeError('HTTP server startup timeout')

    state = initial_state(tenants, budget)
    candidate_controller = Candidate(args.policy,tenants,budget,args.prefix_tokens*kv_bytes_per_token) if args.policy in ('slow','reuse','v3') else None
    quotas = (fixed_unequal_allocation({t: 3 if t == tenants[0] else 1 for t in tenants}, budget)
              if args.policy == 'fixed' else equal_allocation(tenants, budget))
    origin = time.monotonic()
    rows, tasks = [], []
    stopped = asyncio.Event()
    fatal = []

    async def rpc(name, values=()):
        replies = await engine.collective_rpc(name, timeout=20, args=values)
        if len(replies) != 1:
            raise RuntimeError('Only one GPU worker is supported')
        return replies[0]

    await rpc('dis_ml_quota_start', ({'limits': quotas, 'budget_bytes': budget,
                                    'interval_s': .1, 'history_size': 100, 'enforce': args.policy != 'shared'},))
    origin = time.monotonic()
    manifest['status'] = 'running'
    manifest['started_epoch_s'] = time.time()
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    append(out / 'quota_updates.jsonl', dict(at_s=0, quotas=quotas, status='initialized'))

    async def sampling():
        nonlocal state, quotas
        last_window = 0.0
        next_window = 5.0
        while not stopped.is_set():
            try:
                began = time.monotonic() - origin
                # A fresh locked read, independent of the enforcer's stored history.
                cache = await rpc('dis_ml_cpu_cache_snapshot')
                if len(cache) != 1:
                    raise RuntimeError('Expected one CPU cache backend')
                retained = {t: v['tensor_bytes'] for t, v in cache[0]['tenants'].items()}
                adapter = await rpc('dis_ml_quota_snapshot')
                if adapter['error'] or not adapter['running']:
                    raise RuntimeError('quota adapter stopped or failed: '+str(adapter['error']))
                now = time.monotonic() - origin
                append(out / 'occupancy.jsonl', dict(sample_started_s=began, observed_at_s=now,
                    retained_bytes=retained, quotas=quotas, update_id=adapter['update_id'],
                    post_enforcement_latest=adapter['latest']))
                if now >= next_window:
                    if now - last_window > 10:
                        raise RuntimeError('telemetry gap exceeded 10 seconds; terminate episode')
                    selected = [r for r in rows if last_window < r['finished_at_s'] <= now]
                    observations = window_observations(selected, (out/'run.log').read_text(errors='replace'), retained, now, kv_bytes_per_token, tenants=tenants)
                    for observation in observations:
                        append(out/'observations.jsonl', observation)
                    if any(r['errors'] for r in observations):
                        raise RuntimeError('invalid request/log telemetry in observation window')
                    cpu_start = time.process_time()
                    target, candidate = policy(observations, budget, state)
                    cpu_s = time.process_time() - cpu_start
                    if candidate_controller:
                        target = candidate_controller.decide(now) or quotas
                    if (args.policy == 'adaptive' or candidate_controller) and target != quotas:
                        acknowledgement = await rpc('dis_ml_quota_update', (target,))
                        append(out/'quota_updates.jsonl', dict(at_s=time.monotonic()-origin,
                            quotas=target, acknowledgement=acknowledgement, status=acknowledgement['status']))
                        if acknowledgement['status'] != 'accepted':
                            raise RuntimeError('quota target rejected; episode terminated')
                        quotas = target
                    if args.policy == 'adaptive':
                        state = candidate
                    append(out/'decisions.jsonl', dict(window_end_s=now, selected_policy=args.policy,
                        hypothetical_adaptive_reason=candidate['reason'], quotas=quotas,
                        controller_cpu_s=cpu_s))
                    last_window, next_window = now, now+5
                await asyncio.sleep(.5)
            except Exception as exc:
                fatal.append(repr(exc))
                stopped.set()
                return

    async def request_one(client, request):
        if candidate_controller:
            candidate_controller.arrival(request['tenant'], request['variant'])
        row = {k:v for k,v in request.items() if k != 'prompt'}
        row.update(submitted_at_s=time.monotonic()-origin, first_token_at_s=None,
                   prompt_tokens=len(request['prompt']), output_tokens=0, text='', status='error')
        try:
            async with client.post('http://127.0.0.1:%d/v1/completions'%port, json=request) as response:
                response.raise_for_status()
                async for line in response.content:
                    line = line.decode().strip()
                    if not line.startswith('data: ') or line == 'data: [DONE]':
                        continue
                    event = json.loads(line[6:])
                    if event['output_tokens'] and row['first_token_at_s'] is None:
                        row['first_token_at_s'] = time.monotonic()-origin
                    row.update(output_tokens=event['output_tokens'], text=event['text'],
                               engine_request_id=event['engine_request_id'])
            if row['output_tokens'] == 32 and row['first_token_at_s'] is not None:
                row['status'] = 'ok'
        except Exception as exc:
            row['error'] = repr(exc)
        row['finished_at_s'] = time.monotonic()-origin
        rows.append(row)
        append(out/'requests.jsonl', row)

    sampler = asyncio.create_task(sampling())
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        # Each request uses its own connection, avoiding reuse of an idle socket
        # that the HTTP server has concurrently closed. Identical for all policies.
        async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(limit=0, force_close=True)) as client:
            for request in trace:
                await asyncio.sleep(max(0, origin+request['scheduled_at_s']-time.monotonic()))
                if stopped.is_set():
                    break
                if sum(not t.done() for t in tasks) >= 256:
                    fatal.append('more than 256 outstanding requests; overload abort')
                    break
                tasks.append(asyncio.create_task(request_one(client, request)))
            await asyncio.gather(*tasks)
            if not fatal:
                await asyncio.sleep(max(0, origin+args.duration-time.monotonic()))
    finally:
        stopped.set()
        await sampler
        final = await rpc('dis_ml_quota_stop')
        (out/'quota-final.json').write_text(json.dumps(final))
        server.should_exit = True
        await serving
        engine.shutdown()
    manifest.update(status='failed' if fatal else 'completed', errors=fatal,
                    requests_finished=len(rows), request_errors=sum(r['status']!='ok' for r in rows))
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    if fatal or manifest['request_errors']:
        raise RuntimeError('live run failed: '+repr(manifest))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--policy', choices=['equal', 'fixed', 'adaptive', 'slow', 'reuse', 'v3', 'shared'], required=True)
    parser.add_argument('--scenario', choices=['shift','scan','burst'], default='shift')
    parser.add_argument('--tenant-count', type=int, choices=[4, 8, 16], default=4)
    parser.add_argument('--prefix-tokens', type=int, default=4096)
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--duration', type=float, default=180)
    parser.add_argument('--warmup', type=float, default=30)
    parser.add_argument('--shift', type=float, default=105)
    parser.add_argument('--rate', type=float, default=2)
    parser.add_argument('--budget-gib', type=float, default=1.75)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--revision', default=REVISION)
    parser.add_argument('--prefix-pool', type=int, default=4)
    parser.add_argument('--max-num-seqs', type=int, default=32)
    parser.add_argument('--gpu-utilization', type=float, default=.85)
    args = parser.parse_args()
    if args.prefix_tokens < 256 or args.prefix_tokens % 256:
        parser.error("prefix tokens must be a positive multiple of the 256-token cache chunk")
    if args.prefix_pool < 1 or args.max_num_seqs < 1 or not 0 < args.gpu_utilization < 1:
        parser.error('invalid workload or GPU configuration')
    if not 0 <= args.warmup < args.shift < args.duration or args.rate <= 0 or args.budget_gib <= 0:
        parser.error('invalid timing, rate or budget')
    asyncio.run(main(args))
