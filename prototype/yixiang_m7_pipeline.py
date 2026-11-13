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

    tuple_fields = (
        ("candidates", inputs.candidates), ("priors", inputs.priors),
        ("observation_candidates", inputs.observation_candidates),
        ("mappings", inputs.mappings), ("mapping_to_candidate", inputs.mapping_to_candidate),
        ("baseline_conditions", inputs.baseline_conditions), ("interventions", inputs.interventions),
        ("residual_cases", inputs.residual_cases), ("known_signatures", inputs.known_signatures),
    )
    for name, value in tuple_fields:
        if not isinstance(value, tuple):
            raise ValueError(f"{name} must be a tuple")
    if not inputs.candidates:
        raise ValueError("at least one M3 candidate is required")
    arbitration = arbitrate(inputs.candidates)
    eligible_candidate_ids = {
        assessment.candidate_id for assessment in arbitration.assessments
        if assessment.status.value != "rejected"
    }
    prior_id_list = []
    prior_probability_sum = 0.0
    for prior in inputs.priors:
        if not isinstance(prior, HypothesisPrior):
            raise ValueError("priors must contain HypothesisPrior values")
        prior.validate()
        prior_id_list.append(prior.hypothesis_id)
        prior_probability_sum += float(prior.probability)
    prior_ids = set(prior_id_list)
    if len(prior_id_list) != len(prior_ids):
        raise ValueError("M5 prior hypothesis ids must be unique")
    if eligible_candidate_ids != prior_ids:
        raise ValueError("M5 prior hypothesis ids must exactly match non-rejected M3 candidate ids")
    if inputs.priors and abs(prior_probability_sum - 1.0) > 1e-9:
        raise ValueError("M5 prior probabilities must sum to 1")

    for pair in inputs.mapping_to_candidate:
        if (not isinstance(pair, tuple) or len(pair) != 2
                or any(not isinstance(value, str) or not value.strip() for value in pair)):
            raise ValueError("mapping_to_candidate entries must be non-empty string pairs")
    for pair in inputs.interventions:
        if (not isinstance(pair, tuple) or len(pair) != 2
                or not isinstance(pair[0], str) or not pair[0].strip()
                or not isinstance(pair[1], tuple)):
            raise ValueError("interventions entries must be (mapping_id, tuple) pairs")

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
    if arbitration.unresolved and inputs.observation_candidates and inputs.priors:
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
