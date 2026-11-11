"""XSL-5 controlled cross-domain transfer benchmark (synthetic v0.1).

This benchmark isolates lexical overlap, relation-structure matching, and
scope/evidence-aware multi-perspective selection. Synthetic labels are known
by construction; results are not evidence of real-world Yi-Xiang validity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CandidateView:
    view_id: str
    relation_signature: frozenset[str]
    required_context: frozenset[str]
    counterexample_context: frozenset[str]
    evidence_polarity: str
    is_valid_transfer: bool


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    lexical_terms: frozenset[str]
    views: tuple[CandidateView, ...]


@dataclass(frozen=True)
class TransferCase:
    case_id: str
    query_terms: frozenset[str]
    query_relations: frozenset[str]
    context: frozenset[str]
    candidates: tuple[Candidate, ...]
    accepted_candidate_ids: frozenset[str]


@dataclass(frozen=True)
class Prediction:
    case_id: str
    selected_candidate_id: str | None
    reason: str


@dataclass(frozen=True)
class Metrics:
    cases: int
    valid_cases: int
    no_transfer_cases: int
    selected: int
    correct_selected: int
    false_transfer: int
    abstained_correctly: int
    coverage: float
    precision: float
    recall: float
    negative_transfer_rate: float
    abstention_accuracy: float


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def lexical_baseline(case: TransferCase) -> Prediction:
    """Select the candidate with greatest surface-term overlap."""
    best = max(
        case.candidates,
        key=lambda item: (_jaccard(case.query_terms, item.lexical_terms), item.candidate_id),
    )
    return Prediction(case.case_id, best.candidate_id, "MAX_LEXICAL_OVERLAP")


def structural_baseline(case: TransferCase) -> Prediction:
    """Select the candidate with greatest relation overlap, ignoring scope."""
    def score(candidate: Candidate) -> tuple[float, str]:
        best_view = max(
            (_jaccard(case.query_relations, view.relation_signature)
             for view in candidate.views),
            default=0.0,
        )
        return best_view, candidate.candidate_id

    best = max(case.candidates, key=score)
    return Prediction(case.case_id, best.candidate_id, "MAX_RELATION_OVERLAP")


def perspective_aware_selector(case: TransferCase) -> Prediction:
    """Require a scoped, non-countered SUPPORTS view before transferring."""
    eligible: list[tuple[float, str]] = []
    for candidate in case.candidates:
        view_scores = []
        for view in candidate.views:
            if view.evidence_polarity != "SUPPORTS":
                continue
            if not view.required_context.issubset(case.context):
                continue
            if view.counterexample_context & case.context:
                continue
            view_scores.append(_jaccard(case.query_relations, view.relation_signature))
        if view_scores:
            eligible.append((max(view_scores), candidate.candidate_id))
    if not eligible:
        return Prediction(case.case_id, None, "NO_SCOPED_SUPPORTED_VIEW")
    _, selected = max(eligible)
    return Prediction(case.case_id, selected, "BEST_ELIGIBLE_VIEW")


def evaluate(
    cases: Iterable[TransferCase],
    predictor,
) -> tuple[Metrics, tuple[Prediction, ...]]:
    items = tuple(cases)
    predictions = tuple(predictor(case) for case in items)
    by_id = {prediction.case_id: prediction for prediction in predictions}
    if len(by_id) != len(items):
        raise ValueError("case_id values must be unique")
    valid_cases = sum(bool(case.accepted_candidate_ids) for case in items)
    no_transfer = len(items) - valid_cases
    selected_predictions = [
        (case, by_id[case.case_id])
        for case in items
        if by_id[case.case_id].selected_candidate_id is not None
    ]
    correct = sum(
        prediction.selected_candidate_id in case.accepted_candidate_ids
        for case, prediction in selected_predictions
    )
    false_transfer = len(selected_predictions) - correct
    abstained_correctly = sum(
        by_id[case.case_id].selected_candidate_id is None
        and not case.accepted_candidate_ids
        for case in items
    )
    selected = len(selected_predictions)
    return Metrics(
        cases=len(items),
        valid_cases=valid_cases,
        no_transfer_cases=no_transfer,
        selected=selected,
        correct_selected=correct,
        false_transfer=false_transfer,
        abstained_correctly=abstained_correctly,
        coverage=selected / len(items) if items else 0.0,
        precision=correct / selected if selected else 0.0,
        recall=correct / valid_cases if valid_cases else 0.0,
        negative_transfer_rate=false_transfer / selected if selected else 0.0,
        abstention_accuracy=(
            abstained_correctly / no_transfer if no_transfer else 1.0
        ),
    )


def build_synthetic_suite(
    positive_count: int = 24, negative_count: int = 24
) -> tuple[TransferCase, ...]:
    """Build deterministic, balanced cases with lexical and scope traps."""
    if positive_count < 1 or negative_count < 1:
        raise ValueError("both positive_count and negative_count must be >= 1")
    result = []
    for index in range(positive_count + negative_count):
        positive = index < positive_count
        case_id = f"case-{index:03d}"
        context = frozenset({"active_flow", "bounded_channel"}) if positive else frozenset(
            {"stagnant_pool", "blocked_channel"}
        )
        valid_view = CandidateView(
            view_id=f"view-valid-{index}",
            relation_signature=frozenset({"source_to_channel", "channel_to_receiver"}),
            required_context=frozenset({"active_flow", "bounded_channel"}),
            counterexample_context=frozenset({"stagnant_pool", "blocked_channel"}),
            evidence_polarity="SUPPORTS",
            is_valid_transfer=positive,
        )
        lexical_trap_view = CandidateView(
            view_id=f"view-lexical-{index}",
            relation_signature=frozenset({"isolated_storage"}),
            required_context=frozenset({"historical_metaphor"}),
            counterexample_context=frozenset(),
            evidence_polarity="SUPPORTS",
            is_valid_transfer=False,
        )
        candidate_valid = Candidate(
            candidate_id="candidate-structural",
            lexical_terms=frozenset({"flow", "channel", "transfer", f"rare{index}"}),
            views=(valid_view,),
        )
        candidate_lexical = Candidate(
            candidate_id="candidate-lexical",
            lexical_terms=frozenset({"flow", "channel", "transfer", "receiver", "surface"}),
            views=(lexical_trap_view,),
        )
        candidate_unknown = Candidate(
            candidate_id="candidate-unknown",
            lexical_terms=frozenset({"unrelated", f"noise{index}"}),
            views=(CandidateView(
                view_id=f"view-unknown-{index}",
                relation_signature=frozenset({"source_to_channel"}),
                required_context=frozenset(),
                counterexample_context=frozenset(),
                evidence_polarity="UNKNOWN",
                is_valid_transfer=False,
            ),),
        )
        accepted = frozenset({"candidate-structural"}) if positive else frozenset()
        result.append(TransferCase(
            case_id=case_id,
            query_terms=frozenset({"flow", "channel", "transfer", "receiver"}),
            query_relations=frozenset({"source_to_channel", "channel_to_receiver"}),
            context=context,
            candidates=(candidate_valid, candidate_lexical, candidate_unknown),
            accepted_candidate_ids=accepted,
        ))
    return tuple(result)


def metrics_as_dict(metrics: Metrics) -> dict[str, int | float]:
    return {
        "cases": metrics.cases,
        "valid_cases": metrics.valid_cases,
        "no_transfer_cases": metrics.no_transfer_cases,
        "selected": metrics.selected,
        "correct_selected": metrics.correct_selected,
        "false_transfer": metrics.false_transfer,
        "abstained_correctly": metrics.abstained_correctly,
        "coverage": round(metrics.coverage, 4),
        "precision": round(metrics.precision, 4),
        "recall": round(metrics.recall, 4),
        "negative_transfer_rate": round(metrics.negative_transfer_rate, 4),
        "abstention_accuracy": round(metrics.abstention_accuracy, 4),
    }


def run_suite() -> dict[str, dict[str, int | float]]:
    cases = build_synthetic_suite()
    return {
        "lexical": metrics_as_dict(evaluate(cases, lexical_baseline)[0]),
        "structural": metrics_as_dict(evaluate(cases, structural_baseline)[0]),
        "perspective_aware": metrics_as_dict(evaluate(cases, perspective_aware_selector)[0]),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_suite(), indent=2, sort_keys=True))
