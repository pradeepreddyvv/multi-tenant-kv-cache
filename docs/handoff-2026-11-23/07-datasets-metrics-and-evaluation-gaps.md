# Dataset, metric coverage and evaluation improvement plan

Updated November 23, 2026. The workshop feedback summary is useful guidance; the other groups' numbers and professor comments have not been independently checked against recordings. They are not our results. Our announced slot remains 12 minutes presentation plus 3 minutes Q&A.

## What data did we actually use?

The main live benchmark is a custom, reproducible synthetic token-ID workload, not a named public dataset. It is not a natural-language question-answering accuracy benchmark.

Verified source: `scripts/live_common.py` in the frozen candidate-run source, function `build_trace`; serving path in `scripts/live_adaptive.py`. Each tenant has a seeded pool of prefixes. Each prefix consists of 4,096 random token IDs drawn from integers 100 through 19,999, followed by a fresh random 64-token suffix per request. The input is passed directly as `prompt_token_ids`, rather than loading and tokenizing documents. The main configuration uses 64 prefixes per tenant, four tenants, 256 possible reusable prefixes in total. Generation uses temperature zero, 32 output tokens and ignore_eos=True.

Arrival gaps are sampled from an exponential distribution at aggregate rate 0.5 requests/s. The hot tenant has weight 3, other tenants weight 1: expected shares 50%, 16.7%, 16.7%, 16.7%. A is hot before 900 s; B after. Prefix variants are selected uniformly within each tenant's pool. Run length is 1,200 s, warm-up 600 s. Seeded traces and SHA-256 hashes permit identical replay across policies.

Original seeds: 11, 29 and 47; 621, 582 and 567 requests per policy respectively. Three policies give 5,310 request executions, but only three distinct seeded traces. The newer screen uses seed 601, 622 requests per policy across seven policies (4,354 executions of one trace). Do not call these thousands of independent datasets. These counts include warm-up. Newer measured windows contain 154 before-shift and 171 after-shift requests per policy.

The scan generator gives D a new prefix on each request; burst compresses an interval to increase arrival rate. Scheduled scan/burst results still require recovery. Separate offline allocation traces cover 4/8/16 tenants; a separate 1,560-case cache simulator covers six workload families. Neither is a labeled answer dataset or GPU latency benchmark.

Data flow: seeded generator → timestamp/request ID/tenant/prefix variant/token IDs → HTTP wrapper → vLLM/LMCache inference → streaming output and cache events → request-ID attribution and occupancy samples → phase/tenant analysis. There is no vector database, retriever, gold answer or retrieval relevance label in this experiment.

## What does accuracy mean here?

Answer accuracy, exact match, F1, AUROC and retrieval Recall@K were not measured, and the synthetic inputs do not define meaningful ground-truth answers. Mark answer accuracy as “not evaluated,” not zero and not 100%. A zero request-error rate establishes transport/execution success, not answer correctness. Retrieved-token reuse is cache effectiveness, not semantic accuracy or document retrieval hit rate.

The primary systems endpoints are TTFT, reuse, per-tenant latency, eviction/refill behavior and occupied memory. Prefix caching saves repeated prefill computation; it does not by itself eliminate decode work. Official background: https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/ . Our external-cache integration still needs its own correctness validation.

## Metric coverage contract

The new `evidence/live-all-policy-metrics.csv` exports every saved phase/tenant metric for all seven policies: request/valid counts, median TTFT, p95 TTFT where available, reuse fraction, achieved completion rate, offered rate, mean completion latency and maximum dispatch lag. It includes run error counts and validity. Blank p95 cells are unavailable measurements, not zeros. The analyzer suppresses small-group p95; do not invent them.

| Metric | Current evidence | Next action |
|---|---|---|
| Median TTFT and reuse | All seven policies, both phases and each tenant | Present all selected methods with identical phase definitions |
| Aggregate p95 TTFT | All seven policies, current lower-order convention | Standardize quantile convention and preserve original results |
| Per-tenant p95 | Mostly withheld for small sample counts | Collect enough observations or report unavailable |
| Completion rate/latency, errors, dispatch lag | Saved for all seven | Add complete companion table; offered load is not saturation capacity |
| Occupancy, eviction bytes, quota updates | Original diagnosis and run artifacts; coverage needs audit | Recover/recompute consistent metrics for every retained baseline |
| TPOT, SLO violation rate | Not established by the present summary | Audit token timestamps; instrument if needed; define SLO before testing |
| Controller overhead and physical transfer cost | Not comprehensively measured | Instrument explicitly; do not use quota-change bytes as transfer bytes |
| Output equivalence under caching | Not established | Compare deterministic cache-off/cold/warm/evicted executions |
| Task answer quality | Not evaluated | Add labeled natural-language evaluation only with a real task and rubric |

Use common coverage for each reported comparison. A method with missing primary endpoints should not appear in a winner ranking until those endpoints are recovered. It may remain in a separately labeled component study; do not erase inconvenient results.

## Is this project strong enough to present?

Yes, as a scoped systems investigation: it has a working large-cache integration on real A100 hardware, a replicated negative result, a measurable churn/occupancy diagnosis, and a candidate with a visible latency/fairness tradeoff. These map well to the supplied feedback's emphasis on controlled experiments and explanation. This is not a prediction of a grade or proof the study is complete.

Main weaknesses: random token prompts limit application realism; the candidate has one screening seed; several mechanisms change together; tails depend on quantile convention; live scaling/new workloads remain unverified; semantic correctness is untested. Present these candidly and use them to motivate Phase 3.

A useful walkthrough: after hot demand moves A→B, changing quotas can evict cached prefixes; later repeats miss and refill. Equal allocation retained about 127.63 GiB in the original seed-11 diagnosis while adaptive retained roughly 74–76 GiB and evicted more bytes. This supports a churn hypothesis, not a causal proof. The cautious policy's one-seed median gain and tail penalty show why a single aggregate score is insufficient.

## Plan to close the gaps, in priority order

1. **Dataset card and reproducibility.** Preserve generator/source hashes, model revision, prompt construction, seeds, arrival distributions, tenant weights, lengths, timings and raw request IDs. Include synthetic-data wording on setup slides.
2. **Complete baseline metric table.** Start from the exported all-policy CSV. Recover raw remaining runs and occupancy/control logs. Select a focused final comparison (equal, original adaptive, cautious adaptive, shared; fixed where its prior matches the question), reporting the same primary endpoints for every method. Keep the full screen in supporting evidence.
3. **Correctness before semantic claims.** Use a fixed prompt suite and identical greedy decoding parameters. Compare cache disabled, cold enabled, repeated warm hits, eviction/refill and interleaved tenants. Record generated token IDs, exact-output agreement and numerical/logit differences if accessible. Investigate mismatches; GPU nondeterminism is a confound, not permission to ignore errors. This is a cache-output agreement metric, not answer accuracy.
4. **Realistic text validation.** Retain the synthetic benchmark for controlled mechanisms, then add one licensed, versioned document-QA or repeated-document workload. Select and document the exact corpus/split/IDs and tokenizer before running. Preserve document/question boundaries when truncating. Assign tenants explicitly, create repeated document prefixes and changing questions, and publish the workload mapping. No public dataset has yet been selected or run for this addition.
5. **Quality metric if using labeled QA.** Report task-appropriate exact match/token F1 or another justified gold-answer metric for every selected policy, alongside median/p95 TTFT, reuse and errors. Use identical questions and decoding. If an LLM judge is necessary, specify judge/prompt and manually audit a sample; do not treat its judgment as objective ground truth. State that a short forced 32-token systems benchmark is not automatically suitable for answer-quality evaluation.
6. **Held-out replication and bottleneck ablation.** Use at least three new paired seeds if resources allow; separate cadence, floor, repeat signal and prior. Diagnose first touches versus repeat misses, refill time, controller overhead and per-tenant harm. Do not rerun valid existing traces without a specific reason.
7. **Presentation/report integration.** Keep 2–3 main RQs, show setup and dataset construction, one matched results table, one failure walkthrough, observation/explanation/insight distinctions, and a concrete remaining-work slide. Retain 12-minute core timing. Report preparation follows the six-page plan in `04-phase-3-plan.md`.

These are planned additions, not new completed experiments. Recover existing evidence first; prioritize output correctness and one realistic validation over an exhaustive new policy sweep.
