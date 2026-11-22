# Controlled evaluation specification (task C04)

Owner: C. Reviewer: A; B reviews the interface and policy sections. Prepared November 19, 2026.

> **Status: PLANNED.** Nothing in this document has been measured. It specifies the HTTP evaluation that runs after integration (A07) and registry freeze (C07). Numbers below are design parameters or arithmetic, never results. Measured evidence lives only in `CLAIMS.md` (PR03).

Builds on `docs/team/METRICS_AND_EXPERIMENTS.md` and `PROJECT_AND_DESIGN.md` (branch `docs/team-handoff`), workbook steps W10–W18, and `docs/evaluation/METRICS.md` (PR03) for metric definitions.

## 1. Questions and experiments

Draft RQs from `PROJECT_AND_DESIGN.md`. The team still has to finalize them at kickoff.

| RQ | Question | Experiments | Main metrics |
|---|---|---|---|
| RQ1 | Under a fixed CPU-cache budget, how does allocation affect per-tenant reuse, TTFT and throughput under contention? | E05 (fit), E06 (pressure) | per-tenant median TTFT, hit rate, reuse fraction, throughput |
| RQ2 | After demand changes, does a feedback policy improve the objective over fixed equal allocation? | E07 (shift) | harm ratio, per-tenant TTFT by phase, recovery time |
| RQ3 | What overhead and regressions does adaptation cause? | E07, E08 (ablations) | quota updates, evictions by reason, oscillation, controller CPU, quiet-tenant harm |
| Control | What does external retention add over the engine's own prefix cache? | E10 | TTFT and total memory, with cache sizes disclosed |

E04 is a 4-tenant pilot of the full trace and calibrates the rate, budget and run length below. E03 validates streaming attribution before any comparison.

## 2. Serving setup (held fixed within a comparison)

| Item | Setting |
|---|---|
| Model | Qwen2.5-7B-Instruct, revision `a09a3545…`, BF16 (`docs/ENVIRONMENT.md`) |
| Engine | vLLM OpenAI-compatible HTTP server with the LMCache connector; frozen image hash and versions recorded |
| Native prefix cache | **Off** (on only in E10) |
| Active GPU KV | Fixed `gpu_memory_utilization` and `max_num_seqs`, recorded; identical across policies |
| External cache | LMCache CPU tier with capacity ≥ budget B; per-tenant quotas enforced by A's adapter (interface v1) |
| Identity | `lmcache.tag.tenant` on every request. `cache_salt` alone did not isolate tenants on the tested connector (K10). |
| Hardware | One A100 80 GiB node class, job RAM allocation recorded. All runs in a comparison use the same class. |

## 3. Workload

### 3.1 Requests

- **Endpoint:** `/v1/completions` with `stream: true`, so the client observes the first token.
- **Prompt:** token IDs (`prompt` as an integer list), so lengths are exact and chunk-aligned. Prompt = tenant prefix (4,096 tokens = 16 chunks) + a request-unique suffix (64 tokens). Eligible tokens = 4,096 per request; a full hit retrieves 4,096.
- **Prefix content:** token IDs drawn from the seeded generator in [100, 20000) (as in `gpu_scale.py`), unique per (tenant, prefix), so no prefix is shared across tenants.
- **Output:** `max_tokens: 32`, `temperature: 0`, `ignore_eos: true` (vLLM extension), giving fixed output lengths so TPOT and completion times are comparable.
- **Prefix KV size:** 4,096 × 56 KiB = **224 MiB** per prefix.

### 3.2 Tenants, pools and budget

Each tenant draws uniformly from its own pool of P = 4 prefixes, so its working set is 4 × 224 MiB = 896 MiB. The budget is set by a pressure ratio ρ = aggregate working set / budget:

| Tenants N | Aggregate working set | Fit budget (ρ = 0.5) | Pressure budget (ρ = 2) |
|---|---:|---:|---:|
| 4 | 3.5 GiB | 7 GiB | 1.75 GiB |
| 8 | 7 GiB | 14 GiB | 3.5 GiB |
| 16 | 14 GiB | 28 GiB | 7 GiB |

The budget is **frozen across policies** for a given N and condition (E05/E06 acceptance). The pilot may shorten the prefix length or pool size to fit the run time. It then changes these tables, not the ratios.

### 3.3 Demand and arrivals

- **Open-loop Poisson** arrivals per tenant, so queueing shows up in TTFT. A closed loop would hide overload.
- **Skew:** one hot tenant gets 50% of requests; the other N − 1 share the rest equally. Without heterogeneity there is nothing for allocation to change.
- **Total rate λ:** set from the E04 pilot at ≤ 70% of measured saturation throughput, then frozen. Recorded as a target; the realized rate must be within ±5% (validity gate).
- **Shift (E07 only):** at the phase boundary the hot role moves to a previously quiet tenant. Fixed-unequal weights use **initial** demand only, so they are deliberately stale after the shift.

### 3.4 Timeline (15-minute run; E05–E07 Minutes/run)

| Interval | Purpose | Counted in metrics? |
|---|---|---|
| 0–3 min | Warm-up from an empty external cache; populates working sets | No (recorded; occupancy snapshot at the boundary) |
| 3–9 min | Phase 1 | Yes |
| 9–15 min | Phase 2 (E07: after the shift; E05/E06: same demand) | Yes |

Requests are counted by **submission time** within the measured window [3, 15) min. A request submitted in the window but finishing after 15 min is still counted; the client drains it, with a 120 s timeout recorded as a failure.

### 3.5 Sample counts and tails

W18: p95 only with ≥ 100 completed requests per tenant per condition. Expected counts over the 12-minute measured window (arithmetic, not measurement):

| λ (req/s) | N | Hot tenant | Each quiet tenant |
|---:|---:|---:|---:|
| 2 | 4 / 8 / 16 | 720 | 240 / 103 / 48 |
| 4 | 4 / 8 / 16 | 1,440 | 480 / 206 / 96 |

At N = 16, quiet-tenant p95 needs λ ≥ about 4.2 req/s. If the pilot shows the server cannot sustain that, the plan reports **median only** for quiet tenants at N = 16, rather than lengthening runs silently. Per-phase p95 (6 minutes) halves these counts again.

## 4. Seeds, ordering and cache state (W14)

- **Seeds:** pilot 11/22/33; main 101/202/303 (held out from tuning). The seed fixes prefix tokens, suffixes, prefix choice and arrival times.
- **Trace files:** each (seed, N, condition) trace is generated once, hashed (SHA-256), and replayed identically under every policy. The manifest records the hash.
- **Pairing:** every policy runs every seed. Comparisons use per-seed run summaries, never individual requests as trials (W18).
- **Order:** policy order is shuffled within each (seed, N) block using that block's seed, and recorded, so time-of-day or node drift is not confounded with policy.
- **Cache state:** each run starts a **fresh server process** with an empty external cache. No cache carries over between runs. Model weights may stay in the page cache; the manifest records whether the model was already cached on that node.

## 5. Policies and fairness controls

| Policy | Definition | Owner |
|---|---|---|
| Equal | B / N per tenant | B |
| Fixed unequal | Proportional to declared initial demand, with the same floor as adaptive | B |
| Adaptive | W15 candidate (20% floor, smoothed demand, 5 s window, capped transfer, hysteresis), frozen after E08 | B |
| Shared (proposed) | One cache, no per-tenant quotas (proposal's B0). **Kickoff decision**, see `CLAIMS.md` inconsistency 1 | B / all |
| Native-only (E10) | Native prefix cache on, external off; total memory disclosed | C |

Controls that make a comparison fair:

1. Same trace hash, model revision, image hash, node class, `max_num_seqs` and active GPU KV across policies.
2. Σ effective quotas ≤ B in every window (checked from adapter updates, not requested values).
3. Same warm-up length and fresh-process reset for every policy.
4. Any allocation using future knowledge is labelled **oracle**, never a baseline.
5. The acceptable harm threshold (W16) is fixed **before** tuning, on pilot seeds only.
6. All runs are kept, including failed and aborted ones, with predeclared exclusion reasons.

## 6. Per-tenant outputs

Definitions are in `METRICS.md`. For each tenant × policy × seed × phase:

- **Latency:** completed and failed counts; median TTFT and completion; p95 TTFT when n ≥ 100; median TPOT.
- **Cache:** hits, misses, unattributed (must be 0 for Valid); reuse fraction; retained bytes over time; evicted chunks by reason (quota vs capacity).
- **Allocation:** effective quota over time, from accepted adapter updates.
- **Comparisons against equal, same seed:** harm ratio (max over tenants of median-TTFT ratio); paired differences.
- **Run level:** throughput (completed / measured seconds), failure rate, realized λ, quota updates (accepted/deferred/error), controller CPU seconds, cgroup high-water (observed, not a requirement), allocator warnings.

## 7. Records each run must produce

Interface v1 (W13) is used unchanged; the proposed additions in `METRICS.md` are optional fields until agreed.

| File | Contents |
|---|---|
| `manifest.json` | W10 provenance plus `policy`, `seed`, `trace_sha256`, `tenants`, `budget_bytes`, `warmup_end_s`, `measured_end_s`, `shift_at_s` (or null), target λ, policy order position |
| `requests.jsonl` | `request_id`, `tenant`, `submitted_at_s`, `first_token_at_s`, `finished_at_s`, `prompt_tokens`, `output_tokens`, `status` (`ok`/`error`/`timeout`) |
| `observations.jsonl` | Interface v1 per tenant per window: `tenant_id`, `window_end_s`, `eligible_input_tokens`, `retained_bytes`, `retrieved_tokens`, `errors` (integers; seconds as numbers) |
| `quota_updates.jsonl` | `update_id`, `applied_at_s`, `status`, `quotas` (tenant → bytes) |
| `run.log` | Engine log with LMCache lookup/retrieval lines for attribution |
| Occupancy snapshots | Independent of the enforcer (see `METRICS.md`, `enforcement_delay_s`) |

All times are seconds from one clock (client monotonic, with the server offset recorded).

## 8. Validity gates (before Metric validity = Valid)

1. Attribution: 0 unattributed requests (`scripts/check_request_attribution.py`, PR03).
2. Σ effective quotas ≤ budget in every window; no adapter error left unexplained.
3. Realized total rate within ±5% of the target.
4. Interface v1 records parse with integer fields.
5. No OOM; failures and timeouts reported beside every latency number.
6. The warm-up boundary and trace hash are recorded.
7. A second teammate reproduces one summary (W12).

## 9. Analysis path tested now

`scripts/summarize_evaluation_run.py` computes sections 6 and 8's checks from the files in section 7. It is tested **only against synthetic fixtures** (`tests/test_summarize_evaluation_run.py`). Its output on fixtures is a software check, not a result. Not yet covered: attribution (handled by the PR03 checker) and occupancy-snapshot analysis (needs A's adapter output format).

## 10. Open items for kickoff

1. Finalize RQs and the harm threshold (B, all).
2. Keep or drop the shared-cache baseline (B, D05).
3. Agree interface v1 additions (`window_start_s`, `requests`, `hits`, eviction bytes).
4. Confirm the HTTP server and adapter can expose `first_token_at_s` and accepted quotas (A, E03).
5. Compute budget: E05–E07 = 81 runs × 15 min = 20.25 measured GPU-hours before queue, startup and reruns (W19).
