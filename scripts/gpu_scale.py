"""Populate a 128 GiB LMCache tier with real model KV, then test retained prefixes."""
import json, os, time, random
from pathlib import Path

from runtime import MODEL, REVISION, output_directory
from vllm import LLM, SamplingParams
from vllm.config import KVTransferConfig

def main():
    out = output_directory()
    inspect_occupancy = os.environ.get('DIS_ML_OCCUPANCY') == '1'
    extra = ({'worker_extension_cls': 'cache_occupancy_probe.CacheProbeExtension'}
             if inspect_occupancy else {})
    llm = LLM(model=MODEL, revision=REVISION, tokenizer_revision=REVISION, dtype='bfloat16',
              max_model_len=8192, max_num_seqs=4, max_num_batched_tokens=16384,
              gpu_memory_utilization=0.85, enforce_eager=True, enable_prefix_caching=False,
              kv_transfer_config=KVTransferConfig(kv_connector='LMCacheConnectorV1', kv_role='kv_both'),
              **extra)
    def snapshot(label):
        if inspect_occupancy:
            state = {'label': label, 'elapsed_seconds': time.monotonic()-start,
                     'workers': llm.collective_rpc('dis_ml_cpu_cache_snapshot', timeout=30)}
            with (out/'occupancy.jsonl').open('a') as stream:
                stream.write(json.dumps(state)+'\n')
            print('CACHE_OCCUPANCY '+json.dumps(state), flush=True)
    rng = random.Random(20261110)
    # Valid ordinary token IDs; unique early tokens prevent accidental cross-request reuse.
    prompts = [{'prompt_token_ids': [rng.randrange(100, 20000) for _ in range(4096)]} for _ in range(600)]
    params = SamplingParams(temperature=0, max_tokens=1)
    start = time.monotonic()
    snapshot('before_population')
    with (out/'batches.jsonl').open('w') as f:
        for i in range(0, len(prompts), 4):
            began = time.monotonic()
            generated = llm.generate(prompts[i:i+4], params, use_tqdm=False)
            assert len(generated) == 4
            row = {'completed': i+4, 'batch_seconds': time.monotonic()-began,
                   'elapsed_seconds': time.monotonic()-start}
            f.write(json.dumps(row)+'\n'); f.flush()
            print(json.dumps(row), flush=True)
            if (i+4) % 100 == 0:
                snapshot('after_'+str(i+4))
    for label, indices in [('oldest', [0,1]), ('newest', [598,599])]:
        began = time.monotonic()
        llm.generate([prompts[i] for i in indices], params, use_tqdm=False)
        print(json.dumps({'retention_probe': label, 'seconds': time.monotonic()-began}), flush=True)
    snapshot('after_retention_probes')
    (out/'completed.json').write_text(json.dumps({'requests':600,'prompt_tokens_each':4096,
        'elapsed_seconds':time.monotonic()-start,'cache_capacity_GiB':128,
        'note':'Use store/retrieve logs and occupancy metrics to validate retained data, not capacity alone.'},indent=2))

if __name__ == '__main__': main()
