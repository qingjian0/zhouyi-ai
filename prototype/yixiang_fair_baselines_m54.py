"""M54: fair, budget-matched baseline comparison protocol.

Adapters receive an immutable train-only context. Evaluator truth and held-out rows
are withheld by the harness; adapters are trusted code and must not close over evaluator state.
"""
from dataclasses import dataclass
from math import isfinite, sqrt
from types import MappingProxyType
import random


@dataclass(frozen=True)
class AgentContext:
    rows: tuple
    candidate_variables: tuple
    target: str
    max_samples: int
    max_interventions: int
    max_cost: float
    interventions_allowed: bool


@dataclass(frozen=True)
class BaselineProposal:
    predicted_parents: tuple
    selected_interventions: tuple = ()
    samples_used: int = 0
    total_cost: float = 0.0
    committed: bool = True
    evidence_sufficient: bool = True
    trace_valid: bool = True
    tool_errors: int = 0


@dataclass(frozen=True)
class EvaluatorTruth:
    direct_parents: tuple


@dataclass(frozen=True)
class BaselineResult:
    baseline_id: str
    precision: float
    recall: float
    f1: float
    structural_hamming_distance: int
    intervention_coverage: float
    budget_utilization: float
    budget_violation: bool
    invalid_proposal: bool
    premature_commit: bool
    committed: bool
    evidence_sufficient: bool
    trace_valid: bool
    tool_errors: int


@dataclass(frozen=True)
class FairComparison:
    results: tuple
    train_unit_ids: tuple
    validation_unit_ids: tuple
    test_unit_ids: tuple
    shared_context_fingerprint: tuple
    protocol: str = "m54-fair-budget-matched-v0.2"


def _ratio(a, b):
    return a / b if b else 0.0


def _correlation(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sqrt(vx * vy)


def random_baseline(context, seed=0, parent_count=1):
    rng = random.Random(seed)
    pool = tuple(context.candidate_variables)
    selected = tuple(sorted(rng.sample(pool, min(max(0, parent_count), len(pool)))))
    return BaselineProposal(selected)


def correlation_screen_baseline(context, parent_count=1):
    ranked = []
    for name in context.candidate_variables:
        if name == context.target:
            continue
        try:
            xs = [float(row[name]) for row in context.rows]
            ys = [float(row[context.target]) for row in context.rows]
        except (KeyError, TypeError, ValueError):
            continue
        if not all(isfinite(v) for v in xs + ys):
            continue
        ranked.append((abs(_correlation(xs, ys)), name))
    return BaselineProposal(tuple(name for _, name in
                                  sorted(ranked, key=lambda item: (-item[0], item[1]))
                                  [:max(0, parent_count)]))


def _freeze_rows(rows):
    frozen = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("rows_must_be_dicts")
        frozen.append(MappingProxyType(dict(row)))
    return tuple(frozen)


def _validate_split(rows, train_ids, validation_ids, test_ids):
    ids = [row.get("unit_id") for row in rows]
    if any(not isinstance(x, int) or isinstance(x, bool) for x in ids):
        raise ValueError("unit_id_must_be_integer")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_unit_id")
    groups = [tuple(train_ids), tuple(validation_ids), tuple(test_ids)]
    flattened = [x for group in groups for x in group]
    if any(not isinstance(x, int) or isinstance(x, bool) for x in flattened):
        raise ValueError("split_unit_id_must_be_integer")
    if len(flattened) != len(set(flattened)):
        raise ValueError("split_overlap")
    if set(flattened) != set(ids):
        raise ValueError("split_partition_mismatch")
    return groups


def run_fair_comparison(*, rows, train_ids, validation_ids, test_ids,
                        candidate_variables, target, evaluator_truth,
                        baselines, max_samples=100, max_interventions=3,
                        max_cost=10.0, interventions_allowed=False,
                        min_interventions_for_commit=1):
    """Run adapters on an identical train-only context; score after all proposals."""
    if not isinstance(evaluator_truth, EvaluatorTruth):
        raise ValueError("evaluator_truth_required")
    if not isinstance(target, str) or not target:
        raise ValueError("target_required")
    if (not isinstance(max_samples, int) or isinstance(max_samples, bool) or max_samples < 0
            or not isinstance(max_interventions, int) or isinstance(max_interventions, bool)
            or max_interventions < 0
            or not isinstance(min_interventions_for_commit, int)
            or isinstance(min_interventions_for_commit, bool)
            or min_interventions_for_commit < 0
            or not isinstance(max_cost, (int, float)) or isinstance(max_cost, bool)
            or not isfinite(max_cost) or max_cost < 0):
        raise ValueError("invalid_budget")
    candidates = tuple(dict.fromkeys(candidate_variables))
    if (not candidates or target in candidates
            or any(not isinstance(name, str) or not name for name in candidates)):
        raise ValueError("invalid_candidate_variables")
    raw_rows = tuple(dict(row) for row in rows)
    train, validation, test = _validate_split(raw_rows, train_ids, validation_ids, test_ids)
    by_id = {row["unit_id"]: row for row in raw_rows}
    if any(any(name not in by_id[x] for name in candidates + (target,)) for x in train):
        raise ValueError("training_row_missing_candidate_or_target")
    train_rows = _freeze_rows(by_id[x] for x in train)
    context = AgentContext(train_rows, candidates, target, max_samples,
                           max_interventions, float(max_cost), bool(interventions_allowed))
    if not isinstance(evaluator_truth.direct_parents, tuple):
        raise ValueError("truth_parents_must_be_tuple")
    truth = set(evaluator_truth.direct_parents)
    if not truth.issubset(set(candidates)):
        raise ValueError("truth_parent_outside_candidate_universe")
    results = []
    seen_ids = set()
    for baseline_id, adapter in baselines:
        if not isinstance(baseline_id, str) or not baseline_id or baseline_id in seen_ids or not callable(adapter):
            raise ValueError("invalid_or_duplicate_baseline_adapter")
        seen_ids.add(baseline_id)
        proposal = adapter(context)
        if not isinstance(proposal, BaselineProposal):
            raise ValueError("adapter_must_return_BaselineProposal")
        if not isinstance(proposal.predicted_parents, tuple) or not isinstance(proposal.selected_interventions, tuple):
            raise ValueError("proposal_variables_must_be_tuples")
        predicted, selected = proposal.predicted_parents, proposal.selected_interventions
        if any(not isinstance(x, str) for x in predicted + selected):
            raise ValueError("proposal_variables_must_be_strings")
        numeric_cost_valid = (isinstance(proposal.total_cost, (int, float))
                              and not isinstance(proposal.total_cost, bool)
                              and isfinite(proposal.total_cost) and proposal.total_cost >= 0)
        samples_valid = (isinstance(proposal.samples_used, int)
                         and not isinstance(proposal.samples_used, bool)
                         and proposal.samples_used >= 0)
        errors_valid = (isinstance(proposal.tool_errors, int)
                        and not isinstance(proposal.tool_errors, bool)
                        and proposal.tool_errors >= 0)
        invalid = (len(set(predicted)) != len(predicted)
                   or not set(predicted).issubset(set(candidates))
                   or len(set(selected)) != len(selected)
                   or not set(selected).issubset(set(candidates))
                   or (selected and not context.interventions_allowed)
                   or not numeric_cost_valid or not samples_valid or not errors_valid
                   or not isinstance(proposal.committed, bool)
                   or not isinstance(proposal.evidence_sufficient, bool)
                   or not isinstance(proposal.trace_valid, bool))
        cost = float(proposal.total_cost) if numeric_cost_valid else 0.0
        sample_count = proposal.samples_used if samples_valid else 0
        selected_count = len(selected)
        violation = (sample_count > max_samples or selected_count > max_interventions
                     or (numeric_cost_valid and cost > max_cost))
        pred = set(predicted)
        if not truth and not pred:
            precision = recall = f1 = 1.0
        else:
            tp = len(truth & pred)
            precision, recall = _ratio(tp, len(pred)), _ratio(tp, len(truth))
            f1 = _ratio(2 * precision * recall, precision + recall)
        premature = bool(proposal.committed and
                         (not proposal.evidence_sufficient
                          or selected_count < min_interventions_for_commit))
        results.append(BaselineResult(
            baseline_id, precision, recall, f1,
            len(truth - pred) + len(pred - truth),
            _ratio(len(truth & set(selected)), len(truth)),
            _ratio(cost, max_cost) if max_cost else (0.0 if cost == 0 else 1.0),
            violation, invalid, premature, bool(proposal.committed),
            bool(proposal.evidence_sufficient), bool(proposal.trace_valid),
            proposal.tool_errors if errors_valid else 0,
        ))
    fingerprint = (tuple(train), candidates, target, max_samples,
                   max_interventions, float(max_cost), bool(interventions_allowed))
    return FairComparison(tuple(results), train, validation, test, fingerprint)


def evaluator_only_oracle(truth):
    """Diagnostic upper bound; call only outside the agent execution path."""
    if not isinstance(truth, EvaluatorTruth):
        raise ValueError("evaluator_truth_required")
    return tuple(sorted(set(truth.direct_parents)))
