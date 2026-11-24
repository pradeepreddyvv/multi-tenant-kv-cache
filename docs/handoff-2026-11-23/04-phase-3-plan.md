# Phase 3: prioritized execution plan

## Research story and questions

**Story:** changing cache shares is not free. A controller can follow demand yet discard reusable state faster than it refills. Slower, reuse-aware allocation with stronger minimum shares may improve the tradeoff, but must be evaluated against equal and unpartitioned sharing with per-tenant as well as aggregate metrics.

RQ1: Can GPU inference with a large CPU KV cache support useful tenant-aware control?
RQ2: Why did the original adaptive controller lose to equal shares?
RQ3: Does cautious adaptation improve latency without unacceptable tail/tenant harm?
RQ4: How do reuse, demand duration, cache pressure and tenant count affect that tradeoff?

Do not promise a new state-of-the-art algorithm or that adaptive must win. A well-supported negative result satisfies the assignment's explicit emphasis on analysis.

## Priority 0: recover and freeze existing evidence, November 23–24

Pradeep: recover final status/logs/results for jobs 2202045 and 2221040; distinguish complete, invalid, failed and interrupted runs. Record the actual source hash and configuration per run. Do not rerun successful matched cases simply because status was previously unknown.

Jauwaad: audit manifests, request counts, errors, trace hashes, analysis validity and artifact checksums; construct one run inventory. Preserve raw evidence and original analysis, then add consistently recomputed analysis separately.

Akshith: document actual algorithm equations/rounding/caps; check that candidates really implement the intended controls; identify offline-only versus live features.

Exit criteria: every report result maps to a run ID, source/configuration, raw evidence and analysis command; unrecovered results are explicitly excluded. Recover exact hardware/software versions, job placement and run order.

## Priority 1: controlled confirmation, November 24–28

Run only if valid existing data do not answer the question and allocation time allows:

| Experiment | Minimal proposed design | Purpose |
|---|---|---|
| Candidate replication | Equal, cautious adaptive and shared; three held-out seeds, same four-tenant demand-shift workload | Test whether single-seed benefit repeats; keep fixed as a conditional-priority reference |
| Mechanism ablations | Original plus separately slower cadence, stronger floor, repeat signal and prior; matched seeds | Isolate effects currently confounded in V3 |
| Live scaling | Audit the existing 8/16-tenant suite before requesting more | Distinguish actual scaling from offline arithmetic |
| Scan/burst | Audit already scheduled results; replicate only the most informative comparison | Test pollution and short demand spikes |

Nine 20-minute full runs need at least three hours of measurement, plus startup/validation and buffer. A one-baseline-plus-four-ablation design across three seeds needs 15 runs (five measurement hours); do not commit to all ablations before checking available time. Prefer a complete matched comparison over many partial runs.

Freeze primary endpoints before new runs: post-shift median TTFT and p95, plus per-tenant median changes, error rate and reuse. Present the tradeoff/Pareto comparison rather than select a winner from aggregate latency alone. If using a numerical acceptable-harm threshold, agree and record it before observing new results; no threshold is currently agreed.

Counterbalance policy order, use fresh cache/process state consistently, record first-touch/warm-up behavior, and retain the same trace per seed across policies. Do not report highly unstable small-sample per-tenant p95 as reliable. Three seeds are limited replication, not a substitute for a broad production study.

## Priority 2: bounded sensitivity and practical failure cases, November 27–29

Choose at most two informative sensitivity axes after recovery, rather than an infeasible full Cartesian product:

- Cache pressure: working set fits, approximately 2× cache, and larger than cache; change one variable at a time.
- Demand dwell: shorter than the controller window versus sustained demand; measure adaptation lag.
- Reuse: repeated document prefixes versus mostly first-touch requests.
- Quota fairness: idle tenant returns, tenant disappears, all demand zero, one tenant dominates, minimum share holds under rounding.
- Enforcement and measurement: pinned entries, simultaneous writes, failed quota updates, interrupted streams, duplicate/missing request events, trace mismatch, controller restart.
- Scan/burst/churn: reusable tenants alongside one-use traffic; sudden arrivals; tenant population change.

Status of these is mixed: some are covered by offline tests/simulation, some by already queued suites, and some remain proposals. Check the exact test inventory before claiming completion. Failures should either produce a bounded diagnostic or be reported as a limitation; do not silently discard them from performance data.

A true cost-aware extension could estimate saved prefill time minus restore/eviction/refill costs and change allocations only when predicted gain exceeds switching cost. This is future design unless implemented and separately validated; do not insert an untested formula as the completed method.

## Metrics and analysis contract

- TTFT: client submission to first nonempty generated SSE output; report seconds/ms consistently.
- Reuse: retrieved tokens divided by chunk-eligible input tokens; state treatment of partial hits.
- Occupancy: independent samples of actual retained KV, separate from assigned quotas and process memory.
- Churn: evicted bytes, repeat misses, update count; summed quota changes are not network traffic.
- Fairness: show each tenant's change relative to equal; do not infer fairness from aggregate throughput.
- Errors and exclusions: report counts and reasons; keep invalid runs in inventory but outside valid summaries.
- p95: standardize one documented convention across all recomputed results. Preserve historical values separately.
- Statistics: compute per-seed paired effects, report each seed and variability; avoid pooling requests as if they were independent experimental replicates. Any interval method must state its unit and assumptions.
- Throughput: achieved completion rate at the offered load, not maximum serving capacity.
- No dollar-cost or answer-quality claims without measuring them.

## Report schedule and independent work

| Date | Pradeep | Akshith | Jauwaad | Integration checkpoint |
|---|---|---|---|---|
| Nov 23–24 | Recover jobs/environment; architecture | Policy specification, ablation design | Evidence inventory and plots | Freeze evidence schema and run IDs |
| Nov 25 | Present system/results | Present policy | Present evaluation | Collect professor feedback; 4 p.m. workshop |
| Nov 26–28 | Run prioritized missing comparisons | Analyze mechanisms and offline edge cases | Recompute consistent metrics/figures | Review matched results daily |
| Nov 29 | Freeze experiment scope | Finalize method text | Freeze figures/tables | Mark unfinished experiments as future work |
| Nov 30–Dec 2 | Introduction, system, limitations | Related work, algorithms, challenges | Evaluation, insights, report assembly | Complete first six-page draft |
| Dec 3 | Review Jauwaad section | Review Pradeep section | Review Akshith section | Resolve numerical/claim discrepancies |
| Dec 4 | Reproduction check | Algorithm/notation check | Render/layout/reference check | Submission-ready PDF |
| Dec 5 | Final team verification | Contributions confirmation | Submission coordination | Submit before 11:59 p.m.; retain receipt |

These are proposed assignments, not confirmed teammate commitments. Work independently through agreed manifest/CSV interfaces; final results and claims still require integration. No circular dependency is necessary: draft methods and report structure while evidence recovery runs.

## Rubric-to-report mapping

| Required criterion | Points | Our content and remaining action |
|---|---:|---|
| Problem, motivation, questions | 4 | Shared applications compete for retained prefixes; state RQ1–4 |
| Related work | 3 | Closest tiering/prefix-cache papers; separate adopted components from new policy integration |
| Technical challenges | 3 | Identity, asynchronous eviction/pins, signal delay, churn, reliable request attribution |
| Method/system design | 7 | Architecture, original/cautious policies, enforcement, execution alternatives |
| Implementation | 3 | Clearly label vLLM/LMCache/model reuse versus team controller/harness/analysis |
| Setup/data/baselines | 4 | Hardware/software manifests, synthetic trace generation, equal/fixed/shared, metric definitions |
| Evaluation | 6 | Replicated original loss, occupancy diagnosis, cautious tradeoff; add recovered suites only if valid |
| Analysis/insights | 5 | Observation versus explanation versus general lesson; workload-dependent outcomes |
| Conclusions/future work | 2 | Bounded findings, cost-aware extension and unresolved scaling |
| Writing/format | 2 | 11-point, six main-body pages, consistent units/figures/citations |
| Individual contributions | 1 | Concrete actual work per named team member |

Suggested six-page budget: introduction/questions 0.6; background 0.5; challenges/design/algorithm 1.3; methodology 0.8; results/analysis 2.0; conclusions/limitations/contributions 0.8. References can continue beyond the six-page main-body limit. Double-column conference style is recommended, not mandatory.

Recommended figures: (1) system architecture, (2) original paired TTFT and occupancy/churn diagnosis, (3) candidate median/tail/tenant tradeoff. Add scaling only if valid recovered results materially change the story. Use a compact setup table and algorithm pseudocode. Do not put every experiment in the six-page report.

## Final acceptance checklist

All figures trace to evidence; completed and proposed work are distinct; external resources cited; exact software versions documented; workshop feedback incorporated; no unexplained V3 jargon; no universal-winner/causality claim from one seed; actual member contributions confirmed; PDF visually reviewed at 11-point and ≤6 main-body pages; one group upload and receipt verified. If Sol recovery fails, complete the report with verified existing evidence and explicitly state the missing confirmation.
