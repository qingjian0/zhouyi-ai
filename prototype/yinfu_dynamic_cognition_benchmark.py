"""YF-07..10 multi-seed synthetic benchmark.

This benchmark measures narrow algorithmic capabilities on generated worlds.
It is not a natural-world, language, causal, or neural-architecture benchmark.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import asdict, dataclass

from prototype.yinfu_dynamic_cognition import (
    Transition, detect_change_point, enumerate_paths,
    generate_relation_candidates, learn_contextual_reversal,
)


@dataclass(frozen=True)
class Metric:
    mean: float
    stdev: float


def _metric(values: list[float]) -> Metric:
    return Metric(statistics.mean(values), statistics.pstdev(values) if len(values) > 1 else 0.0)


def _balanced_accuracy(gold: list[int], pred: list[int]) -> float:
    pos = [i for i, y in enumerate(gold) if y == 1]
    neg = [i for i, y in enumerate(gold) if y == 0]
    if not pos or not neg:
        return 0.0
    return 0.5 * (
        sum(pred[i] == 1 for i in pos) / len(pos)
        + sum(pred[i] == 0 for i in neg) / len(neg)
    )


def benchmark_yf07(seed: int, episodes: int = 30) -> dict:
    rng = random.Random(seed)
    localization_errors: list[float] = []
    false_alarm = 0
    detected_changes = 0
    fixed_errors: list[float] = []
    for _ in range(episodes):
        n = 80
        split = rng.randint(25, 55)
        shift = rng.choice((-1.0, 1.0)) * rng.uniform(1.5, 3.0)
        noise = [rng.gauss(0.0, 0.5) for _ in range(n)]
        values = [noise[i] + (shift if i >= split else 0.0) for i in range(n)]
        result = detect_change_point(values, min_segment=10, min_effect=0.8)
        if result.detected and result.index is not None:
            detected_changes += 1
            localization_errors.append(abs(result.index - split))
        fixed_errors.append(abs(n // 2 - split))

        # Null episode: calibrated with the same fixed threshold.
        null_values = [rng.gauss(0.0, 0.5) for _ in range(n)]
        null_result = detect_change_point(null_values, min_segment=10, min_effect=0.8)
        false_alarm += int(null_result.detected)
    return {
        "episodes": episodes,
        "change_detection_rate": detected_changes / episodes,
        "mean_localization_error_when_detected": (
            statistics.mean(localization_errors) if localization_errors else None
        ),
        "fixed_midpoint_mean_localization_error": statistics.mean(fixed_errors),
        "null_false_alarm_rate": false_alarm / episodes,
        "limitation": "Synthetic piecewise-constant mean shifts; no gradual drift or causal trigger inference.",
    }


def _make_relation_data(rng: random.Random, n: int) -> tuple[list[dict[str, float]], list[int]]:
    rows = [{"x": rng.uniform(-2.0, 2.0), "y": rng.uniform(-2.0, 2.0)} for _ in range(n)]
    labels = [int(row["x"] * row["y"] > 0.9) for row in rows]
    return rows, labels


def benchmark_yf08(seed: int, episodes: int = 20) -> dict:
    rng = random.Random(seed)
    pair_scores: list[float] = []
    unary_scores: list[float] = []
    for _ in range(episodes):
        support_x, support_y = _make_relation_data(rng, 120)
        test_x, test_y = _make_relation_data(rng, 500)
        candidates = generate_relation_candidates(
            support_x, support_y, max_features=2, max_candidates=256
        )
        if not candidates:
            continue
        # The best support-ranked candidate is frozen before test labels are read.
        selected = candidates[0].candidate
        pair_pred = []
        for row in test_x:
            a = row[selected.features[0]]
            if selected.operator == "feature":
                value = a
            elif selected.operator == "difference":
                value = a - row[selected.features[1]]
            else:
                value = a * row[selected.features[1]]
            pair_pred.append(int(value >= selected.threshold) if selected.direction == "ge"
                             else int(value <= selected.threshold))
        unary = next((s.candidate for s in candidates if s.candidate.operator == "feature"), None)
        if unary is not None:
            unary_pred = [
                int(row[unary.features[0]] >= unary.threshold) if unary.direction == "ge"
                else int(row[unary.features[0]] <= unary.threshold)
                for row in test_x
            ]
            unary_scores.append(_balanced_accuracy(test_y, unary_pred))
        pair_scores.append(_balanced_accuracy(test_y, pair_pred))
    return {
        "episodes": len(pair_scores),
        "best_support_candidate_test_balanced_accuracy": (
            _metric(pair_scores).__dict__ if pair_scores else None
        ),
        "best_unary_candidate_test_balanced_accuracy": (
            _metric(unary_scores).__dict__ if unary_scores else None
        ),
        "test_examples_per_episode": 500,
        "limitation": "Fixed two-feature product target; grammar contains the generating operator, so this is not open-ended discovery.",
    }


def benchmark_yf09(seed: int, episodes: int = 100) -> dict:
    rng = random.Random(seed)
    cases = {"reversal": [], "same_sign": [], "zero": []}
    for case in cases:
        detected = 0
        for _ in range(episodes):
            data = []
            for context in ("A", "B"):
                if case == "reversal":
                    effect = 0.8 if context == "A" else -0.8
                elif case == "same_sign":
                    effect = 0.8
                else:
                    effect = 0.0
                data.extend((context, effect + rng.gauss(0.0, 0.35)) for _ in range(20))
            estimate = learn_contextual_reversal(data, min_samples=10, min_effect=0.25)
            detected += int(estimate.reversed)
        cases[case].append(detected / episodes)
    return {
        "episodes_per_condition": episodes,
        "reversal_detection_rate": cases["reversal"][0],
        "same_sign_false_reversal_rate": cases["same_sign"][0],
        "zero_effect_false_reversal_rate": cases["zero"][0],
        "limitation": "Two observed contexts with Gaussian effect noise; descriptive sign estimation, not causal identification.",
    }


def _greedy_path(edges: list[Transition], start: str, max_depth: int, budget: float) -> tuple[float, float]:
    node = start
    seen = {start}
    utility = cost = 0.0
    for _ in range(max_depth):
        feasible = [e for e in edges if e.source == node and e.target not in seen
                    and cost + e.cost <= budget]
        if not feasible:
            break
        edge = max(feasible, key=lambda e: (e.utility - e.cost, -e.cost, e.target))
        utility += edge.utility
        cost += edge.cost
        node = edge.target
        seen.add(node)
    return utility - cost, cost


def benchmark_yf10(seed: int, episodes: int = 50) -> dict:
    rng = random.Random(seed)
    regrets = []
    greedy_scores = []
    optimal_scores = []
    for _ in range(episodes):
        # Layered DAG, with stochastic edge values and positive costs.
        layers = [["s"], [f"a{i}" for i in range(4)],
                  [f"b{i}" for i in range(4)], ["t"]]
        edges: list[Transition] = []
        for layer_index in range(len(layers) - 1):
            for source in layers[layer_index]:
                for target in layers[layer_index + 1]:
                    edges.append(Transition(
                        source, target,
                        utility=rng.uniform(0.0, 5.0),
                        cost=rng.uniform(0.2, 1.0),
                    ))
        paths = enumerate_paths(edges, start="s", max_depth=3, budget=3.0, top_k=1)
        if not paths:
            continue
        greedy, _ = _greedy_path(edges, "s", 3, 3.0)
        optimum = paths[0].net_utility
        greedy_scores.append(greedy)
        optimal_scores.append(optimum)
        regrets.append(max(0.0, optimum - greedy))
    return {
        "episodes": len(regrets),
        "greedy_mean_net_utility": _metric(greedy_scores).__dict__ if greedy_scores else None,
        "enumeration_oracle_mean_net_utility": _metric(optimal_scores).__dict__ if optimal_scores else None,
        "mean_greedy_regret": statistics.mean(regrets) if regrets else None,
        "oracle_scope": "Exhaustive simple paths in the same generated finite DAG, depth and cost budget.",
        "limitation": "Known transition graph and deterministic edge values; no learned or uncertain world model.",
    }


def run(seeds: int = 20, start_seed: int = 100) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    rows = []
    for seed in range(start_seed, start_seed + seeds):
        rows.append({
            "seed": seed,
            "YF07": benchmark_yf07(seed),
            "YF08": benchmark_yf08(seed),
            "YF09": benchmark_yf09(seed),
            "YF10": benchmark_yf10(seed),
        })
    return {
        "benchmark": "YF07_YF10_synthetic_capability_suite",
        "seeds": seeds,
        "seed_start": start_seed,
        "results": rows,
        "interpretation": "Report per-seed results and uncertainty. These tasks validate only the specified synthetic capability slices.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seeds, args.start_seed)
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
