"""Observation-grounded referent identity checks inspired by Xunzi, Zhengming.

This is an engineering operationalization, not a claim that Xunzi anticipated
modern object tracking or a complete metaphysics of identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class PerceptualModality(str, Enum):
    SIGHT = "sight"
    HEARING = "hearing"
    TASTE = "taste"
    SMELL = "smell"
    TOUCH = "touch"
    INTROSPECTION = "introspection"
    MIXED = "mixed"


class ObservationSource(str, Enum):
    DIRECT_SENSORY = "direct_sensory"
    INSTRUMENTAL = "instrumental"
    TESTIMONY = "testimony"
    TEXTUAL_RECORD = "textual_record"
    MODEL_OUTPUT = "model_output"


class ReferentDecision(str, Enum):
    SAME_REFERENT = "same_referent"
    DISTINCT_REFERENTS = "distinct_referents"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class ObservationRecord:
    observation_id: str
    observed_features: Tuple[str, ...]
    modality: PerceptualModality
    source: ObservationSource
    context: str
    timepoint: str
    referent_anchor: str = ""


@dataclass(frozen=True)
class ReferentPairEvidence:
    first: ObservationRecord
    second: ObservationRecord
    continuity_refs: Tuple[str, ...] = ()
    separation_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReferentAssessment:
    first_observation_id: str
    second_observation_id: str
    decision: ReferentDecision
    reason_codes: Tuple[str, ...]
    appearance_relation: str
    transformation_detected: bool = False
    identity_from_appearance_alone: bool = False


def _validate_observation(obs: ObservationRecord) -> None:
    if not isinstance(obs.observation_id, str) or not obs.observation_id.strip():
        raise ValueError("observation_id is required")
    if not isinstance(obs.observed_features, tuple) or any(
        not isinstance(x, str) or not x.strip() for x in obs.observed_features
    ):
        raise ValueError("observed_features must be a tuple of non-empty strings")
    if not isinstance(obs.modality, PerceptualModality):
        raise ValueError("modality must use PerceptualModality")
    if not isinstance(obs.source, ObservationSource):
        raise ValueError("source must use ObservationSource")
    for field in ("context", "timepoint", "referent_anchor"):
        if not isinstance(getattr(obs, field), str):
            raise ValueError(f"{field} must be a string")


def _validate_refs(name: str, refs: Tuple[str, ...]) -> None:
    if not isinstance(refs, tuple) or any(
        not isinstance(x, str) or not x.strip() for x in refs
    ):
        raise ValueError(f"{name} must be a tuple of non-empty strings")


def assess_referent_pair(pair: ReferentPairEvidence) -> ReferentAssessment:
    """Distinguish appearance similarity from evidence of referent continuity."""
    _validate_observation(pair.first)
    _validate_observation(pair.second)
    _validate_refs("continuity_refs", pair.continuity_refs)
    _validate_refs("separation_refs", pair.separation_refs)

    first, second = pair.first, pair.second
    shared = set(first.observed_features).intersection(second.observed_features)
    appearance_relation = (
        "same_recorded_features" if first.observed_features == second.observed_features
        else "partially_shared_features" if shared
        else "different_recorded_features"
    )
    reasons = []

    perceptual_sources = {ObservationSource.DIRECT_SENSORY, ObservationSource.INSTRUMENTAL}
    if first.source not in perceptual_sources or second.source not in perceptual_sources:
        reasons.append("NON_PERCEPTUAL_SOURCE_CANNOT_GROUND_IDENTITY")
    if not first.observed_features or not second.observed_features:
        reasons.append("OBSERVED_FEATURES_MISSING")
    if pair.continuity_refs and pair.separation_refs:
        reasons.append("CONTINUITY_AND_SEPARATION_EVIDENCE_CONFLICT")
    if reasons:
        decision = ReferentDecision.ABSTAIN
    elif (
        first.referent_anchor and second.referent_anchor
        and first.referent_anchor == second.referent_anchor
        and pair.continuity_refs
    ):
        decision = ReferentDecision.SAME_REFERENT
    elif (
        first.referent_anchor and second.referent_anchor
        and first.referent_anchor != second.referent_anchor
        and pair.separation_refs
    ):
        decision = ReferentDecision.DISTINCT_REFERENTS
    else:
        reasons.append("IDENTITY_REQUIRES_CONTINUITY_OR_SEPARATION_EVIDENCE")
        decision = ReferentDecision.ABSTAIN

    return ReferentAssessment(
        first_observation_id=first.observation_id,
        second_observation_id=second.observation_id,
        decision=decision,
        reason_codes=tuple(reasons),
        appearance_relation=appearance_relation,
        transformation_detected=(
            decision == ReferentDecision.SAME_REFERENT
            and first.observed_features != second.observed_features
        ),
        identity_from_appearance_alone=False,
    )
