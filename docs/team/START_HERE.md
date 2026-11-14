# Team handoff: start here

Prepared November 13, 2026 for Pradeep, Akshit and Jauwaad. Measurements are from November 10; this documentation branch did not run new experiments.

## The question in one sentence

**Can a feedback policy divide a fixed CPU-RAM KV-cache budget among competing tenants better than fixed allocations when their workloads change?**

A tenant is a user/application workload. KV data is the attention state for previously processed tokens, not a saved answer. Retaining reusable prefixes can reduce repeated prefill work. More cache for one tenant means less for another under a fixed budget, so aggregate speed and fairness can conflict.

The intended contribution is the allocation policy, its controllable mechanism and its experimental evaluation. Running vLLM/LMCache alone is supporting infrastructure, not the new research contribution.

## Current direction and status

- **Option 1:** GPU inference with external KV in CPU host RAM, on the same node. This starter implements its diagnostics.
- **Option 2:** CPU-only inference and caching on one CPU node. It was tested separately and is documented as an alternative, not implemented by this starter.
- We lean toward Option 1 because it has measured large-cache feasibility and appears practical for repeated experiments. Professor approval/final selection has not been recorded. Do not present this as an approved decision.
- Proposed scope is 4/8/16 tenants, starting at 128 GiB cache if feasible. 256/512 GiB are unverified extensions. The original smaller proposal's figures were superseded by this revised target.
- Earlier context also contained a distinct multimodal RAG proposal. It is not the same as the two KV deployment options; see the appendix in the test catalog.

## What has been built and measured

1. Qwen2.5-7B GPU inference with real external-cache retrieval.
2. A same-node A100 run with **127.996 GiB actually retained KV**, within a 192 GiB host-RAM allocation.
3. Separate 16-identity tests showing that explicit LMCache tenant tags isolate entries on the tested connector.
4. A separate four-tenant **184-request** manual-quota test: A's retention went **42 MiB → 0 → 126 MiB** while peers remained at 42 MiB each.
5. CPU-only serving with **68 streaming requests across 4/8/16 tenants**, actual L1/L2 reuse and small retention-control diagnostics.
6. A clean starter with configurable paths, launch scripts, analyzers and lightweight tests. Its analyzers reproduce saved outcomes; its cleaned launcher has not had a fresh GPU deployment.

**These are separate component tests. We have not built/evaluated the adaptive controller or completed a combined 128 GiB / 16-tenant / dynamic-quota run.** No adaptive-performance improvement or general two-second TTFT SLO is established.

## Read in this order

| Read | What it gives you |
|---|---|
| [Project design and concepts](PROJECT_AND_DESIGN.md) | Architecture, mechanisms, proposed contribution and glossary |
| [Tests and results](TESTS_AND_RESULTS.md) | Exactly what ran, what came out, what failed and what each result means |
| [Evidence files](evidence/README.md) | Actual measured JSON and the 17-page technical report, with provenance |
| [Metrics and experiment plan](METRICS_AND_EXPERIMENTS.md) | Definitions, baselines, controls and the next experiment |
| [Runbook and outputs](RUNBOOK_AND_OUTPUTS.md) | Clone/setup/replay/rerun instructions and artifact interpretation |
| [Three-person collaboration plan](TEAM_PLAN.md) | Suggested work streams, review workflow, milestones and Q&A preparation |

For one document to share, use the [17-page historical report](evidence/SOL_FEASIBILITY_COMPLETE_REPORT.pdf). For the current team state, this handoff takes precedence over historical cleanup/status statements in that report. Its embedded local evidence links refer to the original archive; use this branch's evidence index for available GitHub files.

## What every teammate should be able to explain

- Why quotas can matter only when useful working sets compete for a limited cache.
- Why a faster repeated request alone does not prove LMCache reuse.
- Why tenant identity must reach the actual cache key and accounting layer.
- Why stock L2 quotas did not remove L1 copies in the CPU tests.
- Why 128 GiB configured capacity is not proof of 128 GiB occupied KV, and why the job needs more RAM.
- Which code is ours, which belongs to vLLM/LMCache, and what is still proposed.
- Which experiment supports each slide claim and what that experiment does not establish.

## Sharing and resource state

Repository visibility remains private. A branch link does not grant access: teammates need their own GitHub accounts added as collaborators by the owner. Do not share account credentials. No invitations were sent as part of this documentation task.

The original experiments were shut down and the earlier queue check showed no jobs. That is historical state, not a current resource check. No jobs were started for this branch. Use your own authorized Sol access and a compute allocation for any new model/memory work.

Phase 2 requires one group slide PDF by **November 21, 2026, 11:59 pm**. The supplied rubric totals 40 points; presentation duration was not yet announced. The research story must extend beyond a feasibility status report.
