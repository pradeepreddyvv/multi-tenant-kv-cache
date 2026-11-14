# Shared historical evidence

These files were selected from the original November 10 Sol experiments. They are measured outputs, not synthetic example numbers or fresh runs of the cleaned repository. [MANIFEST.json](MANIFEST.json) records the original relative path, original SHA-256, published SHA-256 and transformation for each item.

| File | What it supports |
|---|---|
| [gpu-7b-cache.json](gpu-7b-cache.json) | Initial intended-model external cache test output |
| [gpu-scale-first-analysis.json](gpu-scale-first-analysis.json) | First scale run; cumulative stores must not be read as retained capacity |
| [gpu-scale-occupancy.json](gpu-scale-occupancy.json) | Direct retained bytes, whole-job memory, retention probes and warnings |
| [gpu-tenants-first-summary.json](gpu-tenants-first-summary.json) | First successful identity test |
| [gpu-tenants-repeat-summary.json](gpu-tenants-repeat-summary.json) | Independent fresh-model repeat; tag versus salt behavior |
| [gpu-primary-quota-analysis.json](gpu-primary-quota-analysis.json) | Manual quota effects, peer stability and inference overlap |
| [gpu-primary-quota-timeline.json](gpu-primary-quota-timeline.json) | Actual timestamps, scheduled changes and per-tenant byte samples |
| [cpu-7b-http-analysis.json](cpu-7b-http-analysis.json) | CPU 68-request pilot timings, retention metrics and memory |
| [cpu-raw-memory-probe.json](cpu-raw-memory-probe.json) | Raw 128 GiB write test; not occupied KV |
| [cpu-128gib-estimate.json](cpu-128gib-estimate.json) | Calculation/assumptions for estimated CPU population time; not a measured fill |
| [rag-diagnostic-summary.json](rag-diagnostic-summary.json) | Separate RAG exploration, not part of the Option 1 implementation |
| [original-analysis-replay.json](original-analysis-replay.json) | Saved-log replay checks performed during preservation |
| [SOL_FEASIBILITY_COMPLETE_REPORT.pdf](SOL_FEASIBILITY_COMPLETE_REPORT.pdf) | Original 17-page narrative with methods, failures and reproduction boundaries |

Tenant summary files omit request-level generated text; the retained summary fields are unchanged. Other copied experiment files are exact copies. No private email/chat exports or bulk model artifacts are included. New run outputs remain ignored by Git; this curated branch evidence is an explicit exception for team review.

The PDF's embedded relative evidence links point to the original `DIS_ML` archive and may not resolve from GitHub. Its historical “tunnel preserved” statements describe an earlier point in the session; the later shutdown superseded them. Use the current branch handoff for status and the files above for directly accessible data.

Verify all copied evidence and the manifest using SHA256SUMS. The hashes establish file integrity/provenance, not experimental validity. Complete request logs/configurations are preserved outside this repository; request the original results folder from the team owner to reproduce raw-log analysis. The curated summary pack is intentionally not a self-contained model/runtime or full raw-log archive.
