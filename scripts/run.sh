#!/usr/bin/env bash
# Run only inside an existing Slurm GPU compute allocation.
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^(tenants|quota|scale)$ ]]; then
  echo 'Usage: bash scripts/run.sh {tenants|quota|scale}' >&2
  exit 2
fi
mode=$1
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
config=${DIS_ML_CONFIG:-$project_root/configs/local.env}
if [[ -f "$config" ]]; then
  set -a
  source "$config"
  set +a
fi
: "${SLURM_JOB_ID:?Run this script inside an allocated Slurm GPU job}"
: "${GPU_IMAGE:?Set GPU_IMAGE in configs/local.env}"
: "${HF_HOME:?Set HF_HOME to the existing model cache}"
: "${XDG_CACHE_HOME:?Set XDG_CACHE_HOME to writable scratch storage}"
case $(hostname) in
  *login*) echo 'Run on an allocated compute node, not a login node.' >&2; exit 2 ;;
esac
[[ -f "$GPU_IMAGE" ]] || { echo "Missing image: $GPU_IMAGE" >&2; exit 2; }
[[ -d "$HF_HOME/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28" ]] || {
  echo 'The pinned Qwen2.5-7B snapshot is missing from HF_HOME.' >&2; exit 2;
}
command -v apptainer >/dev/null
nvidia-smi -L
export HF_HOME XDG_CACHE_HOME
export HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-1}
export PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1
export PYTHONPATH=$project_root/scripts
export TORCHINDUCTOR_CACHE_DIR=$XDG_CACHE_HOME/torchinductor
export TRITON_CACHE_DIR=$XDG_CACHE_HOME/triton
export LMCACHE_CHUNK_SIZE=256 LMCACHE_LOCAL_CPU=True DIS_ML_OCCUPANCY=1
export TMPDIR=/tmp APPTAINER_TMPDIR=/tmp
case $mode in
  tenants) probe=gpu_tenant_probe.py; analyzer=analyze_gpu_tenant_probe.py; cache_gib=2 ;;
  quota) probe=gpu_primary_quota_probe.py; analyzer=analyze_primary_quota_probe.py; cache_gib=2 ;;
  scale) probe=gpu_scale.py; analyzer=analyze_gpu_scale_occupancy.py; cache_gib=128 ;;
esac
export LMCACHE_MAX_LOCAL_CPU_SIZE=$cache_gib
mkdir -p "$project_root/runs"
if [[ $mode == scale ]]; then
  default_run=$project_root/runs/gpu-scale-$SLURM_JOB_ID
else
  default_run=$project_root/runs/gpu-$mode-$SLURM_JOB_ID
fi
export DIS_ML_RESULT_DIR=${DIS_ML_RESULT_DIR:-$default_run}
# mkdir without -p makes duplicate launchers fail before opening any log.
mkdir -- "$DIS_ML_RESULT_DIR"
export DIS_ML_RESULT_DIR
export GPU_IMAGE
python3 - <<'PY' > "$DIS_ML_RESULT_DIR/launch.json"
import json, os, platform
from runtime import MODEL, REVISION
print(json.dumps({'mode_capacity_GiB': int(os.environ['LMCACHE_MAX_LOCAL_CPU_SIZE']),
 'model': MODEL, 'revision': REVISION, 'host': platform.node(),
 'job_id': os.environ['SLURM_JOB_ID'], 'image': os.environ['GPU_IMAGE'],
 'native_prefix_caching': False}, indent=2))
PY
cleanup() {
  if [[ -n ${monitor_pid:-} ]]; then
    kill "$monitor_pid" 2>/dev/null || true
    wait "$monitor_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
(
  while true; do
    python3 "$project_root/scripts/resource_snapshot.py"
    sleep 5
  done
) > "$DIS_ML_RESULT_DIR/memory.jsonl" &
monitor_pid=$!
set +e
apptainer exec --nv --bind "$project_root,$HF_HOME,$XDG_CACHE_HOME,$DIS_ML_RESULT_DIR" \
  "$GPU_IMAGE" python3 "$project_root/scripts/$probe" \
  > "$DIS_ML_RESULT_DIR/run.log" 2>&1
status=$?
set -e
cleanup
monitor_pid=
if [[ $status -ne 0 ]]; then
  echo "Probe failed ($status); see $DIS_ML_RESULT_DIR/run.log" >&2
  exit "$status"
fi
# Analyze in the pinned image too, rather than assuming host Python compatibility.
apptainer exec --bind "$project_root,$DIS_ML_RESULT_DIR" "$GPU_IMAGE" \
  python3 "$project_root/scripts/$analyzer" "$DIS_ML_RESULT_DIR"
echo "Results saved to $DIS_ML_RESULT_DIR"
