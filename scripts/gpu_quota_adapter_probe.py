"""Sustained quota adapter smoke test with real GPU inference and CPU KV."""
import json
import os
import time
from pathlib import Path

from runtime import MODEL, REVISION, output_directory

from vllm import LLM, SamplingParams
from vllm.config import KVTransferConfig


def main():
    out = output_directory()
    llm = LLM(model=MODEL, revision=REVISION, tokenizer_revision=REVISION, dtype='bfloat16',
        max_model_len=2048, max_num_seqs=4, gpu_memory_utilization=0.85,
        enforce_eager=True, enable_prefix_caching=False,
        worker_extension_cls='tenant_quota.TenantQuotaExtension',
        kv_transfer_config=KVTransferConfig(kv_connector='LMCacheConnectorV1', kv_role='kv_both'))
    tenants = ['A', 'B', 'C', 'D']
    rows = []

    def batch(phase, variant=0):
        prompts = []
        params = []
        for tenant in tenants:
            prefix = variant if tenant == 'A' else 0
            prompts.append({'prompt': f'Document {prefix}. ' +
                'This document describes memory caching and reusable information. ' * 100 +
                'Summarize the document.', 'cache_salt': tenant})
            params.append(SamplingParams(temperature=0, max_tokens=8,
                extra_args={'kv_transfer_params': {'lmcache.tag.tenant': tenant}}))
        begin = time.time()
        results = llm.generate(prompts, params, use_tqdm=False)
        end = time.time()
        for tenant, result in zip(tenants, results, strict=True):
            row = {'phase': phase, 'tenant': tenant, 'variant': variant if tenant == 'A' else 0,
                   'request_id': result.request_id, 'batch_started_at': begin,
                   'batch_finished_at': end, 'prompt_tokens': len(result.prompt_token_ids),
                   'output_tokens': len(result.outputs[0].token_ids),
                   'text': result.outputs[0].text}
            rows.append(row)
            with (out / 'requests.jsonl').open('a') as stream:
                stream.write(json.dumps(row) + '\n')
        print('QUOTA_BATCH ' + json.dumps({'phase': phase, 'variant': variant,
                                          'started': begin, 'finished': end}), flush=True)

    batch('populate')
    batch('warm')
    before = llm.collective_rpc('dis_ml_cpu_cache_snapshot', timeout=30)
    # Actual per-tenant occupied bytes, rather than an assumed model KV size.
    measured = before[0][0]['tenants']
    unit = measured['A']['tensor_bytes']
    limits = {t: measured[t]['tensor_bytes'] for t in tenants}
    config = {'limits': limits, 'budget_bytes': 2 * 1024**3, 'interval_s': 0.1}
    observations = {}
    acknowledgements = []
    started = time.monotonic()
    llm.collective_rpc('dis_ml_quota_start', timeout=30, args=(config,))

    def observe(name):
        time.sleep(0.3)
        observations[name] = llm.collective_rpc('dis_ml_quota_snapshot', timeout=30)[0]

    try:
        observe('initial')
        rejected = llm.collective_rpc('dis_ml_quota_update', timeout=30, args=(dict(limits, A=-1),))[0]
        observe('after_rejected_update')
        low = dict(limits, A=0)
        acknowledgements.append(llm.collective_rpc('dis_ml_quota_update', timeout=30, args=(low,))[0])
        observe('lowered')
        for _ in range(5):
            batch('zero_quota')
            time.sleep(0.15)
        observe('after_zero_requests')
        high = dict(limits, A=3 * unit)
        acknowledgements.append(llm.collective_rpc('dis_ml_quota_update', timeout=30, args=(high,))[0])
        for variant in range(3):
            batch('grow', variant)
        observe('grown')
        while time.monotonic() - started < 35:
            batch('sustained', 0)
            time.sleep(0.5)
        observe('after_35_seconds')
    finally:
        stopped = llm.collective_rpc('dis_ml_quota_stop', timeout=30)[0]
        (out / 'quota-state.json').write_text(json.dumps(stopped, indent=2))
    restarted = llm.collective_rpc('dis_ml_quota_start', timeout=30, args=(dict(config, limits=high),))[0]
    time.sleep(.3)
    restart_state = llm.collective_rpc('dis_ml_quota_stop', timeout=30)[0]
    result = {'model': MODEL, 'revision': REVISION, 'job_id': os.environ.get('SLURM_JOB_ID'),
        'host': os.uname().nodename, 'requests': len(rows), 'tenants': 4,
        'native_prefix_caching': False, 'cache_capacity_GiB': 2,
        'duration_s': time.monotonic() - started, 'unit_bytes': unit,
        'rejected_update': rejected, 'observations': observations, 'acknowledgements': acknowledgements,
        'stopped': stopped, 'restarted': restarted, 'restart_state': restart_state}
    (out / 'completed.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
