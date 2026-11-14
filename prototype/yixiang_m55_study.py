"""Pre-registered M55 multi-seed synthetic study and reproducible report writer."""
import argparse
import csv
import json
import os
import time
from collections import defaultdict
from statistics import mean

from prototype.yixiang_experiments_m55 import METHODS, SCENARIOS, run_paired_suite
from prototype.yixiang_stats_m55 import (
    benjamini_hochberg_adjust,
    holm_adjust,
    paired_bootstrap_interval,
    paired_sign_flip_pvalue,
    wilson_interval,
)


DEFAULT_SAMPLE_SIZES = (120, 240, 480)
DEFAULT_SEEDS = tuple(range(1000, 1050))


def _edge_counts(record, candidate_count=3):
    predicted = set(record["predicted_parents"])
    truth = set(record["true_parents"])
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    tn = candidate_count - tp - fp - fn
    return tp, fp, fn, tn


def summarize(records, *, bootstrap_repetitions=5000, seed=20261114):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record["scenario"], record["sample_size"], record["method"])].append(record)

    summaries = []
    for (scenario, n, method), rows in sorted(grouped.items()):
        counts = [_edge_counts(row) for row in rows]
        tp = sum(item[0] for item in counts)
        fp = sum(item[1] for item in counts)
        fn = sum(item[2] for item in counts)
        tn = sum(item[3] for item in counts)
        f1_values = [row["f1"] for row in rows]
        fpr_ci = wilson_interval(fp, fp + tn) if fp + tn else None
        power_ci = wilson_interval(tp, tp + fn) if tp + fn else None
        summaries.append({
            "scenario": scenario, "sample_size": n, "method": method,
            "paired_seeds": len(rows), "mean_precision": mean(row["precision"] for row in rows),
            "mean_recall": mean(row["recall"] for row in rows),
            "mean_f1": mean(f1_values), "mean_shd": mean(row["shd"] for row in rows),
            "false_positive_edges": fp, "true_negative_edges": tn,
            "false_positive_rate": fp / (fp + tn) if fp + tn else None,
            "false_positive_rate_wilson95": fpr_ci,
            "true_positive_edges": tp, "false_negative_edges": fn,
            "power": tp / (tp + fn) if tp + fn else None,
            "power_wilson95": power_ci,
            "invalid_proposals": sum(bool(row["invalid_proposal"]) for row in rows),
            "budget_violations": sum(bool(row["budget_violation"]) for row in rows),
        })

    lookup = {(row["scenario"], row["sample_size"], row["method"], row["seed"]): row for row in records}
    contrasts = []
    for scenario in SCENARIOS:
        for n in sorted({row["sample_size"] for row in records}):
            for comparator in ("random", "correlation"):
                differences = []
                for seed_value in sorted({row["seed"] for row in records
                                          if row["scenario"] == scenario
                                          and row["sample_size"] == n}):
                    a = lookup[(scenario, n, "pc_skeleton", seed_value)]["f1"]
                    b = lookup[(scenario, n, comparator, seed_value)]["f1"]
                    differences.append(a - b)
                interval = paired_bootstrap_interval(
                    differences, repetitions=bootstrap_repetitions,
                    seed=seed + n + len(differences),
                )
                test = paired_sign_flip_pvalue(
                    differences, repetitions=max(20000, bootstrap_repetitions),
                    seed=seed + n + len(differences) + 1,
                )
                contrasts.append({
                    "scenario": scenario, "sample_size": n,
                    "method_a": "pc_skeleton", "method_b": comparator,
                    "metric": "f1", **interval, **test,
                })

    raw_p = [row["p_value"] for row in contrasts]
    holm = holm_adjust(raw_p)
    bh = benjamini_hochberg_adjust(raw_p)
    for index, row in enumerate(contrasts):
        row["holm_adjusted_p"] = holm[index]
        row["bh_adjusted_p"] = bh[index]

    return {
        "protocol": "M55-pre-registered-synthetic-study-v0.2",
        "interpretation": {
            "paired_difference": "pc_skeleton minus comparator; positive favors PC-style F1",
            "scope": "synthetic target-parent recovery only; not real-world causal identification",
            "limitations": [
                "Only Random, marginal correlation, and target-local linear-Gaussian PC-style are executable comparators.",
                "Quadratic, latent-confounding, and collider-selection cases intentionally violate or challenge baseline assumptions.",
                "Synthetic scenario frequencies are design choices, not estimates of real-world prevalence.",
                "Bootstrap and sign-flip inference assume independent paired seeds; scenario generator correctness remains a separate assumption.",
                "A target-local skeleton does not orient edges and is not full PC/FCI.",
            ],
        },
        "scenario_summaries": summaries,
        "paired_f1_contrasts": contrasts,
        "records": len(records),
    }


def run_study(*, seeds=DEFAULT_SEEDS, sample_sizes=DEFAULT_SAMPLE_SIZES,
              scenarios=SCENARIOS):
    seeds = tuple(seeds)
    sample_sizes = tuple(sample_sizes)
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds_must_be_nonempty_and_unique")
    if any(not isinstance(s, int) or isinstance(s, bool) for s in seeds):
        raise ValueError("seeds_must_be_integers")
    if not sample_sizes or any(not isinstance(n, int) or isinstance(n, bool) or n < 80
                               for n in sample_sizes):
        raise ValueError("invalid_sample_sizes")
    records = []
    for n in sample_sizes:
        records.extend(run_paired_suite(seeds=seeds, n=n, scenarios=scenarios))
    return records


def write_outputs(records, report, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    raw_path = os.path.join(output_dir, "m55_raw_records.jsonl")
    with open(raw_path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\\n")
    report_path = os.path.join(output_dir, "m55_summary.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    csv_path = os.path.join(output_dir, "m55_summary.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        rows = report["scenario_summaries"]
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return {"raw": raw_path, "summary_json": report_path, "summary_csv": csv_path}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=1000)
    parser.add_argument("--sample-sizes", type=int, nargs="+", default=list(DEFAULT_SAMPLE_SIZES))
    parser.add_argument("--output-dir", default="artifacts/m55")
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    args = parser.parse_args()
    started = time.perf_counter()
    seeds = range(args.start_seed, args.start_seed + args.seeds)
    records = run_study(seeds=seeds, sample_sizes=args.sample_sizes)
    report = summarize(records, bootstrap_repetitions=args.bootstrap_repetitions)
    report["execution"] = {
        "elapsed_seconds": time.perf_counter() - started,
        "seed_start": args.start_seed, "seed_count": args.seeds,
        "sample_sizes": args.sample_sizes, "scenarios": list(SCENARIOS),
        "methods": list(METHODS),
    }
    paths = write_outputs(records, report, args.output_dir)
    print(json.dumps({"outputs": paths, "execution": report["execution"],
                      "scenario_summaries": report["scenario_summaries"],
                      "paired_f1_contrasts": report["paired_f1_contrasts"]},
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
