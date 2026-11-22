"""Strict text-span adapter for evidence-grounded classiang observations.

This module does not pretend to understand raw text. It converts explicit,
reviewable feature annotations into Observation objects while binding every
feature to a source document and exact character offsets.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.classiang_engine import (
    FeatureAtom, FeatureCandidate, Observation,
)


@dataclass(frozen=True)
class TextFeatureAnnotation:
    feature_id: str
    start_char: int
    end_char: int
    dimension: str
    value: str
    purpose_scores: tuple[tuple[str, float], ...]


def observation_from_text_spans(
    *,
    observation_id: str,
    subject_id: str,
    domain: str,
    source_id: str,
    text: str,
    annotations: tuple[TextFeatureAnnotation, ...],
    context: tuple[str, ...] = (),
) -> Observation:
    """Build an Observation from explicit source-grounded text annotations.

    Offsets are Python Unicode code-point offsets into the exact supplied
    string. Each annotation must identify a non-empty span whose surface text
    is preserved in the evidence reference. Feature values may be normalized
    labels, but are never substituted for the original surface evidence.
    """
    for name, value in (
        ("observation_id", observation_id), ("subject_id", subject_id),
        ("domain", domain), ("source_id", source_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(text, str) or not text:
        raise ValueError("text must be a non-empty string")
    if not isinstance(annotations, tuple) or not annotations:
        raise ValueError("annotations must be a non-empty tuple")
    if not isinstance(context, tuple):
        raise ValueError("context must be a tuple")

    candidates = []
    refs = []
    seen_ids = set()
    for annotation in annotations:
        if not isinstance(annotation, TextFeatureAnnotation):
            raise ValueError("annotations must contain TextFeatureAnnotation")
        if not isinstance(annotation.feature_id, str) or not annotation.feature_id.strip():
            raise ValueError("feature_id must be a non-empty string")
        if annotation.feature_id in seen_ids:
            raise ValueError("feature IDs must be unique")
        seen_ids.add(annotation.feature_id)
        for name, offset in (
            ("start_char", annotation.start_char), ("end_char", annotation.end_char),
        ):
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise ValueError(f"{name} must be an integer")
        if annotation.start_char < 0 or annotation.end_char <= annotation.start_char:
            raise ValueError("annotation span must be non-empty and ordered")
        if annotation.end_char > len(text):
            raise ValueError("annotation span exceeds source text")
        surface = text[annotation.start_char:annotation.end_char]
        if not surface.strip():
            raise ValueError("annotation span must contain non-whitespace source text")
        if not isinstance(annotation.value, str) or not annotation.value.strip():
            raise ValueError("feature value must be a non-empty string")
        ref = (
            f"text:{source_id}:chars:{annotation.start_char}-"
            f"{annotation.end_char}"
        )
        refs.append(ref)
        candidates.append(FeatureCandidate(
            feature_id=annotation.feature_id,
            atom=FeatureAtom(annotation.dimension, annotation.value),
            evidence_refs=(ref,),
            purpose_scores=annotation.purpose_scores,
        ))

    if len(refs) != len(set(refs)):
        raise ValueError("annotation spans must be unique")
    observation = Observation(
        observation_id=observation_id,
        subject_id=subject_id,
        domain=domain,
        evidence_refs=tuple(sorted(refs)),
        features=tuple(candidates),
        context=context,
    )
    observation.validate()
    return observation
