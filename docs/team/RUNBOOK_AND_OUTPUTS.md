# Team runbook and expected outputs

## Get the branch

Once the repository owner has granted your GitHub account collaborator access:

```bash
git clone --branch docs/team-handoff \
  https://github.com/pradeepreddyvv/multi-tenant-kv-cache.git
cd multi-tenant-kv-cache
```

For an existing clone:

```bash
git fetch origin
git switch --track origin/docs/team-handoff
```

If the local branch already exists, use `git switch docs/team-handoff`, then `git pull --ff-only`. Preserve any local work before switching. A GitHub 404 for this private repository may mean your account lacks access; it does not prove the branch is missing.

## Inspect results without Sol or a GPU

Read [the evidence index](evidence/README.md), open its JSON files or download the PDF. Verify the shared files from the repository root:

```bash
# macOS
(cd docs/team/evidence && shasum -a 256 -c SHA256SUMS)

# Linux alternative
(cd docs/team/evidence && sha256sum -c SHA256SUMS)
```

These checks establish file integrity, not correctness of the original experiment. The included files are selected measured summaries, not a complete raw-log bundle.

Run lightweight code checks with Python 3.10+ and Bash:

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/run.sh scripts/gpu_job.sbatch
```

If you have the original research archive's `results` folder, replay its raw logs through the cleaned analyzers:

```bash
python3 scripts/verify_saved_runs.py /absolute/path/to/original/results
```

That script makes temporary copies, checks all three historical GPU analyses and verifies that absent retrieval logs cannot pass the tenant/quota checks. **The curated summaries on this branch are insufficient for raw-log replay.** Pradeep maintains the separately preserved `DIS_ML` archive. Its `preservation-2026-11-10/README.md` contains download/restore/checksum instructions. The archive is not in Git because it also contains unrelated private context.

## Before a new live run

Each teammate uses their own Sol account and authorized account/partition/QoS combination. Sharing this code does not grant access to Pradeep's home/scratch data or allocations. Confirm which shared project storage and model/container paths the team can actually read. A clone alone cannot run the model without these dependencies.

Check your current host and allocation. Model loading, inference, installation and memory tests belong on compute nodes. The previous login-node resource incident is a reason to verify placement, not to assume a VS Code window title proves it. All live commands below are instructions, not jobs launched by this documentation task.

1. Obtain access to the tested image and pinned model snapshot in [environment provenance](../ENVIRONMENT.md).
2. Copy `configs/example.env` to `configs/local.env` and set existing absolute paths for GPU_IMAGE, HF_HOME and XDG_CACHE_HOME. That local file is ignored by Git.
3. Allocate a suitable GPU and explicit host RAM. Small probes historically used A30/40 GiB; scale used A100/192 GiB. A 128 GiB cache needs overhead beyond 128 GiB total allocation.
4. Start with `tenants`, inspect its analysis/logs, then run `quota`; attempt `scale` only in the larger allocation.

From the repository root:

```bash
sbatch --account=YOUR_ACCOUNT --partition=YOUR_PARTITION --qos=YOUR_QOS \
  scripts/gpu_job.sbatch tenants
```

Substitute `quota` or `scale` as needed. The supplied Slurm template requests an A100, 16 cores, 192 GiB and 30 minutes. Override resources only to match a suitable authorized configuration. Inside an existing GPU compute allocation, `bash scripts/run.sh tenants` invokes the same launcher.

The cleaned wrapper has not yet had a fresh live deployment. A successful rerun is a team milestone, not something already proved by this branch's existence. Preserve failure logs rather than changing the recorded historical evidence.

## Where outputs go

New outputs are ignored by Git under `runs/gpu-tenants-JOBID/`, `runs/gpu-quota-JOBID/`, or `runs/gpu-scale-JOBID/`. The same directory cannot be reused. Set DIS_ML_RESULT_DIR to a new absolute directory with an existing parent for a second run in one allocation.

| Artifact | Contents | How to interpret it |
|---|---|---|
| `launch.json` | Model revision, image path, host, job ID, cache capacity | Launcher configuration, not proof the workload completed |
| `run.log` | Model/cache logs and workload events | Match request IDs to actual retrievals; retain warnings |
| `memory.jsonl` | Periodic cgroup-v1 job-memory snapshots | Whole-job entitlement/use; unsupported layouts need a validated adapter |
| `requests.jsonl` | Tenant/mode or phase, request ID, timings, token counts, text | Per-request record; offline batch timings are not streaming TTFT |
| `occupancy.json` | Tenant-probe locked byte snapshots | Separation and actual occupied bytes |
| `quota-state.json` | Scheduled changes, occupancy samples, evicted chunks, errors | Mechanism behavior and overlap with inference |
| `batches.jsonl` | Scale population progress and batch timings | Population, not per-tenant performance |
| `occupancy.jsonl` | Scale locked-byte snapshots | Actual retained KV, not cumulative store traffic |
| `completed.json` | Workload completion and configuration | Necessary completion evidence; insufficient alone to prove reuse |
| `analysis.json` | Tenant/quota interpretation | Inspect pass flags plus original data; script exit zero alone is not a feasibility verdict |
| `occupancy-analysis.json` | Scale payload, memory, warnings and retention probes | Separates occupied KV from total job memory |

The quota workload is time-bounded; a new run need not have exactly 184 requests. The scale experiment has 600 population requests plus four retention probes. Most analysis checks assume this specific 7B workload and 256-token cache chunks. Changing model/prompt lengths may require revisiting the expected hit counts.

## Cleanup and storage

Let the Slurm job exit or cancel only your own experiment allocation when finished. Check that your model processes stopped. Do not delete other users' or other jobs' shared-memory objects. Do not blindly apply the CPU-only cleanup logic to the GPU path.

Keep weights/images/environments outside Git. Scratch data is not a permanent backup. Preserve important raw records in agreed team storage and retain their manifest/config. The historical cache contents were intentionally destroyed at shutdown; replication regenerates them from the workload.
