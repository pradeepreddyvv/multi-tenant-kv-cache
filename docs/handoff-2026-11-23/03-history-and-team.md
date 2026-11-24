# History, decisions and team contributions

## Evolution

1. Literature survey and paper-comparison workbook established KV-cache design choices and a taxonomy. Survey artifacts are separate from the six-page final implementation report.
2. Selected GPU inference plus CPU-RAM KV retention; professor allowed CPU-only fallback if integration failed. CPU-only feasibility work is not evidence of GPU/CPU performance equivalence.
3. November 10 historical diagnostics established large retained-cache capacity, explicit tenant identity and manual quota enforcement.
4. Split work into architecture/integration (Pradeep), policy/offline validation (Akshith), and evidence/plots/evaluation planning (Jauwaad), with review rotation.
5. Original 32B live equal/fixed/adaptive comparison exposed a negative adaptive result; diagnosis identified lower occupancy and more repeat misses/evictions.
6. Explored replacement/controller families in simulation and queued live candidates. Cautious adaptive improved one median-latency comparison but not every metric.
7. Merged teammate contributions and live scaling integration. Queued scaling under the higher FairShare class profile; the replacement job later ran.
8. Finalized presentation around four-tenant live evidence, with plain-language definitions and explicit uncertainty. Offline scaling results were deliberately excluded from the main deck to avoid implying live performance.
9. Phase 3 now prioritizes explanation, controlled alternatives, evidence recovery and concise reporting.

## Completed merged work (GitHub checked November 23)

| PR | Work |
|---|---|
| [1](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/1) | Evidence claims, metric definitions and saved-log checks |
| [2](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/2) | Historical evidence figures |
| [3](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/3) | Controlled HTTP evaluation specification; a plan, not measured results |
| [4](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/4) | Allocation-policy contract and offline baselines |
| [5](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/5) | CPU allocation policies and offline validation |
| [6](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/6) | Contributor name correction in handoff documents |
| [7](https://github.com/pradeepreddyvv/multi-tenant-kv-cache/pull/7) | Live integration, tenant-count controls and trace/evidence validation |

Main merge commit: `4be316c7cc0d9ec1294cf2fbc56784df6784c4d3`. Scaling source head: `154fa4d`. Fetch found no later main changes at this snapshot. Earlier review notes about plots and wording apply to earlier heads; inspect merged content before reopening them.

## Contributions to confirm for final report

- **Venkata Pradeep Reddy Venuthurla:** architecture and GPU/CPU integration workstream; Sol experiments, controller diagnosis, candidate comparisons and presentation integration. Confirm exact individual implementation ownership against commits and collaboration records.
- **Akshith Reddy Ganta:** policy contract, baseline/allocation implementation, offline validation and policy presentation material (PRs 4–5).
- **Jauwaad Shams:** curated evidence claims, metric checks, historical figures, evaluation specification and evidence presentation material (PRs 1–3).

These are evidence-backed workstream descriptions, not a claim that assigned responsibilities were all completed personally. Obtain each member's actual contributions and distinguish collaborative work in the required final statement.

Review rotation remains Akshith reviews Pradeep, Jauwaad reviews Akshith, Pradeep reviews Jauwaad. Self-review is not teammate approval.

## Presentation and workshop

Latest deck: `team11-kv-cache-final-submission.pptx`, with a companion PDF. The approved version has the full title and the subtitle “Sharing a language model’s cache across applications.” Presentation files remain with the team; this PR publishes documentation and metric tables only.

21 slides: 13 core and 8 appendix; timing plan about 11m45s, not proof of actual rehearsal duration. Covers definitions, architecture, experiment setup, feasibility, original loss/diagnosis, cautious candidate, workload factors, conclusions and evidence limits. Internal version labels are explained. The PDF is image-based; do not rely on PDF text extraction for review.

Team 11: November 25, 2026, 4 p.m.; 12-minute presentation, 3-minute Q&A. Use own ASU Zoom accounts, attend required sessions and submit workshop notes for attendance credit. Capture professor feedback for the final report. Canvas upload status remains unverified.
