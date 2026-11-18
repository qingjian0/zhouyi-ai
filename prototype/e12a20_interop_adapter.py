"""Adapters from the E12-A20 reference engines to the shared CPG-EI contract.

The adapter preserves the distinction between exact joint enumeration and
belief-propagation marginals. In particular, BP marginals are never promoted
to a fabricated joint hypothesis.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.cpg_interop import (
    InferenceResult as InteropInferenceResult,
    InferenceStatus,
    digest_json,
)
from prototype.e12a20_factor_graph import InferenceResult as ExactResult
from prototype.e12a20a1_belief_propagation import BPResult, Marginal


@dataclass(frozen=True)
class RankedHypothesis:
    """Adapter-side details omitted from the track-neutral interchange DTO."""

    hypothesis_ref: str
    assignment: tuple[tuple[str, str], ...]
    energy: float


@dataclass(frozen=True)
class E12A20AdapterResult:
    """Shared result plus source-engine diagnostics and optional joint rankings."""

    inference: InteropInferenceResult
    engine: str
    engine_status: str
    ranked_hypotheses: tuple[RankedHypothesis, ...] = ()
    marginals: tuple[Marginal, ...] = ()


def adapt_exact_result(
    result: ExactResult,
    *,
    query_id: str,
    scope: str,
) -> E12A20AdapterResult:
    """Adapt exact finite-domain enumeration without calling energy a probability."""
    if result.status == "BUDGET_EXHAUSTED":
        status = InferenceStatus.BUDGET_EXHAUSTED
    elif result.feasible_assignments == 0:
        status = InferenceStatus.INCONSISTENT
    elif result.feasible_assignments == 1 and result.status == "CONVERGED":
        status = InferenceStatus.IDENTIFIED
    else:
        status = InferenceStatus.AMBIGUOUS

    ranked = tuple(
        RankedHypothesis(
            hypothesis_ref="e12a20:exact:" + digest_json({
                "assignment": hypothesis.assignment,
                "energy": hypothesis.energy,
                "factor_ids": hypothesis.evaluated_factor_ids,
                "evidence_refs": hypothesis.evidence_refs,
            }),
            assignment=hypothesis.assignment,
            energy=hypothesis.energy,
        )
        for hypothesis in result.hypotheses
    )
    refs = tuple(item.hypothesis_ref for item in ranked)
    if status in (InferenceStatus.INCONSISTENT, InferenceStatus.UNKNOWN):
        refs = ()

    budget_used = tuple(sorted((
        ("assignments_examined", result.assignments_examined),
        ("feasible_assignments", result.feasible_assignments),
        ("rejected_assignments", result.rejected_assignments),
        ("state_space_size", result.state_space_size),
    )))
    inference = InteropInferenceResult(
        query_id=query_id,
        scope=scope,
        status=status,
        ranked_hypothesis_refs=refs,
        evidence_refs=tuple(sorted({
            ref for hypothesis in result.hypotheses for ref in hypothesis.evidence_refs
        })),
        budget_used=budget_used,
    )
    return E12A20AdapterResult(
        inference=inference,
        engine="e12a20-exact-enumeration",
        engine_status=result.status,
        ranked_hypotheses=ranked,
    )


def adapt_bp_result(
    result: BPResult,
    *,
    query_id: str,
    scope: str,
) -> E12A20AdapterResult:
    """Adapt BP marginals while refusing to invent a joint assignment ranking."""
    if result.status == "BUDGET_EXHAUSTED":
        status = InferenceStatus.BUDGET_EXHAUSTED
    elif result.status == "INCONSISTENT_MESSAGES":
        status = InferenceStatus.INCONSISTENT
    else:
        # Marginals do not determine a joint MAP assignment, especially on
        # loopy graphs. Preserve uncertainty rather than multiplying modes.
        status = InferenceStatus.AMBIGUOUS

    budget_used = tuple(sorted((
        ("factor_entries", result.factor_entries),
        ("factor_evaluations", result.factor_evaluations),
        ("iterations", result.iterations),
        ("message_updates", result.message_updates),
    )))
    inference = InteropInferenceResult(
        query_id=query_id,
        scope=scope,
        status=status,
        ranked_hypothesis_refs=(),
        evidence_refs=tuple(sorted(set(result.evidence_refs))),
        budget_used=budget_used,
    )
    return E12A20AdapterResult(
        inference=inference,
        engine="e12a20-sum-product-bp",
        engine_status=result.status,
        marginals=result.marginals,
    )
