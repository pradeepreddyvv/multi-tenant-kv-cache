#!/usr/bin/env bash
#SBATCH --job-name=kv-cache-probe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=192G
#SBATCH --time=00:30:00
#SBATCH --output=slurm-%j.out
set -euo pipefail
# Submit from the repository root. Account/partition/QoS are supplied by the user.
: "${SLURM_SUBMIT_DIR:?Submit this file using sbatch}"
exec bash "$SLURM_SUBMIT_DIR/scripts/run.sh" "${1:?Specify tenants, quota, or scale}"
