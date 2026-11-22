#!/usr/bin/env bash
set -euo pipefail
: "${SLURM_JOB_ID:?Run inside a GPU allocation}"
[[ $(hostname) != *login* ]] || exit 2
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
: "${DIS_ML_RESULT_DIR:?Choose a new absolute result directory}"
[[ "$DIS_ML_RESULT_DIR" = /* ]] || { echo "DIS_ML_RESULT_DIR must be absolute" >&2; exit 2; }
export GPU_IMAGE=${GPU_IMAGE:-/packages/apps/simg/vllm-cu129-nightly-0426.sif}
: "${HF_HOME:?Set HF_HOME to your cached model directory}"
export HF_HOME
: "${XDG_CACHE_HOME:?Set XDG_CACHE_HOME to your writable runtime cache}"
export XDG_CACHE_HOME
export PYTHONPATH="$root/scripts:$root" PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0
export HF_HUB_OFFLINE=1 LMCACHE_CHUNK_SIZE=256 LMCACHE_LOCAL_CPU=True
export LMCACHE_MAX_LOCAL_CPU_SIZE=${LIVE_CAPACITY_GIB:-1.75}
export TORCHINDUCTOR_CACHE_DIR=$XDG_CACHE_HOME/torchinductor TRITON_CACHE_DIR=$XDG_CACHE_HOME/triton
export TMPDIR=/tmp APPTAINER_TMPDIR=/tmp
mkdir "$DIS_ML_RESULT_DIR"
nvidia-smi --query-gpu=name,memory.total --format=csv > "$DIS_ML_RESULT_DIR/hardware.txt"
monitor_pid=
gpu_monitor_pid=
cleanup() {
  if [[ -n $gpu_monitor_pid ]]; then kill "$gpu_monitor_pid" 2>/dev/null || true; wait "$gpu_monitor_pid" 2>/dev/null || true; fi
  if [[ -n $monitor_pid ]]; then kill "$monitor_pid" 2>/dev/null || true; wait "$monitor_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
(while true; do python3 scripts/resource_snapshot.py; sleep 5; done) > "$DIS_ML_RESULT_DIR/memory.jsonl" &
monitor_pid=$!
nvidia-smi --query-gpu=timestamp,index,uuid,utilization.gpu,memory.used,power.draw --format=csv -l 5 > "$DIS_ML_RESULT_DIR/gpu.csv" &
gpu_monitor_pid=$!
apptainer exec --nv --bind "$root,$HF_HOME,$XDG_CACHE_HOME,$DIS_ML_RESULT_DIR" "$GPU_IMAGE" \
  python3 scripts/live_adaptive.py "$@" > "$DIS_ML_RESULT_DIR/run.log" 2>&1
