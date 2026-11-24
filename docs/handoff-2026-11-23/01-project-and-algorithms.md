# Project, implementation and algorithms

## Problem in plain language

Several applications share one language-model server. Repeated prompt prefixes can reuse attention keys and values (the KV cache) instead of repeating all prefill computation. GPU memory is expensive and limited; CPU RAM can retain more cached prefixes. Applications compete for this finite memory. Giving a busy application more cache may help it, but taking memory from others can evict useful prefixes and create refill work.

Our question is when dynamic CPU-cache shares help compared with simple equal shares, and when changing the shares costs more than it saves. The workloads model repeated document/context prefixes; they are synthetic, not production customer traces.

## Execution flow

Seeded arrivals → tenant-tagged prompt → HTTP streaming wrapper → vLLM inference on GPU → LMCache lookup/restore of CPU-retained prefix KV → prefill missing tokens → decode → first nonempty output recorded by client. Cache events and independent occupancy samples are joined with request records. A controller periodically observes demand and changes tenant CPU-cache quotas; a roughly 100 ms enforcement pass evicts entries as needed.

Tenant tags isolate external-cache identities. Native vLLM prefix caching is disabled for these comparisons. CPU quotas are soft enforcement targets, not preallocated physical reservations or immediate hard admission limits. Pins and concurrent stores can delay compliance.

### Built versus reused

Reused: Qwen model, vLLM inference engine, LMCache backing cache, CUDA/PyTorch and Sol infrastructure.

Team implementation/integration: tenant identity and quota hook, allocation policies and controller, synthetic traces, HTTP/SSE measurement harness, request/event matching, occupancy collection, analysis, validation and figures. This is not a complete reproduction of Mooncake, FairCache or every algorithm in the literature.

## Main live configuration

| Item | Setting |
|---|---|
| Resource | ASU Sol; one A100 with 80 GB GPU memory, 16 CPU cores, 192 GiB allocated host RAM |
| Model | Qwen2.5-32B-Instruct, BF16; revision `5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd` |
| CPU KV capacity | 128 GiB; allocation leaves room for process/runtime overhead |
| KV representation | 262,144 bytes/token; 256-token chunks, 64 MiB/chunk for this model |
| Main tenant count | Four, A–D |
| Prefix pool | 64 prefixes per tenant; 4,096 prefix tokens plus 64 suffix tokens |
| Generation | 32 output tokens; max model length 4,352; max concurrent sequences 4 |
| Offered load | 0.5 requests/second; this is not saturation-capacity measurement |
| Run timeline | 1,200 s; warm-up ends at 600 s; demand shifts from A to B at 900 s |
| Analysis phases | Before shift: 600–900 s; after shift: 900–1,200 s |
| Working set | Approximately 256 GiB potential prefix KV against 128 GiB cache |
| GPU setting | Memory utilization target 0.92 |

An 80 GB GPU, 192 GiB RAM allocation and 128 GiB CPU cache are different quantities. Quota totals do not establish actual occupied memory. Do not infer exact CPU model, CUDA or package versions from this table; recover those from environment logs before final reporting.

## Policy definitions

| Internal name | Plain-language meaning | Main behavior |
|---|---|---|
| equal | Equal fixed shares | 25% each, or 32 GiB per tenant |
| fixed | Fixed priority shares | A gets 50%; each other tenant approximately 16.7%; remains fixed after demand shifts |
| adaptive | Original demand-following policy | Roughly 5 s windows of completed eligible input tokens; EWMA smoothing alpha 0.5; 20% total floor pool; 5% hysteresis; 10% transfer cap |
| slow | Slower arrival-based controller | All arrivals; at least 30 s AND 20 arrivals between decisions; smoothing alpha 0.3; 20% floor pool |
| reuse | Repeated-prefix controller | Uses arrivals whose prefix has been seen; same slower cadence; 20% floor pool |
| v3 | Cautious adaptive | Repeat-aware signal, 50% total floor pool (16 GiB each with four tenants), equal 0.05-arrival/s prior, slower cadence |
| shared | Shared cache without tenant quotas | Common backing-cache replacement; no per-tenant capacity protection |

Candidate controllers use bounded per-tenant ordered prefix history and whole-prefix allocation units, with a 5% threshold and 10% cap. The exact executable implementation is `policy/candidates.py` in the frozen candidate-run source (not yet present on main). The original policy is in `policy/allocation.py` and `policy/controller.py`.

Conceptual controller: accumulate observations → wait for cadence/sample threshold → smooth demand → assign floor shares → distribute remaining capacity by demand → round to allocation units → apply threshold/cap → publish quotas. Inspect code for exact rounding and transfer rules before writing final pseudocode.

V3 is an internal version label, not a published algorithm. The candidate changes multiple mechanisms together, so improved behavior cannot yet be attributed only to slower updates.

## Explored simulation families

Thirteen policies: equal/fixed LRU; shared LRU, FIFO, LFU, random, second-chance, probation, two-hit and frequency-admission; slow, reuse and cautious adaptive. These are simplified family implementations. A prior V4 equal-entitlement/spare-eviction simulation was also explored; it is not a deployed live policy.

## Title and research positioning

The project retains its full title. In the report, explain that “cost-aware” motivates accounting for reallocation/refill costs; the present controller does not explicitly optimize a measured transfer/recompute cost function. “Tiered” describes GPU inference plus CPU-retained KV; the implemented policy changes CPU shares rather than jointly optimizing every tier. These are limitations and possible future extensions.
