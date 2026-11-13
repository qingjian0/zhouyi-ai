"""Evidence-bounded generation of provisional yixiang candidates."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class EvidenceKind(str, Enum):
    DIRECT_OBSERVATION = "direct_observation"
    TEXTUAL_ATTESTATION = "textual_attestation"
    REPORTED_OBSERVATION = "reported_observation"
    INFERENCE = "inference"
    MODEL_OUTPUT = "model_output"


class CandidateDecision(str, Enum):
    PROPOSED = "proposed"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class ObservedFeature:
    dimension: str
    value: str
    modality: str
    evidence_ref: str
    evidence_kind: EvidenceKind


@dataclass(frozen=True)
class ObservedRelation:
    predicate: str
    subject_role: str
    object_role: str
    evidence_ref: str
    evidence_kind: EvidenceKind


@dataclass(frozen=True)
class Observation:
    observation_id: str
    domain: str
    features: Tuple[ObservedFeature, ...]
    relations: Tuple[ObservedRelation, ...]
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class FeatureMatch:
    dimension: str
    value: str
    modality: str
    source_evidence_ref: str
    target_evidence_ref: str
    source_evidence_kind: EvidenceKind
    target_evidence_kind: EvidenceKind


@dataclass(frozen=True)
class RelationMatch:
    predicate: str
    subject_role: str
    object_role: str
    source_evidence_ref: str
    target_evidence_ref: str
    source_evidence_kind: EvidenceKind
    target_evidence_kind: EvidenceKind


@dataclass(frozen=True)
class YixiangCandidate:
    candidate_id: str
    source_observation_id: str
    target_observation_id: str
    source_domain: str
    target_domain: str
    decision: CandidateDecision
    shared_features: Tuple[FeatureMatch, ...]
    shared_relations: Tuple[RelationMatch, ...]
    non_shared_feature_dimensions: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    claim_ceiling: Tuple[str, ...] = (
        "recorded_feature_correspondence_only",
        "recorded_relation_pattern_only",
    )
    prohibited_shortcuts: Tuple[str, ...] = (
        "entity_identity", "taxonomic_membership", "functional_equivalence",
        "causal_equivalence", "universal_generalization",
    )


_ELIGIBLE_EVIDENCE = {
    EvidenceKind.DIRECT_OBSERVATION,
    EvidenceKind.TEXTUAL_ATTESTATION,
    EvidenceKind.REPORTED_OBSERVATION,
}


def _required(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _validate_observation(obs: Observation) -> None:
    if not isinstance(obs, Observation):
        raise ValueError("observations must contain Observation values")
    _required(obs.observation_id, "observation_id")
    _required(obs.domain, "domain")
    if not isinstance(obs.evidence_refs, tuple) or not obs.evidence_refs:
        raise ValueError("evidence_refs must be a non-empty tuple")
    for ref in obs.evidence_refs:
        _required(ref, "evidence_ref")
    if len(set(obs.evidence_refs)) != len(obs.evidence_refs):
        raise ValueError("evidence_refs must be unique")
    if not isinstance(obs.features, tuple) or not isinstance(obs.relations, tuple):
        raise ValueError("features and relations must be tuples")

    feature_keys = []
    for item in obs.features:
        if not isinstance(item, ObservedFeature):
            raise ValueError("features must contain ObservedFeature")
        for field in ("dimension", "value", "modality", "evidence_ref"):
            _required(getattr(item, field), f"feature.{field}")
        if not isinstance(item.evidence_kind, EvidenceKind):
            raise ValueError("feature.evidence_kind must use EvidenceKind")
        if item.evidence_ref not in obs.evidence_refs:
            raise ValueError("feature evidence_ref is not linked to observation")
        feature_keys.append((item.dimension, item.value, item.modality))
    if len(set(feature_keys)) != len(feature_keys):
        raise ValueError("feature signatures must be unique within an observation")

    relation_keys = []
    for item in obs.relations:
        if not isinstance(item, ObservedRelation):
            raise ValueError("relations must contain ObservedRelation")
        for field in ("predicate", "subject_role", "object_role", "evidence_ref"):
            _required(getattr(item, field), f"relation.{field}")
        if not isinstance(item.evidence_kind, EvidenceKind):
            raise ValueError("relation.evidence_kind must use EvidenceKind")
        if item.evidence_ref not in obs.evidence_refs:
            raise ValueError("relation evidence_ref is not linked to observation")
        relation_keys.append((item.predicate, item.subject_role, item.object_role))
    if len(set(relation_keys)) != len(relation_keys):
        raise ValueError("relation signatures must be unique within an observation")


def generate_yixiang_candidates(
    observations: Tuple[Observation, ...],
) -> Tuple[YixiangCandidate, ...]:
    """Compare exact typed signatures; never infer identity, function, or cause."""
    if not isinstance(observations, tuple):
        raise ValueError("observations must be a tuple")
    for obs in observations:
        _validate_observation(obs)
    ids = [obs.observation_id for obs in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("observation_id values must be unique")

    ordered = sorted(observations, key=lambda item: item.observation_id)
    candidates = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            right_features = {(x.dimension, x.value, x.modality): x for x in right.features}
            potential_features, supported_features = [], []
            for item in left.features:
                other = right_features.get((item.dimension, item.value, item.modality))
                if other is None:
                    continue
                potential_features.append((item, other))
                if item.evidence_kind in _ELIGIBLE_EVIDENCE and other.evidence_kind in _ELIGIBLE_EVIDENCE:
                    supported_features.append(FeatureMatch(
                        item.dimension, item.value, item.modality,
                        item.evidence_ref, other.evidence_ref,
                        item.evidence_kind, other.evidence_kind,
                    ))

            right_relations = {(x.predicate, x.subject_role, x.object_role): x for x in right.relations}
            potential_relations, supported_relations = [], []
            for item in left.relations:
                other = right_relations.get((item.predicate, item.subject_role, item.object_role))
                if other is None:
                    continue
                potential_relations.append((item, other))
                if item.evidence_kind in _ELIGIBLE_EVIDENCE and other.evidence_kind in _ELIGIBLE_EVIDENCE:
                    supported_relations.append(RelationMatch(
                        item.predicate, item.subject_role, item.object_role,
                        item.evidence_ref, other.evidence_ref,
                        item.evidence_kind, other.evidence_kind,
                    ))

            if not potential_features and not potential_relations:
                continue
            left_dims = {x.dimension for x in left.features}
            right_dims = {x.dimension for x in right.features}
            shared_dims = {x.dimension for x, _ in potential_features}
            reasons = []
            if not supported_features and not supported_relations:
                reasons.append("MATCHES_LACK_ELIGIBLE_PRIMARY_OR_TEXTUAL_EVIDENCE")
            if left.domain != right.domain:
                reasons.append("CROSS_DOMAIN_CANDIDATE_REQUIRES_SEPARATE_SCOPE_REVIEW")
            if potential_features and not supported_features:
                reasons.append("FEATURE_MATCH_SUPPORTED_ONLY_BY_INFERENCE_OR_MODEL_OUTPUT")
            if potential_relations and not supported_relations:
                reasons.append("RELATION_MATCH_SUPPORTED_ONLY_BY_INFERENCE_OR_MODEL_OUTPUT")
            decision = CandidateDecision.PROPOSED if supported_features or supported_relations else CandidateDecision.ABSTAIN
            candidates.append(YixiangCandidate(
                f"yc:{left.observation_id}:{right.observation_id}",
                left.observation_id, right.observation_id, left.domain, right.domain,
                decision, tuple(supported_features), tuple(supported_relations),
                tuple(sorted((left_dims | right_dims) - shared_dims)), tuple(reasons),
            ))
    return tuple(candidates)
