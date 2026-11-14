"""M54: fair, budget-matched baseline comparison protocol.

All candidate methods receive the same immutable training observations and budget.
Evaluator truth and held-out rows are never included in the agent-facing context.
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
    trace_valid: bool
    tool_errors: int


@dataclass(frozen=True)
class FairComparison:
    results: tuple
    train_unit_ids: tuple
    validation_unit_ids: tuple
    test_unit_ids: tuple
    shared_context_fingerprint: tuple
    protocol: str = "m54-fair-budget-matched-v0.1"


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
    rows = context.rows
    ranked = []
    for name in context.candidate_variables:
        if name == context.target:
            continue
        try:
            xs = [float(row[name]) for row in rows]
            ys = [float(row[context.target]) for row in rows]
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
    if len(flattened) != len(set(flattened)):
        raise ValueError("split_overlap")
    if set(flattened) != set(ids):
        raise ValueError("split_partition_mismatch")
    return groups


def run_fair_comparison(*, rows, train_ids, validation_ids, test_ids,
                        candidate_variables, target, evaluator_truth,
                        baselines, max_samples=100, max_interventions=3,
                        max_cost=10.0, interventions_allowed=False):
    """Run adapters on an identical train-only context; score only after execution."""
    if not isinstance(evaluator_truth, EvaluatorTruth):
        raise ValueError("evaluator_truth_required")
    if not isinstance(target, str) or not target:
        raise ValueError("target_required")
    if not isfinite(max_cost) or max_cost < 0 or max_samples < 0 or max_interventions < 0:
        raise ValueError("invalid_budget")
    candidates = tuple(dict.fromkeys(candidate_variables))
    if target in candidates or not candidates:
        raise ValueError("invalid_candidate_variables")
    raw_rows = tuple(dict(row) for row in rows)
    train, validation, test = _validate_split(raw_rows, train_ids, validation_ids, test_ids)
    by_id = {row["unit_id"]: row for row in raw_rows}
    train_rows = _freeze_rows(by_id[x] for x in train)
    # Validation/test rows are deliberately withheld from all candidate methods.
    context = AgentContext(train_rows, candidates, target, max_samples,
                           max_interventions, float(max_cost), bool(interventions_allowed))
    truth = set(evaluator_truth.direct_parents)
    if not truth.issubset(set(candidates)):
        raise ValueError("truth_parent_outside_candidate_universe")
    results = []
    for baseline_id, adapter in baselines:
        if not isinstance(baseline_id, str) or not baseline_id or not callable(adapter):
            raise ValueError("invalid_baseline_adapter")
        proposal = adapter(context)
        if not isinstance(proposal, BaselineProposal):
            raise ValueError("adapter_must_return_BaselineProposal")
        predicted = tuple(proposal.predicted_parents)
        selected = tuple(proposal.selected_interventions)
        invalid = (len(set(predicted)) != len(predicted)
                   or not set(predicted).issubset(set(candidates))
                   or len(set(selected)) != len(selected)
                   or not set(selected).issubset(set(candidates))
                   or (selected and not context.interventions_allowed)
                   or not isfinite(proposal.total_cost) or proposal.total_cost < 0
                   or not isinstance(proposal.samples_used, int)
                   or isinstance(proposal.samples_used, bool) or proposal.samples_used < 0)
        violation = (proposal.samples_used > max_samples
                     or len(selected) > max_interventions
                     or proposal.total_cost > max_cost)
        pred = set(predicted)
        if not truth and not pred:
            precision = recall = f1 = 1.0
        else:
            tp = len(truth & pred)
            precision, recall = _ratio(tp, len(pred)), _ratio(tp, len(truth))
            f1 = _ratio(2 * precision * recall, precision + recall)
        results.append(BaselineResult(
            baseline_id, precision, recall, f1,
            len(truth - pred) + len(pred - truth),
            _ratio(len(truth & set(selected)), len(truth)),
            _ratio(proposal.total_cost, max_cost) if max_cost else (0.0 if proposal.total_cost == 0 else 1.0),
            violation, invalid, bool(proposal.trace_valid), max(0, int(proposal.tool_errors)),
        ))
    fingerprint = (tuple(train), candidates, target, max_samples,
                   max_interventions, float(max_cost), bool(interventions_allowed))
    return FairComparison(tuple(results), train, validation, test, fingerprint)


def evaluator_only_oracle(truth):
    """Diagnostic upper bound; call only outside the agent execution path."""
    if not isinstance(truth, EvaluatorTruth):
        raise ValueError("evaluator_truth_required")
    return tuple(sorted(set(truth.direct_parents)))
