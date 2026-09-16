from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return centre - half, centre + half


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def bootstrap_difference(
    per_scenario: dict[tuple[str, str, str], tuple[float, float]],
    resamples: int = 10_000,
) -> tuple[float, float, float]:
    pairs = list(per_scenario.values())
    observed = sum(a - b for a, b in pairs) / len(pairs)
    rng = random.Random(20260915)
    draws = []
    for _ in range(resamples):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        draws.append(sum(a - b for a, b in sample) / len(sample))
    return observed, percentile(draws, 0.025), percentile(draws, 0.975)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.raw.open(encoding="utf-8", newline="")))
    methods = sorted({row["method"] for row in rows})
    output: dict[str, object] = {
        "methods": {},
        "strata": {},
        "topology_strata": {},
        "paired_bootstrap": {},
    }

    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        attacks = [row for row in subset if row["adversarial"] == "1"]
        unsafe = sum(int(row["unsafe_accept"]) for row in attacks)
        lower, upper = wilson(unsafe, len(attacks))
        costs = [float(row["monitor_cost"]) for row in subset]
        latencies = [float(row["admission_latency_ns"]) / 1e6 for row in subset if float(row["admission_latency_ns"]) > 0]
        output["methods"][method] = {
            "unsafe_attacks": unsafe,
            "attack_trials": len(attacks),
            "unsafe_accept_rate": unsafe / len(attacks),
            "unsafe_accept_wilson95": [lower, upper],
            "closure_rate": sum(int(row["closed"]) for row in subset) / len(subset),
            "benign_accept_rate": sum(int(row["accepted"]) for row in subset if row["adversarial"] == "0") / sum(row["adversarial"] == "0" for row in subset),
            "mean_monitor_cost": sum(costs) / len(costs),
            "latency_ms": {
                "p50": percentile(latencies, 0.50) if latencies else 0.0,
                "p95": percentile(latencies, 0.95) if latencies else 0.0,
                "p99": percentile(latencies, 0.99) if latencies else 0.0,
            },
        }

    for size in sorted({int(row["initial_agents"]) for row in rows}):
        subset = [row for row in rows if int(row["initial_agents"]) == size and row["method"] == "epochcut"]
        latencies = [float(row["admission_latency_ns"]) / 1e6 for row in subset]
        output["strata"][str(size)] = {
            "n": len(subset),
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
            "p99_latency_ms": percentile(latencies, 0.99),
            "mean_monitor_cost": sum(float(row["monitor_cost"]) for row in subset) / len(subset),
        }

    for topology in sorted({row["topology"] for row in rows}):
        epoch_subset = [
            row for row in rows
            if row["topology"] == topology and row["method"] == "epochcut"
        ]
        epoch_attacks = [row for row in epoch_subset if row["adversarial"] == "1"]
        periodic_attacks = [
            row for row in rows
            if row["topology"] == topology
            and row["method"] == "periodic-5"
            and row["adversarial"] == "1"
        ]
        latencies = [float(row["admission_latency_ns"]) / 1e6 for row in epoch_subset]
        output["topology_strata"][topology] = {
            "epochcut_attack_trials": len(epoch_attacks),
            "epochcut_unsafe_attacks": sum(int(row["unsafe_accept"]) for row in epoch_attacks),
            "periodic_unsafe_accept_rate": sum(
                int(row["unsafe_accept"]) for row in periodic_attacks
            ) / len(periodic_attacks),
            "epochcut_mean_monitor_cost": sum(
                float(row["monitor_cost"]) for row in epoch_subset
            ) / len(epoch_subset),
            "epochcut_p95_latency_ms": percentile(latencies, 0.95),
        }

    def scenario_rates(method: str) -> dict[tuple[str, str, str], float]:
        grouped: dict[tuple[str, str, str], list[int]] = defaultdict(list)
        for row in rows:
            if row["method"] == method and row["adversarial"] == "1":
                key = (row["seed"], row["topology"], row["initial_agents"])
                grouped[key].append(int(row["unsafe_accept"]))
        return {key: sum(values) / len(values) for key, values in grouped.items()}

    epoch_rates = scenario_rates("epochcut")
    for baseline in ("startup-cut", "periodic-5"):
        base_rates = scenario_rates(baseline)
        pairs = {key: (base_rates[key], epoch_rates[key]) for key in epoch_rates}
        estimate, lower, upper = bootstrap_difference(pairs)
        output["paired_bootstrap"][f"{baseline}_minus_epochcut_unsafe_rate"] = {
            "estimate": estimate,
            "ci95": [lower, upper],
            "scenario_pairs": len(pairs),
            "resamples": 10_000,
        }

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    epoch = output["methods"]["epochcut"]
    full = output["methods"]["full-mediation"]
    cost_reduction = 1 - epoch["mean_monitor_cost"] / full["mean_monitor_cost"]
    gates = {
        "zero_unsafe": epoch["unsafe_accept_rate"] <= protocol["claim_gate"]["epochcut_unsafe_accept_rate_adversarial_max"],
        "benign_accept": epoch["benign_accept_rate"] >= protocol["claim_gate"]["epochcut_benign_accept_rate_min"],
        "cost_reduction": cost_reduction >= protocol["claim_gate"]["epochcut_cost_reduction_vs_full_min"],
        "latency": epoch["latency_ms"]["p95"] <= protocol["claim_gate"]["epochcut_p95_admission_latency_ms_max"],
    }
    output["claim_gates"] = gates
    output["all_claim_gates_pass"] = all(gates.values())
    output["cost_reduction_vs_full"] = cost_reduction
    output["raw_sha256"] = hashlib.sha256(args.raw.read_bytes()).hexdigest()
    target = args.raw.parents[1] / "analysis" / "confirmatory_analysis.json"
    target.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
