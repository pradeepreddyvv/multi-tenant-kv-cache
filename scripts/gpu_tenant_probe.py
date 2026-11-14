"""Check identity propagation in the installed GPU LMCacheConnectorV1.

Identical tokens under different identities must miss on each identity's first
request and hit on its repeat. Logs establish hits; timing alone does not.
"""
import importlib.metadata as md
import json
import os
import time
from pathlib import Path

from runtime import MODEL, REVISION, output_directory

from vllm import LLM, SamplingParams
from vllm.config import KVTransferConfig


def main():
    out = output_directory()
    start = time.monotonic()
    extra = ({'worker_extension_cls': 'cache_occupancy_probe.CacheProbeExtension'}
             if os.environ.get('DIS_ML_OCCUPANCY') == '1' else {})
    llm = LLM(
        model=MODEL, revision=REVISION, tokenizer_revision=REVISION, dtype='bfloat16',
        max_model_len=2048, max_num_seqs=4, gpu_memory_utilization=0.85,
        enforce_eager=True, enable_prefix_caching=False,
        kv_transfer_config=KVTransferConfig(
            kv_connector='LMCacheConnectorV1', kv_role='kv_both'),
        **extra,
    )
    startup = time.monotonic() - start
    prompt = ('This document describes memory caching and reusable information. ' * 100
              + 'Summarize the document.')
    rows = []
    occupancy = []
    # The same prompt is also reused across modes. Tags must separate entries
    # from the unsalted entry created in the cache_salt-only mode.
    for mode in ['cache_salt', 'lmcache_tag']:
        for repetition in range(2):
            for tenant in range(16):
                identity = f'gpu-tenant-{tenant}'
                params = SamplingParams(temperature=0, max_tokens=8,
                    extra_args=({'kv_transfer_params': {'lmcache.tag.tenant': identity}}
                                if mode == 'lmcache_tag' else None))
                metadata = {'mode': mode, 'repetition': repetition, 'tenant': identity}
                print('TENANT_PROBE_BEGIN ' + json.dumps(metadata), flush=True)
                began = time.monotonic()
                result = llm.generate([{'prompt': prompt, 'cache_salt': identity}],
                                      params, use_tqdm=False)[0]
                row = dict(metadata, request_id=result.request_id,
                           seconds=time.monotonic() - began,
                           prompt_tokens=len(result.prompt_token_ids),
                           output_tokens=len(result.outputs[0].token_ids),
                           text=result.outputs[0].text)
                rows.append(row)
                with (out / 'requests.jsonl').open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
                print('TENANT_PROBE_END ' + json.dumps(row), flush=True)
            if os.environ.get('DIS_ML_OCCUPANCY') == '1':
                state = {'mode': mode, 'repetition': repetition,
                         'workers': llm.collective_rpc('dis_ml_cpu_cache_snapshot', timeout=30)}
                occupancy.append(state)
                (out / 'occupancy.json').write_text(json.dumps(occupancy, indent=2))
                print('TENANT_OCCUPANCY ' + json.dumps(state), flush=True)
    (out / 'completed.json').write_text(json.dumps({
        'model': 'Qwen/Qwen2.5-7B-Instruct', 'startup_seconds': startup,
        'versions': {p: md.version(p) for p in ['vllm', 'torch', 'lmcache']},
        'request_count': len(rows), 'tenant_count': 16, 'client_concurrency': 1,
        'native_prefix_caching': False, 'cache_capacity_GiB': 2,
        'all_outputs_identical': len({r['text'] for r in rows}) == 1,
        'note': 'Analyze matching request IDs in LMCache logs; no quota enforcement tested.'
    }, indent=2))


if __name__ == '__main__':
    main()
