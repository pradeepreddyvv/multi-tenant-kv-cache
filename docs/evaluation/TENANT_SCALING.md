# Live tenant scaling extension

Status: local integration and CPU validation only. Fresh 8/16-tenant GPU runs remain pending.

## Integrated components

The live runner and quota adapter extend the merged evidence/metrics, plotting, evaluation specification, policy contract and allocation-policy components. Historical claims and the offline policy replay retain their original scope.

The live runner accepts `--tenant-count 4|8|16` and `--prefix-tokens` (multiples of 256). It records all tenant identities and the actual working-set size. Fixed allocation uses weight 3 for A and weight 1 for every other tenant. The default four-tenant workload remains unchanged. Run from the repository root with `PYTHONPATH=.`.

## First experiments

Use the previous A100 80 GB, 16-core, 192 GiB host allocation with a 128 GiB CPU cache, the same pinned 32B model, 4096-token prefixes and total offered rate 0.5 requests/s. Keep maximum simultaneous engine sequences at 4 to isolate identity count from concurrency. Use 32 prefixes per tenant for 8 tenants and 16 for 16 tenants, preserving the original aggregate 256-prefix working set and pressure ratio 2. Each condition compares equal, fixed and adaptive across seeds 11,29,47. This adds 18 runs. Original four-tenant results are a historical reference; changed source hashes and traces require explicit compatibility review before combining them into one scaling claim.

## Small-cache experiments

For 1/2 GiB budgets, first calibrate prefixes and concurrency. The 32B model needs 64 MiB for one 256-token prefix. At 1 GiB and 16 tenants, equal allocation fits only one such prefix per tenant, so this is a chunk-granularity boundary condition. Report it explicitly. Smaller adaptive shares can retain no complete chunk. Do not silently change cache chunk size, model or floors between policies.

After calibration, compare 4/8/16 tenants, three policies and three seeds at each budget (54 runs). Preserve the target working-set-to-cache ratio by adjusting pool size. Classify fit, pressure and demand shift separately. Changing prefix length creates a separate experiment family from the large-cache study.

## Validity and analysis

Use paired traces within each condition, fresh-process caches, preserved manifests and logs, and recorded realized load. Report per-tenant median TTFT, reuse, occupancy, evicted bytes, failures and achieved throughput. Withhold tail percentiles when sample counts are inadequate. Keep allocated memory, retained payload, quota targets and physical transfers distinct. Warm-up occupancy must be inspected before calling a phase steady state.

The earlier evaluation specification uses a different 7B footprint, timing and proposed request-rate calibration. It is a reference design, not the manifest for the completed 32B pilot. Do not label pilot results as completion of every E05–E10 experiment.

## Launch inside an existing allocation

Set `HF_HOME` to the cached model directory, `XDG_CACHE_HOME` to a writable runtime cache, `GPU_IMAGE` to the tested container, and `DIS_ML_RESULT_DIR` to a new absolute output directory. The launcher refuses an existing output directory. Example arguments for the first eight-tenant comparison:

```bash
LIVE_CAPACITY_GIB=128 bash scripts/run_live.sh \
  --policy equal --tenant-count 8 --prefix-tokens 4096 --prefix-pool 32 \
  --budget-gib 128 --duration 1200 --warmup 600 --shift 900 \
  --rate 0.5 --max-num-seqs 4 --gpu-utilization 0.92 --seed 11 \
  --model Qwen/Qwen2.5-32B-Instruct \
  --revision 5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd
```

Use a new result directory for each policy/seed. Run `python3 scripts/analyze_live.py --help` for saved-run validation and `python3 scripts/compare_live.py --help` for matched equal/fixed/adaptive comparisons. Experimental slow/reuse/v3 controllers and a shared-cache option are available for separate studies; their presence does not establish a live improvement.
