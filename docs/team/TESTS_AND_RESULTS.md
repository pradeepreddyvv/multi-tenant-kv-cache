# Test catalog and measured results

All live measurements here are historical November 10, 2026 results. They are component feasibility tests, not final comparative research benchmarks. JSON links point to copied evidence; [the manifest](evidence/MANIFEST.json) records original source paths/hashes and transformations.

## GPU inference and external reuse

Qwen2.5-7B BF16 ran on an A30 with native prefix caching disabled. Repeated 1,006-token requests retrieved 768 cacheable tokens each from LMCache, and generated outputs matched. The 256-token chunk size leaves uncached prompt tokens. This establishes real external reuse; it is not a streaming TTFT experiment or an accuracy benchmark. [Recorded output](evidence/gpu-7b-cache.json).

## GPU occupied-cache scale

Two separate A100 allocations used 16 CPU cores and 192 GiB host RAM with a configured 128 GiB cache.

| Test | Workload | Evidence and limit |
|---|---|---|
| Initial scale, job 965041 on sg004 | 600 unique 4K prompts; oldest/newest probes | 131.25 GiB cumulative reported stores; 131.93 GiB Slurm RSS. Those numbers do not establish retained occupancy. |
| Occupancy follow-up, job 976316 on sg046 | Same seeded 600-prefix scale workload | Directly measured 127.99609375 GiB retained payload; 145.18649 GiB job-memory high-water; no sampled cgroup memory failures |

Direct occupied payload during the follow-up:

| Completed population requests | Retained KV GiB |
|---:|---:|
| 0 | 0 |
| 100 | 21.875 |
| 200 | 43.750 |
| 300 | 65.625 |
| 400 | 87.500 |
| 500 | 109.375 |
| 600 | 127.99609375 |

The follow-up held 9,362 chunks. Both oldest probes missed; both newest probes retrieved 4,096 tokens. Population plus probes took about 153.63 s excluding initialization. It reported 270 allocator-full warnings, with bounded occupancy and successful serving. These warnings are part of the result. The ~145 GiB job-memory figure includes overhead and is different from process RSS or retained KV.

**Conclusion:** same-node GPU inference plus a populated 128 GiB CPU cache is feasible in the tested allocation. **Not established:** multi-tenant quotas at that scale, 256/512 GiB, or future queue availability.

Evidence: [initial analysis](evidence/gpu-scale-first-analysis.json), [direct occupancy and retention analysis](evidence/gpu-scale-occupancy.json).

## GPU tenant identity and accounting

Two successful fresh-model runs each completed 64 sequential requests: 16 identities, two identity modes, and two repetitions. Same 906-token prompt, eight output tokens, 2 GiB cache, native prefix cache off. Sequential client concurrency was one.

| Identity mode | First requests across identities | Repeated requests | Interpretation |
|---|---|---|---|
| cache_salt alone | One miss, then 15 hits | 16 actual 768-token retrievals | Does not separate external entries in this installed GPU connector |
| Explicit LMCache tenant tags | 16 misses | 16 actual 768-token retrievals | Separation and reuse demonstrated |

Direct accounting found 42 MiB per tagged tenant: 672 MiB across 16 tenants, plus the prior 42 MiB untagged group. This establishes identity/accounting, not quotas or 16 concurrent inferences. An intermediate failed run encountered callable RPC serialization restrictions; the successful approach used a named worker extension without disabling those restrictions.

Evidence: [first successful summary](evidence/gpu-tenants-first-summary.json), [fresh-process repeat](evidence/gpu-tenants-repeat-summary.json). Request-level generated text was omitted from these shared summaries; the full private archive retains it.

## GPU primary-cache quota control

The four-tenant 7B test completed 184 requests in batches of four on an A30 with a 2 GiB primary CPU tier. It changed retention while inference batches were running:

| Phase | Tenant A retained bytes | B/C/D retained bytes | Observation |
|---|---:|---:|---|
| Initial | 42 MiB | 42 MiB each | Populated repeated prefixes |
| A's quota reduced to zero | 0 | 42 MiB each | 60 zero-occupancy samples; all 15 settled low-quota A requests missed |
| A's quota raised | 126 MiB | 42 MiB each | Three distinct A prefixes retained |

Only A's entries were evicted, 51 chunks across removal/refill. Logs recorded 161 actual 768-token retrievals overall; repeated-input text was consistent. Both changes overlapped inference batches and the hook reported no errors.

**Conclusion:** a custom mechanism can change primary-cache retention selectively during inference. **Not established:** an adaptive policy, HTTP TTFT benefit, a general enforcement-latency guarantee, or large-scale concurrent enforcement. The timestamp of the first zero sample is not a management-API latency measurement.

Evidence: [analysis](evidence/gpu-primary-quota-analysis.json), [actual event/occupancy timeline](evidence/gpu-primary-quota-timeline.json).

## CPU-only alternative

Earlier CPU tests on job 964668 established 0.5B/7B serving, a physically written 128 GiB raw-memory allocation, and small-cache reuse. The raw-memory test is **not populated KV**. A 0.5B run completed 39 requests spanning 16 salts and demonstrated live RAM-backed L2 quota behavior. A separate 7B retry retained 168 MiB L1 and retrieved 1,536 tokens across two requests; outputs matched the uncached control.

The stronger later test, job 981115 on sc005, used 32 CPU cores, 192 GiB RAM, no GPU, Qwen2.5-7B FP32, 4 GiB engine active KV, 2 GiB LMCache L1 and RAM-backed L2. It completed 68 streaming HTTP requests across 4/8/16 tenant identities with client concurrency four.

| Tenants | Cold/repeated round seconds | Median cold/repeated TTFT seconds |
|---:|---:|---:|
| 4 | 87.82 / 18.73 | 63.79 / 11.22 |
| 8 | 145.93 / 44.26 | 62.14 / 10.97 |
| 16 | 308.30 / 71.14 | 67.32 / 10.32 |

Those prompts had 1,006 tokens with 768 externally reused tokens and eight output tokens. A separate aligned 4,096-token probe had 70.64 s cold TTFT and 1.66 s cached TTFT; a cached 32-output probe had 1.32 s TTFT but 34.90 s full completion. Two single-request probes do not establish a general two-second SLO.

Reducing A's stock L2 quota evicted its L2 data while L1 still served A. A diagnostic safely deleted known A keys from L1, taking total L1 from 336 to 252 MiB; peers retained reuse. After raising A's quota and stopping selective deletion, total L1 became 504 MiB. Idle L1 clearing then proved B's actual L2 retrieval. This is not a general arbitrary-prefix L1 quota controller.

Peak job memory was 57.393 GiB. Final retained payload was about 1.42 GiB L1 plus 2.82 GiB L2, including duplicate data. CPU-only occupied 128 GiB KV is untested. A roughly 5.7-hour sequential fill estimate is an extrapolation from one cold-4K observation, not a measurement.

Evidence: [CPU analysis](evidence/cpu-7b-http-analysis.json), [raw-memory test](evidence/cpu-raw-memory-probe.json), [explicitly labeled fill estimate](evidence/cpu-128gib-estimate.json). The CPU scripts remain in the original project archive, not this GPU starter.

## Failed attempts and lessons

| Issue observed | Resolution or remaining implication |
|---|---|
| Login-node editor/agent resource warning | Move sustained work to an allocated compute tunnel; a normal-status email does not verify the current host |
| CPU image TLS / inherited certificate-path failures | Correct environment and retry; failed logs were retained |
| CPU worker threads restricted to one core | Successful tests used explicit thread settings and disabled problematic auto-binding |
| Overlapping CPU servers caused NUMA-local OOM | Stop the old server and retry in isolation; job-wide spare RAM does not guarantee NUMA-local headroom |
| Compiler cache pointed at read-only location | Set writable cache locations |
| First new cache server omitted a required L1 policy | Configure the policy and relaunch |
| GPU callable RPC serialization failed | Use named worker methods; do not disable serialization protections |
| GPU telemetry metadata warning | Use direct occupied-byte snapshots and request-matched logs; label attribution still needs repair |
| CPU telemetry dependency conflict | Functional pilot passed; stable benchmark environment still needs cleanup |
| Full cache emitted allocator warnings | Report pressure behavior and recent-prefix retention, rather than hide warnings |

## What the clean-repository checks proved

Python parsing, shell syntax and two output-preservation tests passed. All three cleaned GPU analyzers reproduced historical JSON exactly on temporary copies. Removing retrieval logs caused tenant/quota success checks to fail. These are saved-log/static checks, **not a fresh deployment of the cleaned wrapper**. See [validation notes](../VALIDATION.md).

## Separate RAG exploration, not Option 2

The earlier alternative RAG proposal had a ten-document pipeline: 245 layouts, 29 questions and 36 gold regions, all mapped at IoU ≥ 0.5; CPU embedding took 16.45 s and the full retrieval diagnostic 30.50 s. Three retrieved-image/text generations completed under a 2,000-reader-token budget. Some answers were wrong or truncated; no accuracy claim or proposed expansion algorithm was established. It does not count toward implementing the adaptive KV project. [Diagnostic summary](evidence/rag-diagnostic-summary.json); the full report includes the reader details.

## Claims we must not make

- That the adaptive policy already improves performance.
- That 128 GiB, 16 tenants and live quotas passed in one run.
- That GPU/CPU timing differences are a controlled hardware speedup; precision/builds differ.
- That occupied 128 GiB CPU KV, 256/512 GiB caches or multi-node transfer are verified.
- That a few repeated requests establish an SLO, a representative workload or statistical significance.
- That the professor has approved the direction or the research novelty is established.
