# Team handoff — November 23, 2026

**Cost-Aware Tiered KV-Cache Repartitioning for Multi-Tenant LLM Serving**
Sharing a language model’s cache across applications.

Team: Venkata Pradeep Reddy Venuthurla, Akshith Reddy Ganta, Jauwaad Shams.

## Start here

- [System and algorithm definitions](01-project-and-algorithms.md)
- [Results, diagnosis and limitations](02-results.md)
- [Project history and team contributions](03-history-and-team.md)
- [Phase 3 schedule and report rubric](04-phase-3-plan.md)
- [Dataset, complete metric coverage and remaining gaps](07-datasets-metrics-and-evaluation-gaps.md)
- [FairCache reproduction and extension plan](08-faircache-baseline-and-extension-plan.md)
- [Evidence inventory and recovery](evidence-inventory.md)
- [Research questions and speaking answers](research-questions.md)
- [Seven-policy aggregate table](evidence/live-policy-results.csv)
- [All 70 policy/phase/tenant metric rows](evidence/live-all-policy-metrics.csv)

## What is established

Our large-cache feasibility run stored 128 GiB of KV while processing 614 validated requests. The original adaptive controller lost to equal shares across three seeds. Cautious adaptive improved median TTFT by about 19.9% in one newer seed, but worsened p95 and some tenant latencies. It is not a confirmed overall winner.

The main workload uses synthetic random token-ID prefixes, not a public QA dataset. Answer accuracy was not measured. Cache reuse, request success and answer correctness are distinct concepts.

All PRs 1–7 were merged at the snapshot; source main was `4be316c7cc0d9ec1294cf2fbc56784df6784c4d3`. This handoff does not modify code or establish a new live deployment.

## What remains unverified

Jobs 2202045 and 2221040 were last recorded running by the watcher on November 22 at 08:33 UTC. The scaling watcher recorded zero saved snapshots. Sol was unreachable during the November 23 check. Recover scan/burst and 8/16-tenant results before claiming completion; do not rerun valid results unnecessarily.

FairCache is selected as a reproduction target. It has NOT been reproduced or compared in our existing experiments. Its proposed extension requires full-paper review, novelty/overlap checks and an unchanged baseline first. The current equal-share baseline remains valid; no old result is relabeled as FairCache.

## Next actions

1. Pradeep: recover outstanding Sol artifacts and exact environments; audit FairCache compatibility separately from the working system.
2. Akshith: map paper mechanisms to code; document original/cautious algorithms and select one controlled extension or ablation.
3. Jauwaad: validate complete metric coverage, assemble matched plots and track evidence/claim links.
4. Together: confirm actual individual contributions, agree a bounded experiment budget and rehearse the current presentation.

Assignments are proposed until confirmed by the team. Review rotation remains Akshith → Pradeep’s work; Jauwaad → Akshith’s work; Pradeep → Jauwaad’s work. Self-review is not teammate approval.

Team 11 workshop: November 25 at 4 p.m., 12 minutes talk plus 3 minutes Q&A. Report: December 5 at 11:59 p.m., one PDF, 11-point, at most six main-body pages; references may extend beyond six. Actual Canvas submission is not verified.
