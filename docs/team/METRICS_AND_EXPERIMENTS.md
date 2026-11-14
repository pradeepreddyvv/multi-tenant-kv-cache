# Metrics and next experiments

## Define metrics before collecting comparisons

| Metric | Definition / reporting rule | Why it matters |
|---|---|---|
| TTFT | Time from request submission to first output token; state whether queue/network time is included | User-visible initial delay; prefill reuse is expected to affect it |
| End-to-end latency | Submission to final response | First-token improvement can coexist with slow decoding |
| TPOT / inter-token latency | Define whether using per-token intervals or post-first-token elapsed time divided by remaining tokens; exclude single-token responses from the latter | Decode behavior and contention |
| Request throughput | Completed requests / measured wall time, with failures also reported | System capacity under the same arrival workload |
| Output throughput | Total generated output tokens / measured wall time | Do not mix input tokens into this denominator |
| External reuse | Retrieved KV tokens per request; define eligible-token or total-prompt denominator if converting to a rate | Timing alone cannot attribute reuse to LMCache |
| Occupied bytes | Actual live KV-object payload per tenant and total | Distinguishes real retention from configured capacity and cumulative writes |
| Eviction | Chunks/bytes removed, by tenant and reason | Reveals refill cost and interference |
| Enforcement delay | Quota-update time to observed compliant occupancy, with sampling interval stated | Soft quotas may lag and locked entries may defer eviction |
| Fairness / SLO | Choose a defined objective: e.g., per-tenant target-attainment rates or normalized slowdown against a documented reference | Aggregate throughput can hide starvation |
| Resource use | Job cgroup memory, process/GPU metrics and controller CPU/time overhead, clearly separated | Prevents attributing extra resources to algorithmic benefit |
| Reliability | Completed/failed/timed-out requests, OOMs and warnings | A faster run with silent failures is not a better result |

Report metrics per tenant as well as aggregate. Include median and tail latency when enough samples exist; p95 from a handful of requests is not a stable tail estimate. The existing GPU offline probes do not provide streaming TTFT. CPU timings must not be substituted as Option 1 results.

## Proposed experiment matrix

Hold model revision, precision, engine settings, hardware class and total memory budget fixed for a policy comparison. Reuse workload seeds/traces across policies and record arrival rate/concurrency separately from tenant count.

| Dimension | Initial choice | Expansion after correctness |
|---|---|---|
| Tenants | Four | Eight, sixteen |
| Cache budget | Small enough for fast, observable pressure | Populated 128 GiB with all mechanisms integrated |
| Workload | Repeated and unique prefixes, short fixed outputs | Prompt-length/reuse diversity |
| Demand | Steady interval, then switch busiest tenant | Different skew/shift rates |
| Working set | One condition fits; another exceeds the budget | Different pressure levels |
| Policies | Equal quotas, explicit fixed/manual unequal allocation, one adaptive policy | Sensitivity/ablation studies |
| Repetition | Multiple independent runs; three as an initial minimum for main cases | More runs if variability/uncertainty warrants |

Use an engine-native-prefix-cache control to show what external retention adds, with actual total-memory differences disclosed. An equal model configuration alone does not make two cache budgets equivalent. If a manual allocation uses future workload knowledge, label it an oracle/reference rather than a deployable baseline.

## Correctness gates before performance claims

1. Identities separate cache entries and reuse is attributed to the right tenant.
2. Occupied bytes are measured and total quota allocations stay within the budget.
3. Reducing A's quota changes real retention while peers remain accounted for.
4. In-flight/locked entries are not forcibly removed; deferred enforcement is measured.
5. Raising quota permits additional retained prefixes.
6. Requests continue and errors/warnings are included in output.
7. The controller stops cleanly and a fresh run starts from a documented cache state.

## Figures to produce

| Figure | Evidence available now? | Intended lesson |
|---|---|---|
| Retained GiB versus population requests | Yes, scale JSON | Real occupied capacity and its relation to host-RAM budget |
| Per-tenant occupancy around manual quota changes | Yes, quota timeline | Selective retention control, with peer stability |
| Tagged versus cache_salt first/repeat hits | Yes, tenant summaries | Correct identity propagation is connector-specific |
| Per-tenant TTFT/throughput across policies | No, new experiment needed | Benefit or harm under equal resources |
| Demand → quota → occupancy → latency around a traffic shift | No, new experiment needed | Responsiveness, lag, oscillation and tradeoffs |

Use the same evidence for plots and slide numbers. Explain each figure as question → observation → mechanism → limitation. Negative results count if the integration is correct and the experiment is controlled. Do not relabel a broken integration as a negative algorithm result.

## Run record template

For every new run save: Git commit/branch, model/image/software revisions, job ID/node/allocation, exact command and effective config, workload seed/trace, tenant count/concurrency/arrival schedule, cache capacities and state, policy parameters, raw per-request records, metrics/snapshots/logs, analyzer version/output, failures and cleanup status. Keep new raw outputs in ignored run directories or agreed storage; commit a reviewed summary with provenance when sharing results.
