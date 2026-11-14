# Validation of the cleaned starter

Prepared November 13, 2026. No new model inference, memory-scale run or Slurm allocation was launched for this cleanup.

Checks completed:

- All Python files parse; both shell entry points pass `bash -n`.
- Two unit tests protect existing experiment records from overwrite and allow fresh launcher metadata.
- The cleaned tenant, quota and scale analyzers reproduce the original saved JSON analyses exactly using temporary copies of the successful historical runs.
- Removing retrieval logs makes both tenant-isolation and quota feasibility checks fail, rather than silently passing from saved completion summaries alone.

Replay those evidence-dependent checks if you have the team's original results folder:

```bash
python3 scripts/verify_saved_runs.py /path/to/original/results
```

Changes from the original runs include configurable image/cache/repository paths, a common launcher and Slurm template, a pinned model/tokenizer revision, refusal to reuse output directories, a consistent per-run log layout, a portable scale-analysis path, and a stricter quota pass condition requiring all settled low-quota A requests to miss plus actual retrieval evidence.

The model workloads and bounded backend diagnostic remain derived from the original tested scripts. Static checks and saved-log replay do not verify that the cleaned launcher deploys successfully: a fresh authorized GPU smoke run is the next validation step. No GPU latency improvement or adaptive-controller benefit is claimed.
