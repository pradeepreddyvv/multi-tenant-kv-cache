"""Shared settings without importing GPU frameworks."""
import os
from pathlib import Path

MODEL = 'Qwen/Qwen2.5-7B-Instruct'
REVISION = 'a09a35458c702b33eeacc393d103063234e8bc28'


def output_directory():
    """Refuse accidental mixing of old and new experiment records."""
    out = Path(os.environ['DIS_ML_RESULT_DIR'])
    out.mkdir(parents=True, exist_ok=True)
    artifacts = ['requests.jsonl', 'batches.jsonl', 'completed.json',
                 'occupancy.json', 'occupancy.jsonl', 'quota-state.json']
    if any((out / name).exists() for name in artifacts):
        raise RuntimeError('Experiment artifacts already exist; use a fresh run directory')
    return out
