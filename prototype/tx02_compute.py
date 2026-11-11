"""TX-02D compute accounting and selective-prediction utilities."""
from __future__ import annotations
import math
from typing import Iterable, Sequence
from prototype.tx02_state_encoders import build_codebook

def feature_dimension(family: str, cardinality: int, embedding_dim: int = 6) -> int:
    if family in ("LEARNED", "FIXED_RANDOM"):
        if type(embedding_dim) is not int or embedding_dim < 1:
            raise ValueError("embedding_dim must be a positive integer")
        return embedding_dim
    return build_codebook(cardinality, "PERMUTED" if family == "PERMUTED" else family).dimension

def estimate_forward_macs(family: str, cardinality: int, hidden_size: int,
                          support_size: int, query_count: int,
                          candidate_count: int | None = None,
                          embedding_dim: int = 6) -> int:
    """Forward MAC proxy for one episode; excludes nonlinearities and backward work."""
    for name, value in (("hidden_size", hidden_size), ("support_size", support_size),
                        ("query_count", query_count)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if candidate_count is None:
        candidate_count = cardinality
    if type(candidate_count) is not int or candidate_count < 1:
        raise ValueError("candidate_count must be a positive integer")
    d = feature_dimension(family, cardinality, embedding_dim)
    return support_size * query_count * candidate_count * hidden_size * (6 * d + 1)

def choose_hidden_size_for_compute_budget(family: str, cardinality: int,
        target_forward_macs: int, support_size: int, query_count: int,
        candidate_count: int | None = None, embedding_dim: int = 6,
        max_hidden_size: int = 4096) -> tuple[int, int]:
    if type(target_forward_macs) is not int or target_forward_macs < 1:
        raise ValueError("target_forward_macs must be a positive integer")
    if type(max_hidden_size) is not int or max_hidden_size < 1:
        raise ValueError("max_hidden_size must be a positive integer")
    unit = estimate_forward_macs(family, cardinality, 1, support_size,
                                  query_count, candidate_count, embedding_dim)
    hidden = min(max_hidden_size, target_forward_macs // unit)
    if hidden < 1:
        raise ValueError(f"compute budget {target_forward_macs} is below minimum {unit}")
    return hidden, hidden * unit

def select_representation(validation_results: dict[str, dict]) -> dict:
    """Select one family using validation-only metrics and deterministic tie breaks.

    Required fields per family: accuracy, nll, forward_macs, parameter_count.
    Locked-test metrics must never be supplied here.
    """
    if not validation_results:
        raise ValueError("validation_results must not be empty")
    ranked = []
    for family, metrics in validation_results.items():
        try:
            accuracy = float(metrics["accuracy"])
            nll = float(metrics["nll"])
            macs = int(metrics["forward_macs"])
            params = int(metrics["parameter_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid validation metrics for {family}") from exc
        if (not math.isfinite(accuracy) or not 0.0 <= accuracy <= 1.0
                or not math.isfinite(nll) or nll < 0.0 or macs < 0 or params < 0):
            raise ValueError(f"out-of-range validation metrics for {family}")
        ranked.append(( -accuracy, nll, macs, params, str(family)))
    ranked.sort()
    winner = ranked[0]
    return {
        "selected_family": winner[4],
        "selection_source": "validation_only",
        "tie_break_order": ["higher_accuracy", "lower_nll", "lower_forward_macs",
                            "lower_parameter_count", "lexicographic_family"],
        "validation_rank": [
            {"family": row[4], "accuracy": -row[0], "nll": row[1],
             "forward_macs": row[2], "parameter_count": row[3]}
            for row in ranked
        ],
    }


def probability_metrics(probability_rows: Sequence[Sequence[float]],
                        targets: Sequence[int], bins: int = 10) -> dict:
    """Multiclass NLL/Brier and fixed-width top-label ECE."""
    if len(probability_rows) != len(targets) or not targets:
        raise ValueError("probability_rows and targets must have equal non-zero length")
    if type(bins) is not int or bins < 1:
        raise ValueError("bins must be a positive integer")
    n, k = len(targets), len(probability_rows[0])
    if k < 2:
        raise ValueError("at least two classes are required")
    nll = brier = correct = 0.0
    confidence_rows = []
    for probs, target in zip(probability_rows, targets):
        if len(probs) != k or type(target) is not int or not 0 <= target < k:
            raise ValueError("inconsistent class dimensions or invalid target")
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in probs):
            raise ValueError("probabilities must be finite and in [0,1]")
        if abs(sum(probs) - 1.0) > 1e-6:
            raise ValueError("each probability row must sum to one")
        pred = max(range(k), key=lambda i: probs[i])
        conf, hit = probs[pred], float(pred == target)
        correct += hit
        nll -= math.log(max(probs[target], 1e-15))
        brier += sum((p - float(i == target)) ** 2 for i, p in enumerate(probs))
        confidence_rows.append((conf, hit))
    ece, details = 0.0, []
    for index in range(bins):
        lo, hi = index / bins, (index + 1) / bins
        selected = [(c, h) for c, h in confidence_rows
                    if lo <= c < hi or (index == bins - 1 and c == 1.0)]
        if selected:
            avg_conf = sum(c for c, _ in selected) / len(selected)
            avg_acc = sum(h for _, h in selected) / len(selected)
            ece += len(selected) / n * abs(avg_conf - avg_acc)
            details.append({"bin": index, "count": len(selected),
                            "mean_confidence": avg_conf, "accuracy": avg_acc})
    return {"count": n, "accuracy": correct / n, "nll": nll / n,
            "brier_multiclass": brier / n, "ece_top_label_fixed_width": ece,
            "ece_bins": bins, "ece_bin_details": details}

def choose_abstention_threshold(probability_rows: Sequence[Sequence[float]],
        targets: Sequence[int], max_selective_risk: float) -> dict:
    """Select maximum validation coverage under an empirical risk cap."""
    if not math.isfinite(max_selective_risk) or not 0 <= max_selective_risk <= 1:
        raise ValueError("max_selective_risk must be in [0,1]")
    if len(probability_rows) != len(targets) or not targets:
        raise ValueError("probability_rows and targets must have equal non-zero length")
    ranked = []
    for probs, target in zip(probability_rows, targets):
        if not probs or type(target) is not int or not 0 <= target < len(probs):
            raise ValueError("invalid probability row or target")
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in probs):
            raise ValueError("invalid probability")
        if abs(sum(probs) - 1.0) > 1e-6:
            raise ValueError("probabilities must sum to one")
        pred = max(range(len(probs)), key=lambda i: probs[i])
        ranked.append((max(probs), int(pred == target)))
    ranked.sort(key=lambda x: x[0], reverse=True)
    best = {"threshold": math.nextafter(1.0, math.inf), "coverage": 0.0,
            "selective_risk": None, "accepted": 0}
    correct = 0
    for count, (confidence, hit) in enumerate(ranked, 1):
        correct += hit
        risk = 1.0 - correct / count
        if risk <= max_selective_risk:
            best = {"threshold": confidence, "coverage": count / len(ranked),
                    "selective_risk": risk, "accepted": count}
    return best

def apply_abstention(probability_rows: Iterable[Sequence[float]],
                     threshold: float) -> tuple[int | None, ...]:
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    result = []
    for probs in probability_rows:
        if not probs:
            raise ValueError("probability rows must not be empty")
        pred = max(range(len(probs)), key=lambda i: probs[i])
        result.append(pred if max(probs) >= threshold else None)
    return tuple(result)
