# FairCache reproduction and proposed extension

November 23, 2026. Selected research target: **FairCache: Demystifying Cache-Induced Unfairness in Multi-Tenant Large Language Model Serving**, IEEE TPDS 37(11), 2390–2406, published September 2, 2026. DOI: 10.1109/TPDS.2026.3729988.

Sources:
- https://ieeexplore.ieee.org/abstract/document/11676094/
- https://github.com/icloud-ecnu/FairCache
- Author repository inspected at commit `4fa5650273e439237b163aaa0d4aa852dcd4463e`, branch `initial-code`.

## Status and scope

Selected for reproduction; NOT yet reproduced, installed or benchmarked. Existing equal-share and adaptive experiments remain separate prior work. None of their results establish improvement over FairCache. Full-text paper review remains necessary: publisher abstract, repository README/tree and portions of the eviction implementation were inspected, not the complete algorithm/proofs/evaluation.

The author artifact includes modified vLLM 0.6.2, LMCache and the connector. Keep it in an isolated environment rather than replacing the working experimental stack. Pin dependencies and record actual hardware/model compatibility. A cache-only port must be labeled an adaptation of a component, not a full FairCache reproduction.

FairCache already includes compute/memory/I/O cost accounting, attribution of shared-prefix costs, and fairness/reuse-aware cache management. Therefore “add fairness,” “add reuse,” or “make it cost-aware” is not a defensible novelty claim. Its theoretical guarantees cannot automatically be transferred to a modified implementation.

## Candidate changes and selection

| Candidate | Hypothesis | Main risk | Priority |
|---|---|---|---|
| Eviction/refill-cost gate | A small predicted reuse advantage may not justify evicting and rebuilding useful state | Poor cost estimates; may already be covered by paper | Primary candidate after full-paper overlap check |
| Workload-adaptive reuse decay | Observed interarrival times may rank prefixes better than fixed workload-class decay values | Cold-start noise, metadata overhead, overlap with existing model | Alternative if primary overlaps or is impractical |
| Short residence protection | Briefly retain newly restored prefixes to prevent immediate re-eviction | Can pin low-value data and worsen capacity/fairness | Optional diagnostic ablation, not first implementation |
| Feedback-driven thresholds | Adjust control thresholds to detected churn or unstable demand | Extra control-loop instability and selection bias | Later work |

Code inspection found `FairEvictor` using a decay-based value model, a low-value threshold, and client-usage-aware eviction. The exact scheduling/cost integration and fairness constraints still require end-to-end audit. This observation is not a finding that FairCache is defective.

## Small proposed extension: eviction/refill-cost-aware decisions

Question: under changing multi-tenant demand, can explicitly accounting for the cost of replacing retained KV reduce repeat misses and latency while preserving the baseline's required fairness behavior?

Conceptual decision score over a fixed horizon H:

    estimated gain = expected time saved by retaining incoming KV
                     - expected time lost from evicting victim KV
                     - additional transfer/control cost caused by this action

Use seconds throughout; avoid mixing byte counts and time. Estimate hit-versus-miss cost from calibrated matched measurements, conditioned on prefix length and load where feasible. Do not count the same transfer cost twice. Admit or replace only when the gain exceeds a fixed safety margin, subject to capacity and the baseline fairness rules.

This is a hypothesis, not validated pseudocode. FairCache's full algorithm may already cover some or all of these terms. If so, pivot to an explicitly different estimator or threshold adaptation rather than claiming the same idea as new.

Forced capacity or fairness reclamation must remain possible: a gain gate must not indefinitely prevent a tenant from receiving its entitlement. Restrict the first extension to discretionary eviction/admission choices among permitted alternatives, or document and re-evaluate any changed fairness behavior. Handle pinned/in-flight entries, incomplete prefixes and mandatory admission failures explicitly. Do not create unsafe cross-tenant prefix sharing in our isolated namespace setup to mimic the paper.

## Reproduction gates

1. Obtain/read full paper, especially algorithm, fairness assumptions, workload generation and evaluation. Record a paper-to-code map and check novelty overlap.
2. Pin author artifact and build a separate environment. Inspect license and retain attribution. Audit experiment scripts and exact fairness metrics before launch.
3. Run original FairCache unmodified on a small smoke workload; verify output correctness, accounting, tenant attribution and bounded memory.
4. Reproduce one paper experiment/trend as closely as resources allow, documenting every deviation. Success means reproducible behavior, not matching an absolute published latency on different hardware.
5. Freeze the baseline; add one extension behind a disabled-by-default option. Separate compatibility fixes from algorithm changes and apply necessary fixes equally to baseline and extension.

If the full system cannot run in the available time, report a clearly labeled cache-policy component study or keep FairCache as related work. Do not relabel our existing cautious controller as FairCache.

## Controlled evaluation

Main methods: author FairCache, FairCache plus the single extension, and equal fixed shares as a simple reference where the same harness permits a fair comparison. Retain the prior cautious controller as historical context rather than expanding the main matrix automatically.

Use identical model, hardware, precision, tokenization, requests, seeds and cache capacity across methods. Fix shared-prefix semantics, scheduler settings, arrival order and cold/warm reset policy. If comparing separate engine versions, disclose the confound; prefer baseline and extension on the same artifact version.

Initial workloads: stable repeated prefixes (no-regression control), persistent demand shift, brief burst/rapid reversals, and scan pollution. Include both tenant-private data and explicitly permitted common prefixes if reproducing the paper's shared-cost mechanism. Our current isolated synthetic workload alone cannot exercise every FairCache feature.

Start with the paper's documented workload if available. Add a versioned real-text workload only after recording source, license, split, IDs, preprocessing and tenant mapping. No new public dataset has been selected or measured yet.

Freeze three held-out seeds and primary endpoints before testing. Compare paired seed results and show every tenant. A starting matrix of two methods × three workloads × three seeds is 18 runs; at 20 minutes each this is six hours of measurement plus setup and calibration. Add the equal baseline only with a budgeted, matched design. Do not launch the matrix until baseline validation passes.

Report all methods' median/p95 TTFT, reuse, completed requests/errors, per-tenant latency, the paper's own fairness metric, actual occupancy, evicted bytes, repeat misses/refill time and controller CPU overhead. Define p95 consistently. Report output agreement versus cache-off reference; add answer-quality metrics only for labeled QA. Lower latency with tenant starvation is not success.

Ablations: baseline; cost estimate without decision gate where meaningful; full gated policy. Separate additional residence/decay changes into later experiments so effects remain attributable. Test zero reuse, cold start, idle tenant return, insufficient samples, pinned victims, estimator error and failed enforcement.

## Delivery and fallback

November 23–25: paper/code mapping, environment feasibility and unchanged baseline smoke; retain current honest Phase 2 slides, and describe this as Phase 3 planned work.
November 26–28: one extension and paired tests only if reproduction succeeds.
November 29: evidence freeze; retain negative or inconclusive findings.
November 30–December 4: integrate into six-page report and review.
December 5: final group submission before 11:59 p.m.

Proposed roles: Pradeep environment/integration/cost instrumentation; Akshith algorithm mapping and extension; Jauwaad baseline/result validation and matched plots. Confirm actual commitments and use the existing review rotation. No outcome, novelty, performance gain or preserved theorem is guaranteed.
