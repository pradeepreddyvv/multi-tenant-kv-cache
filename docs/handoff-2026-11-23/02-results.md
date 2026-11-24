# Results and evidence boundaries

## 1. Historical component feasibility: separate November 10 runs

- A large-cache test retained 127.996 GiB KV across 9,362 chunks; 270 allocator-full warnings were recorded. The approximately 145.2 GiB job-memory high-water includes approximately 14.6 GiB reclaimable file cache; it is not evidence that 145 GiB is the minimum RAM required.
- Tagged identity test: 16 sequential identities, two fresh-process runs, first requests missed and repeated requests retrieved 768 tokens. This is isolation behavior, not 16-tenant concurrent performance.
- `cache_salt` alone did not isolate external cache identity on the legacy connector. This is version/configuration-specific, not a universal security conclusion.
- Four-tenant manual quota diagnostic: 184 requests; A occupancy moved 42 → 0 → 126 MiB; peers remained at 42 MiB. All 15 A requests in the settled low-quota interval missed.
- The 60/60 zero samples were taken immediately after enforcement passes. A's prefix was stored and evicted 17 times (51 chunks). Zero samples do not establish continuous zero occupancy. Enforcement occurs at the next approximately 100 ms pass.

These earlier smaller-model diagnostics have different chunk sizes and configurations from the later 32B study. Do not pool their metrics.

## 2. Offline policy validation from Akshith

Four/eight/sixteen tenants × three seeds (11, 22, 33) × three policies: 27 cases, 120 windows each, 3,240 windows and 30,240 tenant records. The nominal 2 GiB budget is allocation arithmetic, not occupied KV RAM. This suite ran as CPU validation on Sol (job 2138912, sc003; reported Python 3.11.18, commit 503e6b3), without model inference or live GPU timing. Its 23 tests overlap later integrated suites and must not be added as disjoint coverage. Zero-demand smoothing can preserve skew; idle reset is not implemented.

## 3. Live 32B feasibility

`large32-stress01`: seed 22, 614 valid requests, measured peak 128 GiB occupied cache. There were 288 full-hit and 326 miss requests; conditional median TTFT was about 0.176 s versus 1.773 s. This is an association between request groups, not a causal 10× speedup experiment. Reaching 99% capacity took about 727 s, beyond the nominal 600 s warm-up. There were 233 allocation warnings. Approximately 98% GPU utilization and 171 GiB host usage were samples, not run averages.

## 4. Original live comparison: nine runs

Three policies (equal, fixed, original adaptive), each on seeds 11, 29 and 47. Each policy processed 621, 582 and 567 requests respectively by seed, with matched workload traces within a seed.

| Comparison | Before shift | After shift |
|---|---:|---:|
| Original adaptive versus equal: median paired change in median TTFT | +13.34% | +13.61% |
| Seed range of change | +7.44% to +50.26% | +9.15% to +17.25% |
| Original adaptive versus fixed: median paired change | +91.65% | +5.13% |

Positive means slower. These ranges describe three seeds; they are not confidence intervals. Original adaptive lost to equal in both phases for every tested seed. Fixed favored the initially hot tenant and beat equal before the shift; equal beat fixed after the shift for all three seeds.

### Diagnosis, seed 11

| Metric | Equal | Original adaptive |
|---|---:|---:|
| Before-shift reuse | 40.49% | 26.69% |
| After-shift reuse | 49.32% | 28.72% |
| Mean sampled occupied GiB, before | 127.63 | 73.95 |
| Mean sampled occupied GiB, after | 127.63 | 76.10 |
| Full-run evicted GiB, including warm-up | 207 | 351.44 |
| Quota updates | 0 | 205 |
| Measured requests classified as hits | 139 | 87 |
| First touches | 61 | 61 |
| Repeat misses | 111 | 163 |

This supports an explanation involving churn, lost reuse and incomplete refill. It is not yet a controlled mechanism ablation. Summed quota changes of roughly 2,550 GiB are changes in assigned limits, NOT measured bytes transferred. An analysis process overlapped the last minute of the adaptive seed-11 run; its impact was not quantified.

## 5. Seven-policy live screen: one seed, 601

All seven local analyses report valid runs, 622 requests and zero request errors; 154 measured requests before and 171 after the shift. Same trace hash: `89aba29abb42ee33abc03e71470cb8ce08577eda0e9d001097981cb8c6bb20f7`. Values below are generated directly from the saved analysis snapshot. Units are seconds.

| Policy | Median before | Median after | p95 before | p95 after |
|---|---:|---:|---:|---:|
| equal | 1.152 | 1.161 | 3.038 | 3.446 |
| fixed | 0.191 | 1.225 | 2.318 | 3.424 |
| adaptive | 1.178 | 1.261 | 3.378 | 4.321 |
| slow | 0.202 | 1.155 | 2.305 | 3.320 |
| reuse | 0.246 | 1.184 | 2.984 | 3.740 |
| v3 | 0.202 | 0.930 | 2.542 | 3.725 |
| shared | 0.225 | 1.001 | 2.295 | 3.327 |

Cautious adaptive (`v3`) reduced post-shift median TTFT by 19.85% versus equal (about 230 ms), with four updates rather than original adaptive's 204. But its reported p95 increased, tenant C's post-shift median increased about 3.3%, and some pre-shift tenants were also worse. Shared caching has a useful latency tradeoff but no quota protection. Slow also has competitive tails. There is no single winner across these objectives.

This candidate was selected after screening one seed. It needs held-out replication, not a claim of statistically established superiority.

### Percentile caution

The analyzer uses sorted index `int(0.95 * (n - 1))`, and withholds p95 for groups below 100 requests. Nearest-rank post-shift p95 would instead be approximately equal 3.914 s, v3 3.937 s and shared 3.362 s. The median conclusion is unchanged; the apparent size of the tail penalty depends on convention. Choose and disclose one convention in Phase 3 and regenerate every comparison consistently. Do not silently replace historical values.

## 6. Exploratory simulation: 1,560 cases

Thirteen policies × six workloads × 20 seeds (200–219), run as simulation on Sol, not GPU inference. Best median cache-hit gains versus equal LRU:

| Workload | Leading family | Gain, percentage points | Worst observed tenant change, points |
|---|---|---:|---:|
| Demand shift | Shared second-chance | +6.07 | -22.64 |
| Churn | Shared LRU | +11.66 | -19.51 |
| Burst | Shared probation | +9.47 | -18.75 |
| Scan | Shared LFU / probation | +11.05 | -17.02 |
| Skewed reuse | Shared second-chance | +5.06 | -8.70 |
| Low reuse | Shared LFU / probation | +0.35 | -2.27 |

A policy can improve overall reuse while harming individual applications. These simulations use instantaneous whole-prefix accesses and omit GPU timing, pins, concurrent writes, partial hits and transfer costs. Some screening metadata dictionaries are unbounded. They guide hypotheses, not live-performance claims. Prior V4 spare-eviction simulation matched equal after warm-up on its sampled cases; no live implementation or general guarantee follows.

## 7. Runs still needing recovery

Job 2202045 scheduled seven policies on shift, scan and burst (21 full runs plus seven smoke runs). Seven full shift results are locally available. Do not infer the other fourteen completed.

Job 2221040 scheduled six 8/16-tenant smokes and eighteen full runs: two tenant counts × three policies × three seeds. The watcher subsequently recorded it RUNNING, but saved zero snapshots. Therefore 8/16 live performance remains unverified in this handoff. No ten-tenant live result is verified.

## What we can safely conclude

Equal is the strongest replicated reference against our original adaptive policy. Cautious adaptive is a promising median-latency candidate for one synthetic demand-shift scenario, with tail and tenant tradeoffs. Workload reuse, cache pressure, demand duration and the cost of changing allocations plausibly determine the best policy; isolate their effects before making broader causal claims.
