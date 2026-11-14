"""M55.1 repaired study runner.

All baseline cardinalities are protocol constants, never derived from evaluator
truth. The requested sample size denotes training observations; validation and
test observations are additional, disjoint units.
"""
import argparse
import json
import math
import os
import random
import time
from collections import defaultdict
from statistics import mean

from prototype.yixiang_fair_baselines_m54 import (
    EvaluatorTruth, correlation_screen_baseline, random_baseline,
    run_fair_comparison,
)
from prototype.yixiang_pc_skeleton_m54 import pc_skeleton_baseline
from prototype.yixiang_stats_m55 import (
    holm_adjust, paired_bootstrap_interval, paired_sign_flip_pvalue,
)

SCENARIOS = (
    "linear_gaussian", "linear_weak", "linear_near_null", "linear_null",
    "nonlinear_quadratic", "nonlinear_interaction", "non_gaussian_noise",
    "latent_common_cause", "selection_collider", "measurement_error_proxy",
    "collinear_linear", "mechanism_heterogeneity",
)
METHODS = ("random_k1", "correlation_k1", "random_k2", "correlation_k2", "pc_skeleton")
FIXED_CARDINALITIES = (1, 2)


def _laplace(rng, scale=0.7):
    magnitude = rng.expovariate(1.0 / scale)
    return magnitude if rng.random() < 0.5 else -magnitude


def _training_companion_sizes(train_n):
    # Keep validation and test disjoint and approximately 15% each of all rows.
    companion = max(20, math.ceil(train_n * 0.15 / 0.70))
    return companion, companion


def generate_scenario(name, *, train_n=120, seed=0):
    if name not in SCENARIOS:
        raise ValueError("unknown_scenario")
    if not isinstance(train_n, int) or isinstance(train_n, bool) or train_n < 80:
        raise ValueError("train_n_must_be_integer_at_least_80")
    validation_n, test_n = _training_companion_sizes(train_n)
    total_n = train_n + validation_n + test_n
    rng = random.Random(seed)
    regime_rng = random.Random(seed ^ 0x5A17C9E3)
    rows, regimes = [], []
    while len(rows) < total_n:
        i = len(rows)
        x, z, w = (rng.gauss(0.0, 1.0) for _ in range(3))
        regime = None
        if name == "linear_gaussian":
            y, parents, values = 1.25*x + rng.gauss(0, .8), ("x",), (x,z,w)
        elif name == "linear_weak":
            y, parents, values = .30*x + rng.gauss(0, .8), ("x",), (x,z,w)
        elif name == "linear_near_null":
            y, parents, values = .10*x + rng.gauss(0, .8), ("x",), (x,z,w)
        elif name == "linear_null":
            y, parents, values = rng.gauss(0, .8), (), (x,z,w)
        elif name == "nonlinear_quadratic":
            y, parents, values = x*x - 1 + rng.gauss(0, .6), ("x",), (x,z,w)
        elif name == "nonlinear_interaction":
            y, parents, values = x*z + rng.gauss(0, .6), ("x","z"), (x,z,w)
        elif name == "non_gaussian_noise":
            y, parents, values = 1.1*x + _laplace(rng), ("x",), (x,z,w)
        elif name == "latent_common_cause":
            latent = rng.gauss(0, 1)
            x = latent + rng.gauss(0, .35)
            y = 1.3*latent + rng.gauss(0, .35)
            parents, values = (), (x,z,w)
        elif name == "selection_collider":
            y = rng.gauss(0, 1)
            if x + y + rng.gauss(0, .2) < .9:
                continue
            parents, values = (), (x,z,w)
        elif name == "measurement_error_proxy":
            latent = rng.gauss(0, 1)
            x = latent + rng.gauss(0, .9)
            y = 1.1*latent + rng.gauss(0, .5)
            parents, values = (), (x,z,w)
        elif name == "collinear_linear":
            z = x + rng.gauss(0, .05)
            y = x + rng.gauss(0, .8)
            parents, values = ("x",), (x,z,w)
        else:
            # Hidden regime is sampled independently of unit order/identifier.
            regime = regime_rng.randrange(2)
            sign = 1.0 if regime == 0 else -1.0
            y = sign*x + rng.gauss(0, .4)
            parents, values = ("x",), (x,z,w)
        rows.append({"unit_id": i, "x": values[0], "z": values[1],
                     "w": values[2], "y": y})
        regimes.append(regime)
    evaluator_metadata = {"hidden_regime_by_unit": tuple(regimes)}
    return rows, tuple(parents), evaluator_metadata


def run_cell(scenario, train_n, seed):
    rows, parents, evaluator_metadata = generate_scenario(
        scenario, train_n=train_n, seed=seed
    )
    validation_n, test_n = _training_companion_sizes(train_n)
    train_end = train_n
    validation_end = train_n + validation_n
    captured = {}

    def capture(name, adapter):
        def wrapped(context):
            proposal = adapter(context)
            captured[name] = tuple(proposal.predicted_parents)
            return proposal
        return wrapped

    # Fixed cardinalities are declared protocol settings, not inferred from truth.
    baselines = []
    for k in FIXED_CARDINALITIES:
        baselines.append((
            f"random_k{k}",
            capture(f"random_k{k}", lambda context, k=k:
                    random_baseline(context, seed=seed + 7919*k, parent_count=k)),
        ))
        baselines.append((
            f"correlation_k{k}",
            capture(f"correlation_k{k}", lambda context, k=k:
                    correlation_screen_baseline(context, parent_count=k)),
        ))
    baselines.append(("pc_skeleton", capture("pc_skeleton", pc_skeleton_baseline)))

    comparison = run_fair_comparison(
        rows=rows,
        train_ids=range(train_end),
        validation_ids=range(train_end, validation_end),
        test_ids=range(validation_end, validation_end + test_n),
        candidate_variables=("x", "z", "w"),
        target="y",
        evaluator_truth=EvaluatorTruth(parents),
        baselines=tuple(baselines),
        max_samples=train_n,
        max_interventions=0,
        max_cost=0.0,
        interventions_allowed=False,
        min_interventions_for_commit=0,
    )
    records = []
    for result in comparison.results:
        records.append({
            "scenario": scenario,
            "seed": seed,
            "sample_size": train_n,
            "train_sample_size": train_n,
            "validation_sample_size": validation_n,
            "test_sample_size": test_n,
            "total_sample_size": len(rows),
            "method": result.baseline_id,
            "predicted_parents": captured[result.baseline_id],
            "true_parents": parents,
            "precision": result.precision,
            "recall": result.recall,
            "f1": result.f1,
            "shd": result.structural_hamming_distance,
            "budget_violation": result.budget_violation,
            "invalid_proposal": result.invalid_proposal,
        })
    # Evaluator metadata never enters AgentContext or adapter closures.
    return records, evaluator_metadata


def run_study(*, seeds=range(1000, 1050), train_sample_sizes=(120,240,480),
              scenarios=SCENARIOS):
    seeds = tuple(seeds)
    train_sample_sizes = tuple(train_sample_sizes)
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds_must_be_nonempty_and_unique")
    if any(not isinstance(s, int) or isinstance(s, bool) for s in seeds):
        raise ValueError("seeds_must_be_integers")
    if not train_sample_sizes or any(not isinstance(n, int) or isinstance(n, bool) or n < 80
                                     for n in train_sample_sizes):
        raise ValueError("invalid_train_sample_sizes")
    records, metadata = [], {}
    for scenario in scenarios:
        if scenario not in SCENARIOS:
            raise ValueError("unknown_scenario")
        for train_n in train_sample_sizes:
            for seed in seeds:
                cell, evaluator_metadata = run_cell(scenario, train_n, seed)
                records.extend(cell)
                if scenario == "mechanism_heterogeneity":
                    metadata[f"{scenario}:{train_n}:{seed}"] = evaluator_metadata
    return records, metadata


def summarize(records, *, bootstrap_repetitions=5000, seed=20261114):
    grouped = defaultdict(list)
    paired = defaultdict(dict)
    for row in records:
        grouped[(row["scenario"], row["sample_size"], row["method"])].append(row)
        paired[(row["scenario"], row["sample_size"], row["seed"])][row["method"]] = row
    summaries = []
    for (scenario, train_n, method), rows in sorted(grouped.items()):
        summaries.append({
            "scenario": scenario, "train_sample_size": train_n,
            "total_sample_size": rows[0]["total_sample_size"],
            "method": method, "paired_seeds": len(rows),
            "mean_precision": mean(r["precision"] for r in rows),
            "mean_recall": mean(r["recall"] for r in rows),
            "mean_f1": mean(r["f1"] for r in rows),
            "mean_shd": mean(r["shd"] for r in rows),
            "invalid_proposals": sum(bool(r["invalid_proposal"]) for r in rows),
            "budget_violations": sum(bool(r["budget_violation"]) for r in rows),
        })
    contrasts = []
    p_values = []
    for scenario in sorted({r["scenario"] for r in records}):
        for train_n in sorted({r["sample_size"] for r in records}):
            for comparator in ("random_k1", "correlation_k1", "random_k2", "correlation_k2"):
                diffs = []
                for seed_value in sorted({r["seed"] for r in records
                                          if r["scenario"] == scenario and r["sample_size"] == train_n}):
                    cell = paired[(scenario, train_n, seed_value)]
                    if "pc_skeleton" not in cell or comparator not in cell:
                        raise ValueError("incomplete_paired_method_cell")
                    diffs.append(cell["pc_skeleton"]["f1"] - cell[comparator]["f1"])
                interval = paired_bootstrap_interval(
                    diffs, repetitions=bootstrap_repetitions,
                    seed=seed + train_n + len(diffs),
                )
                # Sign-flip is reported as sensitivity only; the report states its assumptions.
                sign_flip = paired_sign_flip_pvalue(
                    diffs, repetitions=max(20000, bootstrap_repetitions),
                    seed=seed + train_n + len(diffs) + 1,
                )
                contrasts.append({
                    "scenario": scenario, "train_sample_size": train_n,
                    "method_a": "pc_skeleton", "method_b": comparator,
                    "metric": "f1", **interval,
                    "sign_flip_sensitivity": sign_flip,
                })
                p_values.append(sign_flip["p_value"])
    adjusted = holm_adjust(p_values)
    for i, row in enumerate(contrasts):
        row["holm_adjusted_p_sensitivity_only"] = adjusted[i]
    return {
        "protocol": "M55.1-repaired-synthetic-study-v0.1",
        "inference_note": (
            "Paired bootstrap intervals summarize mean seed-level differences. "
            "Sign-flip p-values are sensitivity analyses only and require an "
            "exchangeability/symmetry justification; they are not assumption-free."
        ),
        "limitations": [
            "All scenarios are synthetic and do not establish real-world causal identification.",
            "Only fixed-k random/correlation baselines and a target-local linear-Gaussian PC-style baseline are executed.",
            "Fixed k=1 and k=2 are protocol settings, not oracle-selected per scenario.",
            "No Transformer, SCM learner, or Zhouyi agent is included.",
        ],
        "scenario_summaries": summaries,
        "paired_f1_contrasts": contrasts,
        "records": len(records),
    }


def write_outputs(records, evaluator_metadata, report, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    raw_path = os.path.join(output_dir, "m55_1_raw_records.jsonl")
    with open(raw_path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    metadata_path = os.path.join(output_dir, "m55_1_evaluator_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as handle:
        json.dump(evaluator_metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
    report_path = os.path.join(output_dir, "m55_1_summary.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return {"raw": raw_path, "evaluator_metadata": metadata_path, "summary": report_path}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=1000)
    parser.add_argument("--train-sample-sizes", type=int, nargs="+", default=[120,240,480])
    parser.add_argument("--output-dir", default="artifacts/m55_1")
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    args = parser.parse_args()
    started = time.perf_counter()
    records, metadata = run_study(
        seeds=range(args.start_seed, args.start_seed + args.seeds),
        train_sample_sizes=args.train_sample_sizes,
    )
    report = summarize(records, bootstrap_repetitions=args.bootstrap_repetitions)
    report["execution"] = {
        "elapsed_seconds": time.perf_counter() - started,
        "seed_start": args.start_seed, "seed_count": args.seeds,
        "train_sample_sizes": args.train_sample_sizes,
        "scenarios": list(SCENARIOS), "methods": list(METHODS),
    }
    paths = write_outputs(records, metadata, report, args.output_dir)
    print(json.dumps({"outputs": paths, "execution": report["execution"],
                      "scenario_summaries": report["scenario_summaries"],
                      "paired_f1_contrasts": report["paired_f1_contrasts"]},
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
