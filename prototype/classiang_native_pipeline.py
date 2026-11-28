"""Unified symbolic cognition cycle projected into native computation graphs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from prototype.classiang_native import (
    CompositionResult, EvidenceRef, SymbolGraph, compose_relations,
)
from prototype.classiang_native_adapter import observation_to_symbol_graph
from prototype.classiang_native_learning import (
    NativeCompositionScorer, NativeRoleBindingModel, rank_compositions,
)
from prototype.classiang_pipeline import (
    ClassiangCycleRequest, ClassiangCycleResult, run_classiang_cycle,
)


@dataclass(frozen=True)
class NativeClassiangCycleResult:
    cognition: ClassiangCycleResult
    graph: SymbolGraph
    compositions: CompositionResult
    ranked_compositions: tuple


def run_native_classiang_cycle(
    request: ClassiangCycleRequest,
    evidence_catalog: Mapping[str, EvidenceRef],
    *,
    model: NativeCompositionScorer | NativeRoleBindingModel | None = None,
    max_depth: int = 3,
    max_candidates: int = 1000,
) -> NativeClassiangCycleResult:
    """Run the existing classiang cognition cycle and native graph operators.

    All observations, labels, role mappings, and evidence remain caller-supplied.
    This function orchestrates explicit symbolic operations; it does not infer
    raw perception, generate evidence, or claim semantic/causal truth.
    """
    cognition = run_classiang_cycle(request)
    hypothesis = (
        cognition.revision.active_hypothesis
        if cognition.revision is not None
        else cognition.induction.hypothesis
    )
    graph = observation_to_symbol_graph(
        request.query_observation, evidence_catalog, hypothesis=hypothesis,
    )
    compositions = compose_relations(
        graph, max_depth=max_depth, max_candidates=max_candidates,
    )
    ranked = (
        rank_compositions(
            graph, model, max_depth=max_depth, max_candidates=max_candidates,
        )
        if model is not None else ()
    )
    return NativeClassiangCycleResult(
        cognition=cognition,
        graph=graph,
        compositions=compositions,
        ranked_compositions=ranked,
    )
