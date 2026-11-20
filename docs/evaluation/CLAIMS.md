# Source-to-claim list (task C01)

Owner: C (results and evaluation). Reviewer: A. Prepared November 18, 2026; evidence levels updated November 19.

Every number that appears on a slide or in the report must map to a row here. A claim without a row is not presented. This list covers the November 10, 2026 Sol feasibility runs only. No new run was launched to prepare it.

## Verification levels

| Level | Meaning |
|---|---|
| **S** | Stated in the consolidated Nov 10 report (`SOL_FEASIBILITY_COMPLETE_REPORT.pdf`) and consistent with `docs/RESULTS.md`. Secondary source only. |
| **X** | Agrees exactly with an independent arithmetic cross-check against the model's KV layout (see `METRICS.md` § Units). |
| **D** | Read directly from the saved analysis or run JSON in the curated evidence pack (below), with checksums verified. |
| **D+** | Independently recomputed by C from a raw run record (not just read from a derived summary). |
| **R** | Raw request logs replayed with the repository analyzer on a copy of the preserved evidence, matching the saved analysis exactly. |

**Current state (Nov 19, evening):** 14 of 17 rows reach **R** (K06, K07 and K17 only for their GPU-run parts), and K11 is recomputed from its raw snapshot (D+). K08 stays at D; its job's raw files are not in the archive. K01's retrieval count is still report-only.

## Evidence pack

Branch `docs/team-handoff`, directory `docs/team/evidence/` (commit `d00a9a5`). All 14 files passed `sha256sum -c SHA256SUMS` on Nov 19. `MANIFEST.json` gives each file's original path under the archive's `DIS_ML/` directory, the original SHA-256 and the transformation. All files are exact copies, except the two tenant summaries, which had generated text removed. The evidence column below gives the pack file name, with the original path in parentheses.

Checksums establish integrity and provenance, not experimental validity.

## Raw log archive

`historical-gpu-raw-logs-2026-11-10.zip` (SHA-256 `79063d808b16f383326f983359373b03cf488f188dc27e3a2d84b4336c065781`), received from A on Nov 19. It is kept out of Git because it holds original environment paths and node names. It contains request records, engine logs, snapshots and saved analyses for `gpu-scale-976316`, `gpu-primary-quota-run1`, `gpu-tenants-run1` and `gpu-tenants-run3`, plus the original scripts. It does not include `gpu-7b` or `gpu-scale-965041`.

Checks performed by C on Nov 19 (saved-log replay; no inference):

1. All 30 files passed `sha256sum -c SHA256SUMS`.
2. The five archive files that the pack manifest lists as sources hash to the manifest's `source_sha256`, so the pack and the archive derive from the same originals.
3. `python3 scripts/verify_saved_runs.py <archive>/results` reproduced the saved analyses for `gpu-tenants-run3`, `gpu-primary-quota-run1` and `gpu-scale-976316` exactly. Both empty-log negative checks failed as required.
4. `analyze_gpu_tenant_probe.py` on a copy of `gpu-tenants-run1` reproduced its saved analysis byte-for-byte.
5. The repository analyzers differ from the archived originals only in path handling, plus the stricter quota pass condition described in `docs/VALIDATION.md`. The replays pass under the stricter condition.

## GPU external reuse (job 959878, A30 24 GiB, 40 GiB host RAM)

| ID | Claim | Value | Evidence | Field | Level | Boundary (must accompany the claim) |
|---|---|---|---|---|---|---|
| K01 | Qwen2.5-7B BF16 KV tensors are stored to and retrieved from LMCache's CPU tier | Two 1,006-token requests stored 768 cacheable tokens each; repeats retrieved 768 each; outputs matched | `gpu-7b-cache.json` (`results/gpu-7b/gpu_cache.json`); retrievals only in `results/gpu-7b-cache.log` (not in pack) | `runs[].texts` | Outputs matched: **D**. 768-token retrieval: **S, X** | Native prefix caching disabled. Reuse is shown by retrieval logs, not by the faster repeat (2.71 s → 0.71 s), which the JSON itself says is not proof. Not a TTFT measurement. |

## Retained-cache scale (job 976316, sg046, A100 80 GiB, 192 GiB host RAM)

| ID | Claim | Value | Evidence | Field | Level | Boundary |
|---|---|---|---|---|---|---|
| K02 | Directly measured retained KV reached the configured 128 GiB tier | 127.99609375 GiB = 9,362 chunks = 137,434,759,168 bytes | `gpu-scale-occupancy.json` (`results/gpu-scale-976316/occupancy-analysis.json`) | `peak_retained_GiB`, `occupancy[-1]` | **R, X** | Under-lock sum of live cache objects (pinned-version internal fields). Single tenant, no quotas. |
| K03 | Retained bytes grow linearly while filling | 0, 21.875, 43.75, 65.625, 87.5, 109.375, 127.996 GiB at 0–600 requests (step 100); about 24.7 s per 100 requests | same | `occupancy[].tensor_bytes`, `elapsed_seconds` | **R, X** | 600 unique 4,096-token synthetic prompts, seed 20261110. Not an application workload. |
| K04 | Under capacity pressure, oldest prefixes are evicted and newest are retained | Both oldest probes had 0 hit tokens; both newest retrieved 4,096 tokens | same | `oldest_probe_hits`, `newest_probe_retrieves` | **R** | Two probes each. Shows retention order, not an eviction-policy evaluation. |
| K05 | Host memory stayed within the allocation | Sampled cgroup high-water 145.19 GiB under 192 GiB limit; failcnt 0 | same | `max_sampled_cgroup_highwater_GiB`, `job_limit_GiB`, `max_memory_failcnt` | **R** | Cgroup total includes model/runtime overhead, so it is larger than retained KV. Slurm MaxRSS for this job agrees (152,237,644 KiB = 145.18 GiB, `slurm-accounting-976316.txt`). Not comparable to K08, which is a different job. A 128 GiB cache needs well over 128 GiB allocated RAM. |
| K06 | The allocator reported cache-full warnings at capacity | 270 warnings in each of jobs 976316 and 965041 | same; `gpu-scale-first-analysis.json` | `cache_full_warning_count`, `allocator_full_warning_count` | 976316: **R**. 965041: **D** | Must be shown, not hidden. Serving still completed. |
| K07 | Population plus probes took about 2.5 minutes | 153.63 s (976316), excluding model/cache initialization | same | `completed.elapsed_seconds` | **R** (154.55 s for 965041: **S** only) | Batch of 4, one output token. Not a throughput benchmark. |
| K08 | First scale run (job 965041, sg004) completed on a different node | Slurm MaxRSS 131.93 GiB; 131.25 GiB *reported store traffic* (2,457,600 tokens) | `gpu-scale-first-analysis.json` (`results/gpu-scale-965041/analysis.json`) | `slurm_peak_rss_GiB`, `reported_store_GiB` | **D, X** | 131.25 GiB is write traffic (600 × 16 chunks × 14 MiB), **not** retained occupancy. Use only to explain the distinction; K02 is the occupancy claim. |

## Tenant identity (job 959878; runs `gpu-tenants-run1`, `gpu-tenants-run3`)

| ID | Claim | Value | Evidence | Field | Level | Boundary |
|---|---|---|---|---|---|---|
| K09 | Explicit LMCache tenant tags separate identical prompts across tenants | 16 first requests missed; 16 repeats retrieved 768 tokens; identical in two fresh model processes | `gpu-tenants-first-summary.json`, `gpu-tenants-repeat-summary.json` (`results/gpu-tenants-run{1,3}/analysis.json`) | `groups[]`, `tagged_isolation_and_reuse_pass` | **R** (both runs) | Sequential (concurrency 1), 906-token prompts, 2 GiB tier. Connector/version-specific. Not a security guarantee. |
| K10 | `cache_salt` alone did not separate external entries on this connector | 1 miss, then 15 cross-identity hits, in both runs | same | `cache_salt_alone_separates_external_cache` = false | **R** (both runs) | Installed LMCacheConnectorV1 (LMCache 0.4.4) only. The CPU MP connector propagated salt correctly. |
| K11 | Per-tenant retained bytes are measurable | 16 tenants × 42 MiB = 672 MiB tagged, plus one 42 MiB untagged group | `results/gpu-tenants-run3/occupancy.json` (raw archive; not in pack) | `occupancy[].workers[][].tenants` | **D+, X** (same totals after both tagged rounds; no analyzer exists for this file) | 42 MiB = 3 chunks × 14 MiB = 768 tokens × 56 KiB. Diagnostic instrumentation, not a management API. |

## Manual primary-L1 quota (job 959878; run `gpu-primary-quota-run1`)

| ID | Claim | Value | Evidence | Field | Level | Boundary |
|---|---|---|---|---|---|---|
| K12 | One tenant's retained bytes were lowered and raised during live inference | A: 42 MiB → 0 → 126 MiB; B/C/D at 42 MiB in all 134 samples | `gpu-primary-quota-analysis.json` (`.../analysis.json`); `gpu-primary-quota-timeline.json` (`.../quota-state.json`) | `before_bytes`, `after_bytes`, `peer_occupancy_stable`; timeline `samples` | **R, X** | Custom bounded hook (30 s lifetime, 100 ms cadence). Two scheduled manual changes. Not stock LMCache quotas, not adaptive. |
| K13 | The lowered quota took effect for requests | 15 of 15 A requests wholly inside the settled low-quota interval missed | `gpu-primary-quota-analysis.json` | `low_quota_A_requests`, `low_quota_A_lookup_misses` | **R** | Settled = batch started > 0.2 s after the change. |
| K14 | Enforcement held occupancy at zero while lowered | 60 of 60 samples in the lowered interval were zero | timeline | `samples`, `events` | **R** | The first zero sample is 0.3 ms after `applied_at` because the enforcer samples right after applying. **Do not quote 0.3 ms as a latency.** Resolution is the 100 ms cadence. |
| K15 | Only the targeted tenant was evicted; changes overlapped inference | 51 evicted chunks, all A; both changes overlapped a batch; 0 thread errors | analysis; timeline | `evicted_chunks`, `event_overlap_with_inference_batch`, `errors` | **R** | Batches of 4, offline engine. Not concurrent HTTP serving. |
| K16 | The workload completed with real external retrievals | 184 requests; 161 actual 768-token retrievals; outputs consistent per input | analysis | `requests`, `actual_768_token_retrieves`, `output_consistency_by_input` | **R** | Output consistency is not a quality claim. |

## Analysis replay

| ID | Claim | Value | Evidence | Level | Boundary |
|---|---|---|---|---|---|
| K17 | Saved analyses are reproducible from the raw logs, and the cleaned analyzers fail when retrieval logs are removed | Preservation replay matched for 4 runs (`cpu-project2-981115`, `gpu-tenants-run3`, `gpu-primary-quota-run1`, `gpu-scale-976316`). Nov 13 cleanup replay: 3 GPU runs matched, 2 negative checks | `original-analysis-replay.json`; `docs/VALIDATION.md`; C's Nov 19 replay (§ Raw log archive) | GPU runs: **R**, repeated by C including both negative checks. CPU run 981115: **D** | Saved-log replay, not deployment. The cleaned launcher has **no fresh GPU run** (E01 pending). |

## Context only: CPU-only alternative (job 981115)

H05 in the workbook. CPU-only is deferred (D06) and outside the selected plan. If mentioned, it is one line: 68 streaming HTTP requests across 4/8/16 identities at client concurrency 4 with real L1/L2 reuse (`cpu-7b-http-analysis.json`). Never place CPU FP32 and GPU BF16 timings side by side as a hardware comparison.

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

Source: course Phase 2 assignment page (copy provided Nov 18; kept out of Git).

- **Deadline:** draft slide PDF by 11:59 pm Nov 21, one submission per group. Timezone is not stated on the page (D02 still open on that point).
- **Duration:** 15 minutes total per presentation (team update, Nov 19). Still to confirm: whether that includes Q&A. If it does, plan for about 10–12 minutes of talk, which gives the evidence section about 3–4 minutes: the three C02 figures plus one setup and limitations slide. The presentation timeline link is TBD.
- **Rubric (40 points):** problem, motivation and RQs 5; technical challenges (2–4) 4; technical ideas and system design 9; implementation and methodology 5; **experimental results 7; analysis and insights 5**; slide quality and timing 3; Q&A 2. Presenter split is not graded, but all members attend and answer questions.

Requirements that bear on the evidence section:

- Each experiment must name the RQ it answers, the main observation, why it occurs and what it teaches. "Faster/better" alone is insufficient.
- Separate **observations** (measured) from **insights** (what they teach). This list's rows are the observations.
- Negative and unexpected results are explicitly valued. Candidates: K10 (`cache_salt` does not isolate on this connector), K06 (allocator-full warnings at capacity), K08 (store traffic ≠ retained bytes), and the finding that stock LMCache quotas govern L2 and do not evict primary L1 copies.
- Implementation must state **changes from the Phase 1 proposal**: two applications / 16 GiB → 4/8/16 tenants with a small pilot budget; stock quota API insufficient → custom tenant-aware retention hook (the proposal's own §3.5 fallback).
- Figures need labeled axes, units, legends and a stated takeaway.

**Gap against the rubric:** the assignment expects "meaningful preliminary or final experimental results" that answer the RQs. The proposal's RQs (do dynamic quotas beat shared or fixed caches?) cannot be answered by the Nov 10 evidence, which has no latency data and no policy comparison. Unless pilot E04 runs by the Nov 20 noon freeze, the results section must either frame Phase 2 RQs that the evidence does answer (mechanism feasibility and cost) or present B04's offline policy replay, clearly labeled as synthetic. Team decision needed at kickoff.
