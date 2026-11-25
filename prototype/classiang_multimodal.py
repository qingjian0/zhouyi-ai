"""Evidence-preserving adapter contract for externally extracted image regions.

This module does not decode pixels or perform OCR/vision inference. It accepts
region claims from a separately selected perception provider and binds them
to a content-addressed image plus normalized bounding-box coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from prototype.classiang_engine import FeatureAtom, FeatureCandidate, Observation


@dataclass(frozen=True)
class ImageRegionClaim:
    region_id: str
    bbox: tuple[float, float, float, float]
    dimension: str
    value: str
    purpose_scores: tuple[tuple[str, float], ...] = ()


def observation_from_image_regions(
    *,
    observation_id: str,
    subject_id: str,
    domain: str,
    image_sha256: str,
    provider: str,
    provider_version: str,
    claims: tuple[ImageRegionClaim, ...],
    context: tuple[str, ...] = (),
) -> Observation:
    """Convert reviewed provider claims into image-region-grounded features.

    Coordinates are normalized [0, 1] xyxy values. Provider output remains
    untrusted: this adapter verifies provenance and shape, not visual truth.
    """
    for name, value in (
        ("observation_id", observation_id), ("subject_id", subject_id),
        ("domain", domain), ("provider", provider),
        ("provider_version", provider_version),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be non-empty")
    if not isinstance(image_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", image_sha256):
        raise ValueError("image_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(claims, tuple) or not claims:
        raise ValueError("claims must be a non-empty tuple")
    if not isinstance(context, tuple) or any(not isinstance(x, str) or not x.strip() for x in context):
        raise ValueError("context must contain non-empty strings")
    seen = set()
    features = []
    refs = []
    for claim in claims:
        if not isinstance(claim, ImageRegionClaim):
            raise ValueError("claims must contain ImageRegionClaim")
        if not isinstance(claim.region_id, str) or not claim.region_id.strip() or claim.region_id in seen:
            raise ValueError("region IDs must be non-empty and unique")
        seen.add(claim.region_id)
        if not isinstance(claim.bbox, tuple) or len(claim.bbox) != 4:
            raise ValueError("bbox must be an xyxy tuple")
        x1, y1, x2, y2 = claim.bbox
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not 0 <= x <= 1 for x in claim.bbox):
            raise ValueError("bbox coordinates must be finite normalized values")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must have positive area")
        atom = FeatureAtom(claim.dimension, claim.value)
        atom.validate()
        evidence = (
            f"image:sha256:{image_sha256}:region:{claim.region_id}:"
            f"xyxy:{x1:.6f},{y1:.6f},{x2:.6f},{y2:.6f}",
        )
        refs.extend(evidence)
        features.append(FeatureCandidate(
            feature_id=f"{observation_id}:{claim.region_id}",
            atom=atom, evidence_refs=evidence,
            purpose_scores=claim.purpose_scores,
        ))
    observation = Observation(
        observation_id, subject_id, domain, tuple(sorted(refs)),
        tuple(features), context + (f"vision-provider:{provider}@{provider_version}",),
    )
    observation.validate()
    return observation
