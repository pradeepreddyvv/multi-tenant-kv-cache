# Source-to-claim list (task C01)

Owner: C (results and evaluation). Reviewer: A. Prepared November 18, 2026.

Every number that appears on a slide or in the report must map to a row here. A claim without a row is not presented. This list covers the November 10, 2026 Sol feasibility runs only. No new run was launched to prepare it.

## Verification levels

| Level | Meaning |
|---|---|
| **S** | Stated in the consolidated Nov 10 report (`SOL_FEASIBILITY_COMPLETE_REPORT.pdf`, team preservation archive) and consistent with `docs/RESULTS.md`. Secondary source only. |
| **X** | S, plus an independent arithmetic cross-check against the model's KV layout (see `METRICS.md` § Units) agrees exactly. |
| **R** | Raw record replayed with the repository analyzer on a copy of the preserved evidence and matched (task C03). |

**Current state: no row is at level R yet.** The raw results archive is not available to C as of Nov 18. Rows move to R when `scripts/verify_saved_runs.py` and the per-run analyzers are replayed on a copy of it. Until then, slides may cite S/X rows with the source named, but the evidence freeze (Nov 20, 12:00) should aim for R on every plotted number.

Evidence paths are relative to the archive's `DIS_ML/` directory. They are never copied into this repository.

## GPU external reuse (job 959878, A30 24 GiB, 40 GiB host RAM)

| ID | Claim | Value | Evidence | Analyzer / field | Level | Boundary (must accompany the claim) |
|---|---|---|---|---|---|---|
| K01 | Qwen2.5-7B BF16 KV tensors are stored to and retrieved from LMCache's CPU tier | Two 1,006-token requests stored 768 cacheable tokens each; repeats retrieved 768 each; outputs matched | `results/gpu-7b/gpu_cache.json`, `results/gpu-7b-cache.log` | No analyzer in this repo (original `gpu_baseline.py` path) | X | Native prefix caching disabled. Reuse is shown by retrieval logs, not by a faster repeat. Not a TTFT measurement. |

## Retained-cache scale (job 976316, sg046, A100 80 GiB, 192 GiB host RAM)

| ID | Claim | Value | Evidence | Analyzer / field | Level | Boundary |
|---|---|---|---|---|---|---|
| K02 | Directly measured retained KV reached the configured 128 GiB tier | 127.99609375 GiB = 9,362 chunks = 137,434,759,168 bytes | `results/gpu-scale-976316/occupancy.jsonl`, `occupancy-analysis.json` | `analyze_gpu_scale_occupancy.py` → `peak_retained_GiB` | X | Under-lock sum of live cache objects (pinned-version internal fields). Single tenant, no quotas. |
| K03 | Retained bytes grow linearly while filling | 0, 21.875, 43.75, 65.625, 87.5, 109.375, 127.996 GiB at 0–600 requests (step 100) | same | `occupancy[].tensor_bytes` | X | 600 unique 4,096-token synthetic prompts, seed 20261110. Not an application workload. |
| K04 | Under capacity pressure, oldest prefixes are evicted and newest are retained | Both oldest probes missed; both newest retrieved 4,096 tokens | `results/gpu-scale-976316.log` | `oldest_probe_hits`, `newest_probe_retrieves` | S | Two probes each. Shows retention order, not an eviction-policy evaluation. |
| K05 | Host memory stayed within the allocation | Sampled cgroup high-water 145.19 GiB under 192 GiB limit; failcnt 0 | `results/gpu-scale-976316-memory.jsonl` | `max_sampled_cgroup_highwater_GiB`, `job_limit_GiB`, `max_memory_failcnt` | S | Cgroup total includes model/runtime overhead, so it is larger than retained KV. Not comparable to K08's Slurm MaxRSS. A 128 GiB cache needs well over 128 GiB allocated RAM. |
| K06 | The allocator reported cache-full warnings at capacity | 270 warnings (same count in jobs 965041 and 976316) | run logs | `cache_full_warning_count` | S | Must be shown, not hidden. Serving still completed. |
| K07 | Population plus probes took about 2.5 minutes | 153.63 s (976316), 154.55 s (965041), excluding model/cache initialization | `completed.json` | `elapsed_seconds` | S | Batch of 4, one output token. Not a throughput benchmark. |
| K08 | First scale run (job 965041, sg004) completed on a different node | Slurm MaxRSS 131.93 GiB; 131.25 GiB *cumulative store traffic* | `results/gpu-scale-965041/` | `analysis.json` (older analyzer) | X | 131.25 GiB is write traffic (600 × 16 chunks × 14 MiB), **not** retained occupancy. Use only to explain the distinction; K02 is the occupancy claim. |

## Tenant identity (job 959878; runs `gpu-tenants-run1`, `gpu-tenants-run3`)

| ID | Claim | Value | Evidence | Analyzer / field | Level | Boundary |
|---|---|---|---|---|---|---|
| K09 | Explicit LMCache tenant tags separate identical prompts across tenants | 16 first requests missed; 16 repeats retrieved 768 tokens; reproduced in two fresh model processes | `results/gpu-tenants-run{1,3}/analysis.json`, logs | `analyze_gpu_tenant_probe.py` → `tagged_isolation_and_reuse_pass` | S | Sequential (concurrency 1), 906-token prompts, 2 GiB tier. Connector/version-specific. Not a security guarantee. |
| K10 | `cache_salt` alone did not separate external entries on this connector | 1 miss, then 15 cross-identity hits | same | `cache_salt_alone_separates_external_cache` = false | S | Installed LMCacheConnectorV1 (LMCache 0.4.4) only. The CPU MP connector propagated salt correctly. |
| K11 | Per-tenant retained bytes are measurable | 16 tenants × 42 MiB = 672 MiB tagged, plus one 42 MiB untagged group | `results/gpu-tenants-run3/occupancy.json` | `occupancy[].workers[][].tenants` | X | 42 MiB = 3 chunks × 14 MiB = 768 tokens × 56 KiB. Diagnostic instrumentation, not a management API. |

## Manual primary-L1 quota (job 959878; run `gpu-primary-quota-run1`)

| ID | Claim | Value | Evidence | Analyzer / field | Level | Boundary |
|---|---|---|---|---|---|---|
| K12 | One tenant's retained bytes were lowered and raised during live inference | A: 42 MiB → 0 → 126 MiB; B/C/D at 42 MiB in every sample | `quota-state.json`, `completed.json` | `before_bytes`, `after_bytes`, `peer_occupancy_stable` | X | Custom bounded hook (30 s lifetime, 100 ms cadence). Two scheduled manual changes. Not stock LMCache quotas, not adaptive. |
| K13 | The lowered quota took effect for requests | 15 of 15 A requests wholly inside the settled low-quota interval missed | `requests.jsonl`, log | `low_quota_A_requests`, `low_quota_A_lookup_misses` | S | Settled = batch started > 0.2 s after the change. |
| K14 | Enforcement reached zero quickly | First zero sample after the first enforcement pass; 60 zero samples while lowered | `quota-state.json` | `seconds_to_first_zero_after_lower`, `zero_occupancy_samples_while_lowered` | S | Resolution is the 100 ms sample cadence. Not a measured API latency. |
| K15 | Only the targeted tenant was evicted; changes overlapped inference | 51 evicted chunks, all A; both changes overlapped a batch; 0 thread errors | `quota-state.json`, `requests.jsonl` | `evicted_chunks`, `event_overlap_with_inference_batch`, `thread_errors` | S | Batches of 4, offline engine. Not concurrent HTTP serving. |
| K16 | The workload completed with real external retrievals | 184 requests; 161 actual 768-token retrievals; outputs consistent per input | log, `requests.jsonl` | `requests`, `actual_768_token_retrieves`, `output_consistency_by_input` | S | Output consistency is not a quality claim. |

## Cleaned-repository validation (Nov 13, `docs/VALIDATION.md`)

| ID | Claim | Value | Evidence | Level | Boundary |
|---|---|---|---|---|---|
| K17 | Cleaned analyzers reproduce the original saved analyses exactly, and fail when retrieval logs are removed | 3 runs replayed; 2 negative checks | `scripts/verify_saved_runs.py` output (not archived in repo) | S | Replay, not deployment. The cleaned launcher has **no fresh GPU run** (E01 pending). |

## Context only: CPU-only alternative (job 981115)

H05 in the workbook. CPU-only is deferred (D06) and outside the selected plan. If mentioned, it is one line: 68 streaming HTTP requests across 4/8/16 identities at client concurrency 4 with real L1/L2 reuse. Never place CPU FP32 and GPU BF16 timings side by side as a hardware comparison.

## Do not claim

These come from the report's "Not claimed as completed" section and `docs/LIMITATIONS.md`. Slides must not state or imply any of them.

- A combined 128 GiB + multi-tenant + live-quota run. K02, K09 and K12 are **separate** experiments on different nodes/capacities.
- Any TTFT, TPOT, goodput or two-second SLO result for the GPU path. The GPU diagnostics were offline-engine calls with no streaming timestamps.
- That adaptive or dynamic quotas improve latency, fairness or throughput. No controller has run.
- 16-way concurrency. 16 identities were tested sequentially.
- 256/512 GiB caches, multi-node KV transfer, or fresh-job repeatability of the full setup.
- That the cleaned launcher in this repository has been deployed.
- Native-prefix-cache baselines or equal-total-memory comparisons.

## Inconsistencies found for kickoff

1. **Shared-cache baseline dropped.** The proposal (§3.6) lists B0 = one shared CPU cache with default eviction. The workbook's E04–E07 compare only equal, fixed-unequal and adaptive quotas. The shared cache is the natural "no partitioning" reference. → B / D05: keep or explicitly drop with a reason.
2. **Two-second goodput threshold.** The proposal defines goodput as TTFT ≤ 2 s, with a revision after pilots. W16 and the report say no 2 s SLO is established. → Slides should describe goodput's threshold as "set from pilot measurements before final comparisons", not as 2 s.
3. **Scope change.** The proposal targets two applications and a 16 GiB budget. The plan uses 4/8/16 tenants and a pilot-calibrated small budget (2 GiB in E02/E04). The slides should present the current plan and state that scope changed after feasibility.
4. **Interface v1 cannot compute hit rate or evictions.** See `METRICS.md` § Interface v1 gaps.

## Slide rubric and duration

Source: course Phase 2 assignment page (copy provided Nov 18 as `docs/presentation.html`).

- **Deadline:** draft slide PDF by 11:59 pm Nov 21, one submission per group. Timezone is not stated on the page (D02 still open on that point).
- **Duration:** not yet announced ("based on the number of project groups"). Presentation timeline link is TBD.
- **Rubric (40 points):** problem, motivation and RQs 5; technical challenges (2–4) 4; technical ideas and system design 9; implementation and methodology 5; **experimental results 7; analysis and insights 5**; slide quality and timing 3; Q&A 2. Presenter split is not graded, but all members attend and answer questions.

Requirements that bear on the evidence section:

- Each experiment must name the RQ it answers, the main observation, why it occurs and what it teaches. "Faster/better" alone is insufficient.
- Separate **observations** (measured) from **insights** (what they teach). This list's rows are the observations.
- Negative and unexpected results are explicitly valued. Candidates: K10 (`cache_salt` does not isolate on this connector), K06 (allocator-full warnings at capacity), K08 (store traffic ≠ retained bytes), and the finding that stock LMCache quotas govern L2 and do not evict primary L1 copies.
- Implementation must state **changes from the Phase 1 proposal**: two applications / 16 GiB → 4/8/16 tenants with a small pilot budget; stock quota API insufficient → custom tenant-aware retention hook (the proposal's own §3.5 fallback).
- Figures need labeled axes, units, legends and a stated takeaway.

**Gap against the rubric:** the assignment expects "meaningful preliminary or final experimental results" that answer the RQs. The proposal's RQs (do dynamic quotas beat shared or fixed caches?) cannot be answered by the Nov 10 evidence, which has no latency data and no policy comparison. Unless pilot E04 runs by the Nov 20 noon freeze, the results section must either frame Phase 2 RQs that the evidence does answer (mechanism feasibility and cost) or present B04's offline policy replay, clearly labeled as synthetic. Team decision needed at kickoff.
