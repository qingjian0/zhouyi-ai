"""Adapters from reviewed observation-to-xiang traces into classiang.

The adapter deliberately requires explicit dimension and task-relevance
annotations. It does not guess ontology labels or invent upstream scores.
"""
from __future__ import annotations

from typing import Mapping

from prototype.classiang_engine import (
    FeatureAtom, FeatureCandidate, Observation as ClassiangObservation,
)
from prototype.yixiang_formation import (
    FormationStatus, FormationTrace, assess_formation,
)


def adapt_formation_trace(
    trace: FormationTrace,
    *,
    subject_id: str,
    domain: str,
    dimensions: Mapping[str, str],
    purpose_scores: Mapping[str, tuple[tuple[str, float], ...]],
) -> ClassiangObservation:
    """Convert one reviewed subject trace without losing evidence lineage.

    Only a complete, reviewed FormationTrace is admitted. Every selected
    feature needs an explicit classiang dimension and upstream task scores.
    The adapter preserves the existing formation API and is additive.
    """
    for name, value in (("subject_id", subject_id), ("domain", domain)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(dimensions, Mapping) or not isinstance(purpose_scores, Mapping):
        raise ValueError("dimensions and purpose_scores must be mappings")

    assessment = assess_formation(trace)
    if assessment.status != FormationStatus.PROVISIONAL_FORMATION:
        raise ValueError(
            f"formation trace is not admission-ready: {assessment.status.value}"
        )

    features = tuple(
        item for item in trace.selected_features if item.subject_id == subject_id
    )
    if not features:
        raise ValueError("trace has no selected features for subject_id")

    feature_ids = {item.feature_id for item in features}
    if set(dimensions) != feature_ids:
        raise ValueError("dimensions must map exactly the selected feature IDs")
    if set(purpose_scores) != feature_ids:
        raise ValueError("purpose_scores must map exactly the selected feature IDs")

    linked_observations = {
        observation.observation_id: observation
        for observation in trace.observations
        if observation.subject_id == subject_id
    }
    evidence_refs = tuple(sorted({
        ref for feature in features for ref in feature.evidence_refs
    }))
    context = tuple(sorted({
        f"{item.context_id}@{item.context_version}"
        for item in linked_observations.values()
    }))
    candidates = tuple(
        FeatureCandidate(
            feature_id=item.feature_id,
            atom=FeatureAtom(
                dimension=dimensions[item.feature_id],
                value=f"{item.label}: {item.operational_description}",
            ),
            evidence_refs=item.evidence_refs,
            purpose_scores=purpose_scores[item.feature_id],
        )
        for item in features
    )
    adapted = ClassiangObservation(
        observation_id=f"formation:{trace.trace_id}:{subject_id}",
        subject_id=subject_id,
        domain=domain,
        evidence_refs=evidence_refs,
        features=candidates,
        context=context,
    )
    adapted.validate()
    return adapted
