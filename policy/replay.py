"""Synthetic observation replay; no cache simulation or inference metrics."""

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import socket
import subprocess
import tempfile

from policy.allocation import equal_allocation, fixed_unequal_allocation
from policy.controller import CONFIG, initial_state, policy


BUDGET = 2 * 2**30
SEEDS = (11, 22, 33)
TENANT_COUNTS = (4, 8, 16)
STEPS = 120


def git_output(*args):
    return subprocess.check_output(
        ["git", *args], text=True
    ).strip()


def save_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def make_fixture(tenants, seed):
    rng = random.Random(seed)
    windows = []
    for step in range(1, STEPS + 1):
        if step <= 20:
            phase, hot = "balanced", None
        elif step <= 40:
            phase, hot = "initial_skew", tenants[0]
        elif step <= 80:
            phase, hot = "shifted", tenants[1]
        elif step <= 100:
            phase, hot = "idle_tenant_0", tenants[1]
        else:
            phase, hot = "zero_demand", None

        rows = []
        for tenant in tenants:
            base = 1000 if hot == tenant else 100
            if phase == "balanced":
                base = 100
            tokens = base + rng.randrange(21)
            if phase == "zero_demand":
                tokens = 0
            if phase == "idle_tenant_0" and tenant == tenants[0]:
                tokens = 0
            rows.append({
                "tenant_id": tenant,
                "window_end_s": step * CONFIG["interval_s"],
                "eligible_input_tokens": tokens,
                "retained_bytes": 0,
                "retrieved_tokens": 0,
                "errors": 0,
            })
        windows.append({"step": step, "phase": phase, "observations": rows})
    return windows


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    if not Path("policy/controller.py").is_file():
        raise SystemExit("Run from the repository root.")

    sources = sorted(Path("policy").glob("*.py"))
    source_hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sources
    }

    Path("runs").mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="policy-offline-", dir="runs"))

    manifest = {
        "status": "started",
        "evidence_type": "synthetic observation replay",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_output("rev-parse", "HEAD"),
        "git_status": git_output("status", "--porcelain"),
        "source_sha256": source_hashes,
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "budget_bytes": BUDGET,
        "seeds": SEEDS,
        "tenant_counts": TENANT_COUNTS,
        "windows_per_fixture": STEPS,
        "controller_config": CONFIG,
        "fixed_weight_rule": "tenant 0 = 700; every other tenant = 100",
        "limitations": [
            "Fixed observations do not respond to quota decisions.",
            "Zero retained/retrieved values are placeholders, not measurements.",
            "No inference, cache eviction, TTFT, throughput, or fairness measured.",
            "Window timestamps are synthetic; replay does not sleep.",
            "Initial allocations are excluded from update counts.",
        ],
    }
    save_json(out / "manifest.json", manifest)
    summaries = []

    fields = [
        "tenant_count", "seed", "policy", "step", "time_s",
        "phase", "tenant_id", "eligible_input_tokens",
        "quota_bytes", "reason", "window_moved_bytes",
    ]

    with (out / "quotas.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()

        for count in TENANT_COUNTS:
            tenants = [f"T{i:02d}" for i in range(count)]
            equal = equal_allocation(tenants, BUDGET)
            weights = {t: 700 if t == tenants[0] else 100 for t in tenants}
            fixed = fixed_unequal_allocation(weights, BUDGET)
            floors = equal_allocation(tenants, BUDGET // 5)

            for seed in SEEDS:
                windows = make_fixture(tenants, seed)
                fixture_name = f"fixture-n{count}-seed{seed}.json"
                save_json(out / fixture_name, {
                    "synthetic": True,
                    "initial_weights": weights,
                    "windows": windows,
                })
                fixture_hash = hashlib.sha256(
                    (out / fixture_name).read_bytes()
                ).hexdigest()

                for name in ("equal", "fixed_unequal", "adaptive"):
                    state = initial_state(tenants, BUDGET)
                    previous = dict(fixed if name == "fixed_unequal" else equal)
                    updates = 0
                    total_moved = 0

                    for window in windows:
                        rows = window["observations"]
                        if name == "adaptive":
                            quotas, state = policy(rows, BUDGET, state)
                            reason = state["reason"]
                        else:
                            quotas = dict(equal if name == "equal" else fixed)
                            reason = "static_baseline"

                        require(set(quotas) == set(tenants), "membership mismatch")
                        require(
                            all(type(q) is int and q >= 0 for q in quotas.values()),
                            "invalid quota",
                        )
                        require(sum(quotas.values()) == BUDGET, "budget mismatch")
                        moved = sum(
                            max(quotas[t] - previous[t], 0) for t in tenants
                        )

                        if name == "adaptive":
                            require(moved <= BUDGET // 10, "transfer cap exceeded")
                            require(
                                all(quotas[t] >= floors[t] for t in tenants),
                                "minimum allocation violated",
                            )
                            require(moved == state["moved_bytes"], "move mismatch")
                        else:
                            require(moved == 0, "static baseline changed")

                        updates += int(moved > 0)
                        total_moved += moved
                        for row in rows:
                            tenant = row["tenant_id"]
                            writer.writerow({
                                "tenant_count": count,
                                "seed": seed,
                                "policy": name,
                                "step": window["step"],
                                "time_s": row["window_end_s"],
                                "phase": window["phase"],
                                "tenant_id": tenant,
                                "eligible_input_tokens": row["eligible_input_tokens"],
                                "quota_bytes": quotas[tenant],
                                "reason": reason,
                                "window_moved_bytes": moved,
                            })
                        previous = dict(quotas)

                    summaries.append({
                        "tenant_count": count,
                        "seed": seed,
                        "policy": name,
                        "fixture": fixture_name,
                        "fixture_sha256": fixture_hash,
                        "windows_checked": len(windows),
                        "quota_updates": updates,
                        "total_transferred_bytes": total_moved,
                        "final_quotas": previous,
                    })

    save_json(out / "summary.json", {
        "status": "completed",
        "all_invariants_passed": True,
        "comparisons": summaries,
    })
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(out.iterdir()) if path.is_file()
    }
    save_json(out / "artifact_sha256.json", hashes)

    print(f"OUTPUT_DIRECTORY={out.resolve()}")
    print(f"Completed {len(summaries)} policy replays.")
    print("All checked allocation invariants passed.")
    print("Synthetic policy evidence only; no inference performance measured.")


if __name__ == "__main__":
    main()
