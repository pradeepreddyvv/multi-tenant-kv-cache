# Metric checks on saved logs (task C03)

Owner: C. Reviewer: A. Prepared November 19, 2026. **Saved-log check only; no inference, no Sol run.**

## What was checked

`scripts/check_request_attribution.py` joins every request record to the engine log by request ID and applies the classification in `METRICS.md`: hit, miss or unattributed, where missing evidence is never a hit. For each request it checks:

1. Exactly one lookup line, and at most one retrieval line.
2. The log's total tokens equal the record's prompt tokens. This confirms the ID join lines up.
3. Engine-computed tokens are 0. A non-zero value is flagged, not skipped (see below).
4. Retrieved tokens ≤ eligible (full-chunk) tokens, and the lookup hit equals the retrieved count.
5. The retrieval line's reported size equals tokens × 56 KiB.
6. The response is not failed (non-empty text, output tokens > 0).

Per run, it also flags log IDs with no matching record, and checks that every retained-byte snapshot is a whole number of 14 MiB chunks that agrees with its chunk count.

Any problem marks the run **Needs review** (exit status 2) rather than Valid.

## Results on the Nov 10 raw logs

Input: `historical-gpu-raw-logs-2026-11-10.zip` (SHA-256 `79063d80…`, see `CLAIMS.md` § Raw log archive). Archive checksums were verified before and after the check; nothing was modified.

| Run | Requests | Hit | Miss | Unattributed | Failed | Orphan log IDs | Snapshots checked | Validity |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `gpu-tenants-run1` | 64 | 47 | 17 | 0 | 0 | 0 | 0 (none saved) | Valid |
| `gpu-tenants-run3` | 64 | 47 | 17 | 0 | 0 | 0 | 4 | Valid |
| `gpu-primary-quota-run1` | 184 | 161 | 23 | 0 | 0 | 0 | 136 | Valid |
| `gpu-scale-976316` | 604 | 2 | 602 | 0 | 0 | 0 | 8 | Valid |

Cross-checks against the saved analyses:

- **Tenant runs:** 47 hits = 15 (salt first) + 16 (salt repeat) + 0 (tag first) + 16 (tag repeat). 17 misses = 1 + 16. This matches K09/K10.
- **Quota run:** 161 hits matches `actual_768_token_retrieves`. Per tenant: A 26 hits / 20 misses; B, C, D 45 hits / 1 miss each (their single cold populate request).
- **Scale run:** 600 population requests plus 4 probes. The 2 hits are the newest probes (4,096 tokens each); the oldest probes missed. Request IDs follow submission order because the scale workload writes no per-request file.
- **Reuse fraction** (retrieved / eligible tokens, METRICS.md): 73.4% in each tenant run, 87.5% in the quota run. The scale run is near zero by design, since it measures population, not reuse.

## Finding: the historical analyzers' log regex is fragile

The three analyzers match lookup lines only when `Inference Engine computed tokens: 0`. All historical runs had native prefix caching disabled, so every line had 0 and nothing was dropped. In any run with native prefix caching on, such as E10 or a native-cache baseline, a lookup line with a non-zero value would be **silently skipped**. Its request would then look like it had no lookup, and a hit could go uncounted. The new checker parses the field and flags it instead.

→ Before E10, the shared analysis path should parse this field (A/C, after Nov 21). No historical result is affected.

## Reproduce

```bash
python3 scripts/check_request_attribution.py \
  <archive>/results/gpu-tenants-run1 <archive>/results/gpu-tenants-run3 \
  <archive>/results/gpu-primary-quota-run1 <archive>/results/gpu-scale-976316 \
  --out /tmp/c03-report.json
```

Tests in `tests/test_check_request_attribution.py` use labeled synthetic logs to cover hit, miss, missing evidence, non-zero engine-computed tokens, join mismatch, impossible retrieval, size mismatch, orphan lines, failed responses and non-chunk byte counts.
