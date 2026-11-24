# Evidence inventory and recovery

## Published with this handoff

Two derived CSVs contain the seven-policy seed-601 comparison and all 70 policy/phase/tenant rows. They were exported from the preserved analysis/manifests, not newly measured. Empty p95 values mean unavailable due to small sample counts, not zero. Hashes are in `evidence/checksums.json`.

## Preserved experiment identifiers

| Study | Identifiers | Status |
|---|---|---|
| Original live comparison | `large32-{equal,fixed,adaptive}-{11,29,47}` | Nine completed runs; paired analysis and raw evidence preserved by Pradeep |
| 32B feasibility | `large32-stress01`, seed 22 | Completed; 614 validated requests |
| Seven-policy shift screen | `screening-{equal,fixed,adaptive,slow,reuse,v3,shared}-shift-601-2202045` | Seven valid local analyses; 622 requests each |
| Remaining scan/burst screen | Job 2202045 | Final completion and raw evidence need recovery |
| Live 8/16-tenant scaling | Job 2221040 | Observed running historically; final results unverified |
| Offline policy validation | PR 5, commit 503e6b3 | 4/8/16 tenants; arithmetic validation, not live inference |
| Algorithm simulation | 13 policies × 6 workloads × 20 seeds | 1,560 simulations; not GPU latency measurements |

Raw JSON snapshots are intentionally not copied into this documentation directory because they include execution metadata and local environment details. Obtain the preserved source bundles from the experiment owner; do not treat CSVs as a substitute for raw evidence.

## Existing GitHub evidence release

https://github.com/pradeepreddyvv/multi-tenant-kv-cache/releases/tag/evidence-2026-11-21

Listed assets at the November 23 check: `analysis-evidence.tar.gz`, `publication-inspection.json`, `sol-evidence-20261121.tar.gz`, `sol-evidence-20261122T032046Z.tar.gz`. Asset listing is not a fresh checksum verification. These are snapshots; do not assume they contain final candidate/scaling results. No scaling-specific archive was listed.

On Sol, the experiment owner should inspect accounting for jobs 2202045 and 2221040, then retrieve status tables, source snapshots, manifests, request/cache/quota/occupancy logs and analysis outputs. A completed allocation does not prove every inner experiment completed successfully.

Before new analysis: verify source and trace hashes, model revision, cache capacity, phase boundaries, errors and percentile convention. Keep original and recomputed analyses separately. Preserve interrupted/invalid runs in the inventory with reasons for exclusion.

## Reproduction resources

- Historical claims and metrics: `../evaluation/CLAIMS.md` and adjacent evaluation documentation.
- Integrated live runner: repository `scripts/live_adaptive.py`, `scripts/analyze_live.py` and `docs/evaluation/TENANT_SCALING.md`.
- Candidate controllers: frozen experiment source includes `policy/candidates.py`; this file is not on main at the handoff snapshot. Recover/review it before implementation comparisons.
- FairCache author artifact: https://github.com/icloud-ecnu/FairCache at `4fa5650273e439237b163aaa0d4aa852dcd4463e`; planned reproduction only.

Previously reported 23, 71, 79 and 87 checks belong to overlapping snapshots/scopes. Do not add them or claim a fresh test run from this documentation update.
