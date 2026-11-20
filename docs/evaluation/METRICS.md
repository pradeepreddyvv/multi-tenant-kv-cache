# Metric definitions (task C01)

Owner: C. Reviewer: A, with B for the interface section. Prepared November 18, 2026.

These definitions extend workbook steps W13 (interface v1), W14 (seeds), W16 (harm) and W17/W18 (metrics, tails). Where this file and the workbook disagree, raise it at kickoff rather than silently picking one. Every analysis script that reports a metric below must use this name and definition.

## Units and constants

| Quantity | Definition | Source |
|---|---|---|
| GiB / MiB | 2^30 / 2^20 bytes | Report convention |
| KV bytes per token | 2 (K,V) × 28 layers × 4 KV heads × 128 head dim × 2 bytes (BF16) = **56 KiB** | Qwen2.5-7B config; proposal §3.6 |
| Chunk | 256 tokens = **14 MiB** of KV | `docs/ENVIRONMENT.md` (chunk size 256) |
| Eligible (cacheable) tokens | `floor(prompt_tokens / 256) × 256`: only full chunks are stored on this stack | Observed: 906 → 768, 1,006 → 768, 4,096 → 4,096 retrieved |

The eligible-token rule is an observation for LMCache 0.4.4 with the tested configuration. Re-check it if the LMCache version, chunk size or partial-chunk setting changes.

## Request-level metrics

| Metric | Definition | Notes |
|---|---|---|
| `ttft_s` | Request submission → first output token received by the client, including queue and network time | W17. Requires streaming HTTP (E03+). **Not available in any historical GPU run.** |
| `completion_s` | Submission → final response | W17 |
| `tpot_s` | `(completion_s − ttft_s) / (output_tokens − 1)` when `output_tokens > 1` | W17. Exclude TPOT for single-token outputs. Keep the request in all other metrics. |
| `prompt_tokens`, `output_tokens` | From the engine's usage record | |
| `eligible_tokens` | See Units | |
| `lookup_hit_tokens` | LMCache lookup log line matched by request ID (`LMCache hit tokens: N`) | Existing analyzers' regex |
| `retrieved_tokens` | LMCache `Retrieved N out of` log line matched by request ID | Existing analyzers' regex |
| `cache_outcome` | **hit**: retrieval log matched with N > 0. **miss**: lookup log matched with 0 hits and no retrieval. **unattributed**: no matching log line, or lookup hit without retrieval | Missing evidence is never a hit (C03 acceptance). |
| `recomputed_prefill_tokens` | `prompt_tokens − retrieved_tokens` | Proposal's "repeated prefill work" |
| `failed` | Error response, timeout, missing usage record or empty text | Report beside every latency number (W18) |

**Parsing rule:** parse `Inference Engine computed tokens` as a field and flag non-zero values. Never use it as a match condition; the historical analyzers' regex does, and would silently drop lines when native prefix caching is on (see `METRIC_CHECKS.md`). `scripts/check_request_attribution.py` implements this classification.

**Validity rule (proposed):** a run with any `unattributed` request is marked Metric validity = "Needs review", not Valid, until the reviewer explains it (W12). Unattributed requests stay in denominators and count as non-hits.

## Tenant-level metrics (per tenant, per window or per run)

| Metric | Definition |
|---|---|
| `hit_rate` | hits / completed requests. State the denominator. |
| `reuse_fraction` | Σ `retrieved_tokens` / Σ `eligible_tokens` |
| `retained_bytes` | Sum of `tensor_bytes` of live cache objects for the tenant tag, from a locked snapshot. `physical_bytes` is reported separately. |
| `retained_GiB` | `retained_bytes / 2^30` (W17) |
| `quota_bytes` | Effective quota from the adapter's accepted update, not the requested value |
| `evicted_chunks` | Count by reason: `quota` (enforcer) vs `capacity` (allocator full). The two must not be merged. |
| `median_ttft_s`, `p95_ttft_s` | p95 only with ≥ 100 completed requests for that tenant and condition. Otherwise leave it blank and say "insufficient samples" (W18). |

## Run-level metrics

| Metric | Definition |
|---|---|
| `throughput_rps` | Completed requests / measured-window seconds. The measured window excludes warm-up; record the boundary (W14). |
| `failure_rate` | Failed / submitted |
| `cgroup_highwater_GiB`, `memory_failcnt` | Job cgroup `memory.max_usage_in_bytes` / 2^30 and `memory.failcnt` (cgroup v1 only; other layouts need a validated adapter) |
| `allocator_full_warnings` | Count of LMCache "no memory is available" messages. Always reported. |
| `quota_updates` | Accepted / deferred / error counts from adapter `apply_quotas` results |
| `enforcement_delay_s` | `applied_at_s` → first snapshot with `retained_bytes ≤ quota_bytes`. Resolution equals the snapshot cadence; report the cadence with it. |
| `controller_cpu_s` | CPU time of the policy and enforcement threads over the measured window |

## Comparison metrics

| Metric | Definition |
|---|---|
| `harm_ratio` | max over tenants of `median_ttft(policy) / median_ttft(equal)`, same trace and seed (W16). The acceptable threshold must be fixed before tuning. |
| Paired difference | Per seed, `metric(policy) − metric(equal)`. Use run summaries as the unit, never individual requests (W18). |

**Aggregation:** report all three per-seed run values plus their spread for each policy × tenant count. Pilot seeds 11/22/33; held-out main seeds 101/202/303, paired across policies with policy order randomized within a block (W14). Three repetitions is a minimum, not a power analysis.

## Availability from historical evidence

| Metric | Available from Nov 10 GPU runs? |
|---|---|
| `retained_bytes` per tenant, `evicted_chunks` (quota), `cache_outcome`, `retrieved_tokens` | Yes (tenant, quota and scale runs) |
| `cgroup_highwater_GiB`, `allocator_full_warnings` | Scale run only |
| Per-request wall time | Tenant probe `seconds` (sequential offline call); quota run batch start/finish only |
| `ttft_s`, `tpot_s`, goodput, `harm_ratio`, `controller_cpu_s` | **No.** Needs E03+ streaming harness and a controller |

So the Phase 2 evidence slides can show bytes, retention and hit/miss behavior, but no latency results.

## Interface v1 gaps (W13, for kickoff with B)

W13 observation fields: `tenant_id, window_end_s, eligible_input_tokens, retained_bytes, retrieved_tokens, errors`. Against the metrics above:

1. **No window start or length.** The policy cannot convert counts into rates, and stale or missing windows (B07) cannot be detected. Proposed: add `window_start_s`.
2. **No request count.** Hit rate and per-request demand cannot be computed. Proposed: add `requests` and `hits`.
3. **No eviction counts.** The proposal's controller (§3.5) watches evictions, and E06 acceptance requires them. Proposed: add `evicted_bytes_quota` and `evicted_bytes_capacity`.
4. **`eligible_input_tokens` is undefined.** Proposed: the chunk-aligned rule in Units, summed over requests in the window.
5. **`errors` type unspecified.** Proposed: integer count of failed requests in the window.

These are proposals only. Until agreed, B's fixtures and C's analysis use the six W13 fields unchanged.
