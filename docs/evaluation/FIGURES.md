# Historical evidence figures (task C02)

Owner: C. Reviewer: A. Prepared November 19, 2026.

Three figures recreated from the saved Nov 10, 2026 Sol measurements. **These are replots of saved files, not new runs.** Claim IDs (K02 etc.) refer to `docs/evaluation/CLAIMS.md` (PR03).

## Regenerate

The script reads the curated evidence pack from the `docs/team-handoff` branch. It uses only the standard library and needs no GPU.

```bash
EVIDENCE=$(mktemp -d)
git archive origin/docs/team-handoff docs/team/evidence | tar -x -C "$EVIDENCE"
(cd "$EVIDENCE/docs/team/evidence" && sha256sum -c SHA256SUMS)
python3 scripts/plot_historical_evidence.py "$EVIDENCE/docs/team/evidence" runs/figures
```

`runs/figures` is inside the repository checkout but ignored by Git (`runs/` is in `.gitignore`), so generated figures are never committed. The output is three 960×540 SVGs plus `figure-data.json`, which holds the exact plotted numbers (the table view for review). For tools that do not accept SVG, such as Google Slides, convert with a browser:

```bash
# Linux
CHROME=google-chrome
# macOS
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

"$CHROME" --headless --no-sandbox --window-size=960,700 \
  --screenshot=fig.png "file://$PWD/runs/figures/fig-scale-retained.svg"
```

Crop the PNG to 960×540, since headless Chrome's viewport is shorter than its window.

## Figures

Each figure states its job, hardware, date, units, source file and limitation on the image itself, so it can be lifted into a slide without losing its boundary.

### 1. `fig-scale-retained.svg`: retained KV fills the 128 GiB tier (K02–K06)

- **Observation:** retained KV grew 21.875 GiB per 100 unique 4,096-token prompts and stopped at 127.996 GiB (9,362 chunks). The oldest probes then missed and the newest hit. 270 allocator-full warnings appeared.
- **Why:** each prompt stores 16 chunks of 14 MiB (4,096 tokens × 56 KiB). The 600th-prompt total would be 131.25 GiB, so the tier filled and evicted the oldest chunks.
- **Lesson:** the CPU tier can hold close to its configured capacity of real model KV. The job's observed cgroup high-water was 145.19 GiB under its 192 GiB job RAM allocation. That includes file cache (14.6 GiB at the peak sample) and runtime memory, and **does not establish a minimum required allocation**. Capacity planning must measure overhead rather than assume it, and the warnings must be reported.
- **Not shown:** tenants, quotas, latency.

### 2. `fig-quota-timeline.svg`: per-tenant quota lower and raise (K12–K15)

- **Observation:** after A's limit was lowered to 0 at 1.10 s, A was zero in 60 of 60 post-enforcement samples. B, C and D held 42 MiB in all 134 samples. After the raise at 7.11 s, A was back at 42 MiB in the same sample. It reached 84 MiB at 8.21 s and 126 MiB at 8.61 s. Where A equals the peers, A is drawn dashed over their line.
- **Why:** each enforcement pass evicts only entries carrying A's tenant tag that are safe to evict, then records the sample. Passes are 100 ms apart. During the lowered interval A kept sending its one prefix, which was stored and then evicted by subsequent enforcement passes: 51 chunks, i.e. 17 removals of its 3-chunk prefix. Occupancy can rise between passes, so a post-enforcement sample of zero does not mean A held zero bytes at every instant, and 100 ms is not a guaranteed enforcement deadline. The request-level evidence is that 15/15 settled low-quota A requests missed. Once the limit rose, that prefix stayed (42 MiB). The workload sends A two new prefix variants only after 8 s, which explains the later steps. A quota permits retention; occupancy follows demand.
- **Lesson:** per-tenant retention can be controlled live without disturbing peers. The gap between a quota change and actual occupancy is demand-driven, which an adaptive policy must account for (E07's quota-to-occupancy timeline).
- **Not shown:** adaptive control, latency, more than four tenants, sustained runs. The hook is a 30-second diagnostic, not stock LMCache quotas.

### 3. `fig-tenant-isolation.svg`: tag versus salt isolation (K09–K10)

- **Observation:** with `cache_salt` alone, 15 of 16 tenants' first requests retrieved another tenant's entry. With LMCache tenant tags, all 16 first requests missed and all 16 repeats hit. The counts were identical in two fresh-process runs.
- **Why:** on the installed LMCacheConnectorV1 (LMCache 0.4.4), the salt did not reach the external cache key, while the tag did.
- **Lesson:** a negative result worth presenting. Per-tenant accounting depends on identity reaching the external cache, so it must be verified per connector version rather than assumed.
- **Not shown:** concurrency (requests were sequential), security properties, other connectors.

## Design notes

- Light slide surface. Categorical slots 1–2 of the dataviz reference palette (blue `#2a78d6`, orange `#eb6834`) pass the palette validator: CVD ΔE 24.7, normal-vision ΔE 33.6, both ≥ 3:1 contrast. Identity is never color-alone: direct labels and a legend appear on every multi-series figure.
- The script refuses an output directory that resolves to the evidence directory or anywhere inside it. It compares resolved paths, so a case-insensitive alias on macOS or Windows is not detected. It also raises an error rather than merging B/C/D or the two tenant runs if they ever differ.
- Captions label 192 GiB and 40 GiB as job RAM allocations, not host RAM.
- Tests in `tests/test_plot_historical_evidence.py` use labeled synthetic fixtures only.
