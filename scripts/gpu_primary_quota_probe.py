"""Four tenants, 7B GPU inference and live quotas on actual primary CPU KV."""
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
        worker_extension_cls='primary_quota_probe.PrimaryQuotaProbeExtension',
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
    plan = {'initial_limits': {t: measured[t]['tensor_bytes'] for t in tenants},
            'changes': [{'after_seconds': 1.1, 'tenant': 'A', 'limit_bytes': 0},
                        {'after_seconds': 7.1, 'tenant': 'A', 'limit_bytes': 3 * unit}]}
    start = llm.collective_rpc('dis_ml_start_quota_probe', timeout=30, args=(plan,))
    try:
        began = time.monotonic()
        index = 0
        while time.monotonic() - began < 13:
            batch('live', index % 3 if time.monotonic() - began > 8 else 0)
            index += 1
        time.sleep(0.2)
        after = llm.collective_rpc('dis_ml_cpu_cache_snapshot', timeout=30)
    finally:
        state = llm.collective_rpc('dis_ml_stop_quota_probe', timeout=30)
        (out / 'quota-state.json').write_text(json.dumps(state, indent=2))
    (out / 'completed.json').write_text(json.dumps({'model': 'Qwen/Qwen2.5-7B-Instruct',
        'job_id': os.environ.get('SLURM_JOB_ID'), 'host': os.uname().nodename,
        'requests': len(rows), 'tenants': 4, 'max_batch_size': 4,
        'cache_capacity_GiB': 2, 'native_prefix_caching': False,
        'start': start, 'plan': plan, 'before': before, 'after': after,
        'note': 'Custom pinned-version diagnostic L1 eviction hook, not stock quota support.'}, indent=2))


if __name__ == '__main__':
    main()
