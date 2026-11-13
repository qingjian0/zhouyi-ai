"""M7 orchestration baseline connecting M3-M6 without collapsing evidence layers.

The pipeline coordinates existing transparent modules. It does not infer
observations, manufacture residuals, or promote novelty proposals.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.yixiang_active_observation import (
    HypothesisPrior, ObservationCandidate, ObservationSelection,
    select_observation,
)
from prototype.yixiang_competing_hypotheses import (
    ArbitrationResult, XiangCandidate, arbitrate,
)
from prototype.yixiang_counterfactual import (
    ConditionIntervention, ConditionValue, ConditionalMapping,
    CounterfactualAssessment, assess_counterfactual,
)
from prototype.yixiang_novelty import (
    NoveltyProposal, ResidualCase, propose_novel_structures,
)


@dataclass(frozen=True)
class M7Input:
    candidates: tuple[XiangCandidate, ...]
    priors: tuple[HypothesisPrior, ...]
    observation_candidates: tuple[ObservationCandidate, ...]
    mappings: tuple[ConditionalMapping, ...] = ()
    mapping_to_candidate: tuple[tuple[str, str], ...] = ()
    baseline_conditions: tuple[ConditionValue, ...] = ()
    interventions: tuple[tuple[str, tuple[ConditionIntervention, ...]], ...] = ()
    residual_cases: tuple[ResidualCase, ...] = ()
    known_signatures: tuple[tuple[tuple[str, str, str], ...], ...] = ()


@dataclass(frozen=True)
class M7Result:
    arbitration: ArbitrationResult
    counterfactuals: tuple[tuple[str, CounterfactualAssessment], ...]
    observation_selection: ObservationSelection | None
    novelty_proposals: tuple[NoveltyProposal, ...]
    stages_executed: tuple[str, ...]
    evidence_boundary: str = "observations_and_interventions_are_not_promoted_automatically"


def run_m7(inputs: M7Input) -> M7Result:
    """Run M3 arbitration, declared M4 checks, conditional M5 selection, M6 proposals."""
    if not isinstance(inputs, M7Input):
        raise ValueError("inputs must be an M7Input")

    arbitration = arbitrate(inputs.candidates)
    candidate_ids = {candidate.candidate_id for candidate in inputs.candidates}
    prior_ids = {prior.hypothesis_id for prior in inputs.priors}
    if candidate_ids != prior_ids:
        raise ValueError("M5 prior hypothesis ids must exactly match M3 candidate ids")

    mapping_ids = [mapping.mapping_id for mapping in inputs.mappings]
    if len(mapping_ids) != len(set(mapping_ids)):
        raise ValueError("mapping ids must be unique")
    candidate_mapping = dict(inputs.mapping_to_candidate)
    if len(candidate_mapping) != len(inputs.mapping_to_candidate):
        raise ValueError("each mapping may be assigned to only one candidate")
    if set(candidate_mapping) - set(mapping_ids):
        raise ValueError("mapping_to_candidate references an unknown mapping")
    if set(candidate_mapping.values()) - candidate_ids:
        raise ValueError("mapping_to_candidate references an unknown candidate")

    intervention_map = dict(inputs.interventions)
    if len(intervention_map) != len(inputs.interventions):
        raise ValueError("intervention mapping ids must be unique")
    if set(intervention_map) - set(mapping_ids):
        raise ValueError("interventions reference an unknown mapping")

    counterfactuals = []
    for mapping in sorted(inputs.mappings, key=lambda item: item.mapping_id):
        candidate_id = candidate_mapping.get(mapping.mapping_id)
        if candidate_id is None:
            raise ValueError("every M4 mapping must be associated with an M3 candidate")
        assessment = assess_counterfactual(
            mapping,
            inputs.baseline_conditions,
            intervention_map.get(mapping.mapping_id, ()),
        )
        counterfactuals.append((candidate_id, assessment))

    # M5 is used when M3 leaves competing, contested, or underdetermined
    # explanations. It ranks prospective observations only.
    observation_selection = None
    if arbitration.unresolved and inputs.observation_candidates:
        observation_selection = select_observation(
            inputs.priors, inputs.observation_candidates
        )

    # M6 consumes only explicitly supplied, already annotated residual cases.
    # It never manufactures residuals from M3/M4/M5 outputs.
    novelty_proposals = propose_novel_structures(
        inputs.residual_cases,
        known_signatures=inputs.known_signatures,
    ) if inputs.residual_cases else ()

    stages = ["M3"]
    if inputs.mappings:
        stages.append("M4")
    if observation_selection is not None:
        stages.append("M5")
    if novelty_proposals:
        stages.append("M6")

    return M7Result(
        arbitration,
        tuple(counterfactuals),
        observation_selection,
        novelty_proposals,
        tuple(stages),
    )
