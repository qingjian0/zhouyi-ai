"""YF-07..10 bounded dynamic-cognition research primitives.

These deterministic symbolic prototypes test four separable capabilities:
change-point/trigger detection, candidate relation generation, context-dependent
sign reversal, and budgeted multi-path rollout. They are not a neural learner,
causal-discovery system, or evidence of classical-theory superiority.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class ChangePoint:
    detected: bool
    index: int | None
    mean_before: float | None
    mean_after: float | None
    effect: float | None
    reason: str


def detect_change_point(
    values: Sequence[float], *, min_segment: int = 3, min_effect: float = 1.0
) -> ChangePoint:
    """Find the largest absolute adjacent-window mean shift.

    This is a bounded retrospective detector, not a causal trigger estimator.
    Thresholds and minimum segment size must be fixed on training data.
    """
    if min_segment < 1 or not math.isfinite(min_effect) or min_effect < 0:
        raise ValueError("invalid detector configuration")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool)
           or not math.isfinite(v) for v in values):
        raise ValueError("values must be finite numbers")
    if len(values) < 2 * min_segment:
        return ChangePoint(False, None, None, None, None, "INSUFFICIENT_SERIES")
    best: tuple[float, int, float, float] | None = None
    for split in range(min_segment, len(values) - min_segment + 1):
        left = sum(values[:split]) / split
        right_values = values[split:]
        right = sum(right_values) / len(right_values)
        effect = right - left
        candidate = (abs(effect), split, left, right)
        if best is None or candidate[0] > best[0]:
            best = candidate
    assert best is not None
    magnitude, split, left, right = best
    if magnitude < min_effect:
        return ChangePoint(False, None, left, right, right-left, "NO_CHANGE_ABOVE_THRESHOLD")
    return ChangePoint(True, split, left, right, right-left, "CHANGE_POINT_DETECTED")


@dataclass(frozen=True)
class RelationCandidate:
    relation_id: str
    operator: str
    features: tuple[str, ...]
    threshold: float
    direction: str


@dataclass(frozen=True)
class RelationScore:
    candidate: RelationCandidate
    balanced_accuracy: float
    support_count: int


def _balanced_accuracy(gold: Sequence[int], pred: Sequence[int]) -> float:
    positives = [i for i, y in enumerate(gold) if y == 1]
    negatives = [i for i, y in enumerate(gold) if y == 0]
    if not positives or not negatives:
        return 0.0
    tpr = sum(pred[i] == 1 for i in positives) / len(positives)
    tnr = sum(pred[i] == 0 for i in negatives) / len(negatives)
    return (tpr + tnr) / 2.0


def _relation_value(row: Mapping[str, float], candidate: RelationCandidate) -> float:
    a = row[candidate.features[0]]
    if candidate.operator == "feature":
        return a
    b = row[candidate.features[1]]
    if candidate.operator == "difference":
        return a - b
    if candidate.operator == "product":
        return a * b
    raise ValueError("unsupported relation operator")


def _predict_relation(row: Mapping[str, float], candidate: RelationCandidate) -> int:
    value = _relation_value(row, candidate)
    return int(value >= candidate.threshold) if candidate.direction == "ge" else int(value <= candidate.threshold)


def generate_relation_candidates(
    rows: Sequence[Mapping[str, float]],
    labels: Sequence[int],
    *,
    max_features: int = 8,
    max_candidates: int = 256,
) -> tuple[RelationScore, ...]:
    """Generate a bounded grammar of unary and pairwise numeric relations.

    Candidate thresholds are derived from support rows only. The returned
    scores are support diagnostics; promotion requires independent Gate data.
    """
    if len(rows) != len(labels) or not rows:
        raise ValueError("rows and labels must be non-empty and equally sized")
    if any(y not in (0, 1) for y in labels) or len(set(labels)) != 2:
        raise ValueError("labels must contain both binary classes")
    keys = tuple(sorted(rows[0]))
    if not keys or len(keys) > max_features or max_candidates < 1:
        raise ValueError("feature or candidate budget invalid")
    for row in rows:
        if tuple(sorted(row)) != keys or any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
            for v in row.values()
        ):
            raise ValueError("all rows need the same finite numeric features")
    raw: list[RelationCandidate] = []
    for feature in keys:
        vals = sorted({float(row[feature]) for row in rows})
        thresholds = [(a+b)/2 for a,b in zip(vals, vals[1:])]
        for threshold in thresholds:
            for direction in ("ge", "le"):
                raw.append(RelationCandidate(
                    f"unary:{feature}:{direction}:{threshold:.12g}",
                    "feature", (feature,), threshold, direction))
    for left, right in itertools.combinations(keys, 2):
        for operator in ("difference", "product"):
            vals = sorted({_relation_value(row, RelationCandidate(
                "tmp", operator, (left, right), 0.0, "ge")) for row in rows})
            for threshold in [(a+b)/2 for a,b in zip(vals, vals[1:])]:
                for direction in ("ge", "le"):
                    raw.append(RelationCandidate(
                        f"{operator}:{left}:{right}:{direction}:{threshold:.12g}",
                        operator, (left, right), threshold, direction))
    # Apply a deterministic round-robin cap across operator families. A plain
    # lexical slice would let high-cardinality operators consume the entire
    # budget and silently exclude later operators (notably product relations).
    by_operator: dict[str, list[RelationCandidate]] = {}
    for candidate in raw:
        by_operator.setdefault(candidate.operator, []).append(candidate)
    for candidates in by_operator.values():
        candidates.sort(key=lambda c: c.relation_id)
    selected: list[RelationCandidate] = []
    operators = sorted(by_operator)
    cursor = 0
    while len(selected) < max_candidates:
        added = False
        for operator in operators:
            candidates = by_operator[operator]
            if cursor < len(candidates):
                selected.append(candidates[cursor])
                added = True
                if len(selected) >= max_candidates:
                    break
        if not added:
            break
        cursor += 1
    raw = selected
    scores = []
    for candidate in raw:
        pred = [_predict_relation(row, candidate) for row in rows]
        scores.append(RelationScore(candidate, _balanced_accuracy(labels, pred), len(rows)))
    return tuple(sorted(scores, key=lambda s: (-s.balanced_accuracy, s.candidate.relation_id)))


@dataclass(frozen=True)
class ReversalEstimate:
    reversed: bool
    context_a: str | None
    context_b: str | None
    mean_a: float | None
    mean_b: float | None
    count_a: int
    count_b: int
    reason: str


def learn_contextual_reversal(
    observations: Sequence[tuple[str, float]], *, min_samples: int = 3, min_effect: float = 0.1
) -> ReversalEstimate:
    """Estimate opposite signed effects across contexts, with sample guards."""
    if min_samples < 1 or not math.isfinite(min_effect) or min_effect < 0:
        raise ValueError("invalid reversal configuration")
    groups: dict[str, list[float]] = {}
    for context, effect in observations:
        if not context or not isinstance(effect, (int, float)) or isinstance(effect, bool) or not math.isfinite(effect):
            raise ValueError("observations require context labels and finite effects")
        groups.setdefault(context, []).append(float(effect))
    eligible = [(name, vals, sum(vals)/len(vals)) for name, vals in groups.items()
                if len(vals) >= min_samples]
    if len(eligible) < 2:
        return ReversalEstimate(False, None, None, None, None,
                                sum(len(v) for v in groups.values()), 0, "INSUFFICIENT_CONTEXT_EVIDENCE")
    pairs = []
    for a, b in itertools.combinations(sorted(eligible, key=lambda x: x[0]), 2):
        if (a[2] > min_effect and b[2] < -min_effect) or (a[2] < -min_effect and b[2] > min_effect):
            pairs.append((a, b))
    if not pairs:
        return ReversalEstimate(False, None, None, None, None,
                                len(eligible[0][1]), len(eligible[1][1]), "NO_SIGN_REVERSAL")
    a, b = pairs[0]
    return ReversalEstimate(True, a[0], b[0], a[2], b[2], len(a[1]), len(b[1]),
                            "CONTEXTUAL_SIGN_REVERSAL")


@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    utility: float
    cost: float


@dataclass(frozen=True)
class PathResult:
    nodes: tuple[str, ...]
    gross_utility: float
    total_cost: float
    net_utility: float


def enumerate_paths(
    transitions: Sequence[Transition],
    *,
    start: str,
    max_depth: int = 4,
    budget: float = 10.0,
    top_k: int = 5,
) -> tuple[PathResult, ...]:
    """Enumerate bounded simple paths; score all before returning top-k.

    This evaluates multiple candidate futures; it does not claim concurrent
    hardware execution or optimality outside the declared transition graph.
    """
    if not start or max_depth < 1 or top_k < 1 or not math.isfinite(budget) or budget < 0:
        raise ValueError("invalid path-search configuration")
    adjacency: dict[str, list[Transition]] = {}
    for edge in transitions:
        if (not edge.source or not edge.target or edge.source == edge.target
            or not math.isfinite(edge.utility) or not math.isfinite(edge.cost) or edge.cost < 0):
            raise ValueError("invalid transition")
        adjacency.setdefault(edge.source, []).append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda e: (e.target, e.cost, -e.utility))
    results: list[PathResult] = []

    def visit(node: str, nodes: tuple[str, ...], utility: float, cost: float, depth: int) -> None:
        if depth and cost <= budget:
            results.append(PathResult(nodes, utility, cost, utility-cost))
        if depth >= max_depth:
            return
        for edge in adjacency.get(node, ()):
            if edge.target in nodes or cost + edge.cost > budget:
                continue
            visit(edge.target, nodes + (edge.target,), utility + edge.utility,
                  cost + edge.cost, depth + 1)

    visit(start, (start,), 0.0, 0.0, 0)
    results.sort(key=lambda p: (-p.net_utility, p.total_cost, p.nodes))
    return tuple(results[:top_k])


# ---------------------------------------------------------------------------
# Unified synthetic capability benchmark (YF-07..10)
# Kept in this module so the research branch can be updated without creating
# files through the default-branch-only contents endpoint.
# ---------------------------------------------------------------------------
def run_synthetic_benchmark(*, seeds: int = 5, start_seed: int = 100) -> dict:
    """Run compact seeded smoke experiments with explicit negative controls.

    This is a synthetic capability smoke test, not a natural-world or causal
    benchmark. Raw per-seed values are returned for auditability.
    """
    import random
    import statistics

    if seeds < 1:
        raise ValueError("seeds must be positive")
    per_seed = []
    for seed in range(start_seed, start_seed + seeds):
        rng = random.Random(seed)

        # YF-07: unannounced mean shifts and independent null sequences.
        detected, false_alarms, errors = 0, 0, []
        for _ in range(12):
            n = 60
            split = rng.randint(20, 40)
            shift = rng.choice((-1.0, 1.0)) * rng.uniform(1.5, 2.5)
            series = [rng.gauss(0, 0.4) + (shift if i >= split else 0)
                      for i in range(n)]
            cp = detect_change_point(series, min_segment=8, min_effect=0.8)
            if cp.detected and cp.index is not None:
                detected += 1
                errors.append(abs(cp.index - split))
            null_series = [rng.gauss(0, 0.4) for _ in range(n)]
            false_alarms += int(detect_change_point(
                null_series, min_segment=8, min_effect=0.8).detected)

        # YF-08: support-only candidate selection; independent test examples.
        support = [{"x": rng.uniform(-2, 2), "y": rng.uniform(-2, 2)}
                   for _ in range(100)]
        support_labels = [int(row["x"] * row["y"] > 0.8) for row in support]
        test = [{"x": rng.uniform(-2, 2), "y": rng.uniform(-2, 2)}
                for _ in range(300)]
        test_labels = [int(row["x"] * row["y"] > 0.8) for row in test]
        candidates = generate_relation_candidates(
            support, support_labels, max_features=2, max_candidates=128)
        selected = candidates[0].candidate
        test_predictions = [_predict_relation(row, selected) for row in test]
        relation_test_score = _balanced_accuracy(test_labels, test_predictions)

        # YF-09: reversal positive condition and same-sign/zero negative controls.
        reversal_hits = same_sign_false = zero_false = 0
        for _ in range(30):
            for condition in ("reversal", "same", "zero"):
                observations = []
                for context in ("A", "B"):
                    effect = (0.8 if context == "A" else -0.8) if condition == "reversal" else (
                        0.8 if condition == "same" else 0.0)
                    observations.extend(
                        (context, effect + rng.gauss(0, 0.3)) for _ in range(12))
                estimate = learn_contextual_reversal(
                    observations, min_samples=8, min_effect=0.25)
                if condition == "reversal":
                    reversal_hits += int(estimate.reversed)
                elif condition == "same":
                    same_sign_false += int(estimate.reversed)
                else:
                    zero_false += int(estimate.reversed)

        # YF-10: compare greedy local choice with finite-graph exhaustive oracle.
        regret_values = []
        for _ in range(20):
            edges = []
            for source, targets in (("s", ("a", "b", "c")),
                                    ("a", ("t",)), ("b", ("t",)), ("c", ("t",))):
                for target in targets:
                    edges.append(Transition(source, target,
                        rng.uniform(0.2, 4.0), rng.uniform(0.1, 0.8)))
            oracle = enumerate_paths(edges, start="s", max_depth=2,
                                     budget=1.5, top_k=1)
            node, seen, utility, cost = "s", {"s"}, 0.0, 0.0
            for _step in range(2):
                feasible = [e for e in edges if e.source == node
                            and e.target not in seen and cost + e.cost <= 1.5]
                if not feasible:
                    break
                edge = max(feasible, key=lambda e: (e.utility-e.cost, -e.cost))
                node, utility, cost = edge.target, utility+edge.utility, cost+edge.cost
                seen.add(node)
            greedy_net = utility-cost
            regret_values.append(max(0.0, oracle[0].net_utility-greedy_net)
                                  if oracle else 0.0)

        per_seed.append({
            "seed": seed,
            "YF07": {
                "detection_rate": detected / 12,
                "mean_localization_error": statistics.mean(errors) if errors else None,
                "null_false_alarm_rate": false_alarms / 12,
            },
            "YF08": {
                "support_selected_test_balanced_accuracy": relation_test_score,
                "selected_operator": selected.operator,
                "support_rows": len(support),
                "test_rows": len(test),
            },
            "YF09": {
                "reversal_detection_rate": reversal_hits / 30,
                "same_sign_false_reversal_rate": same_sign_false / 30,
                "zero_effect_false_reversal_rate": zero_false / 30,
            },
            "YF10": {
                "mean_greedy_regret_vs_finite_graph_oracle":
                    statistics.mean(regret_values),
            },
        })
    return {
        "benchmark": "YF07_YF10_compact_synthetic_smoke_suite",
        "seeds": seeds,
        "start_seed": start_seed,
        "results": per_seed,
        "limitations": [
            "Synthetic distributions only; not evidence of natural cognition or general intelligence.",
            "YF07 covers abrupt mean shifts and null controls, not gradual drift or causal triggers.",
            "YF08 target product relation is inside the candidate grammar; no open-world discovery claim.",
            "YF09 uses supplied contexts and observational effect values; no causal identification.",
            "YF10 uses known finite graphs and an oracle with the same graph; no learned world model.",
        ],
    }
