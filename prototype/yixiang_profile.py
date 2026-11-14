"""Source-versioned trigram profiles with explicit provenance.

The module deliberately stores claims without inventing canonical meanings.
Binary trigram encoding is computational structure; semantic claims must be
provided by a named textual tradition/edition and a precise source locator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

TRIGRAM_LINES_BOTTOM_TO_TOP: Mapping[str, tuple[int, int, int]] = {
    "乾": (1, 1, 1),
    "兑": (1, 1, 0),
    "离": (1, 0, 1),
    "震": (1, 0, 0),
    "巽": (0, 1, 1),
    "坎": (0, 1, 0),
    "艮": (0, 0, 1),
    "坤": (0, 0, 0),
}


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    work: str
    edition: str
    locator: str
    source_type: str = "classical_text"

    def validate(self) -> None:
        allowed = {
            "classical_text", "historical_commentary", "modern_scholarship",
            "field_observation", "research_hypothesis", "synthetic_fixture",
            "model_generated",
        }
        if not all(isinstance(value, str) and value.strip() for value in (
            self.source_id, self.work, self.edition, self.locator, self.source_type
        )):
            raise ValueError("source id, work, edition, locator, and source_type are required")
        if self.source_type not in allowed:
            raise ValueError(f"unknown source_type: {self.source_type}")


@dataclass(frozen=True)
class SourcedClaim:
    subject: str
    predicate: str
    object: str
    source_id: str
    scope: str
    claim_id: str
    locator: str = ""
    claim_kind: str = "traditional_textual_claim"
    review_status: str = "unreviewed"

    def validate(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (
            self.subject, self.predicate, self.object, self.source_id,
            self.scope, self.claim_id, self.locator, self.claim_kind,
            self.review_status
        )):
            raise ValueError("claim fields, exact locator, claim_kind, and review_status must be non-empty")
        allowed_kinds = {
            "traditional_textual_claim", "commentarial_claim",
            "modern_interpretation", "project_operational_definition",
            "research_hypothesis", "observational_claim", "synthetic_fixture",
        }
        allowed_statuses = {"unreviewed", "reviewed", "disputed", "rejected"}
        if self.claim_kind not in allowed_kinds:
            raise ValueError(f"unknown claim_kind: {self.claim_kind}")
        if self.review_status not in allowed_statuses:
            raise ValueError(f"unknown review_status: {self.review_status}")


@dataclass(frozen=True)
class TrigramProfile:
    profile_id: str
    tradition: str
    version: str
    trigram: str
    lines_bottom_to_top: tuple[int, int, int]
    claims: tuple[SourcedClaim, ...] = ()


@dataclass(frozen=True)
class ProfileConflict:
    subject: str
    predicate: str
    scope: str
    object_values: tuple[str, ...]
    source_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProfileSet:
    profile_set_id: str
    sources: tuple[SourceRef, ...]
    profiles: tuple[TrigramProfile, ...]

    def validate(self) -> None:
        if not self.profile_set_id.strip():
            raise ValueError("profile_set_id is required")
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")
        for source in self.sources:
            source.validate()

        profile_ids = [profile.profile_id for profile in self.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("profile_id values must be unique")
        known_sources = set(source_ids)
        claim_ids: list[str] = []
        for profile in self.profiles:
            if not all(value.strip() for value in (
                profile.profile_id, profile.tradition, profile.version
            )):
                raise ValueError("profile id, tradition, and version are required")
            expected = TRIGRAM_LINES_BOTTOM_TO_TOP.get(profile.trigram)
            if expected is None:
                raise ValueError(f"unknown trigram: {profile.trigram}")
            if (type(profile.lines_bottom_to_top) is not tuple
                    or len(profile.lines_bottom_to_top) != 3
                    or any(type(bit) is not int or bit not in (0, 1)
                           for bit in profile.lines_bottom_to_top)):
                raise ValueError("trigram lines must be a 3-bit integer tuple")
            if profile.lines_bottom_to_top != expected:
                raise ValueError("trigram name and binary line encoding disagree")
            for claim in profile.claims:
                claim.validate()
                claim_ids.append(claim.claim_id)
                if claim.source_id not in known_sources:
                    raise ValueError(
                        f"claim {claim.claim_id} references unknown source "
                        f"{claim.source_id}"
                    )
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique across the profile set")

    def conflicts(self) -> tuple[ProfileConflict, ...]:
        """Return disagreements; never silently choose or merge traditions."""
        self.validate()
        grouped: dict[tuple[str, str, str], list[SourcedClaim]] = {}
        for profile in self.profiles:
            for claim in profile.claims:
                key = (claim.subject, claim.predicate, claim.scope)
                grouped.setdefault(key, []).append(claim)
        conflicts = []
        for (subject, predicate, scope), claims in sorted(grouped.items()):
            values = tuple(sorted({claim.object for claim in claims}))
            if len(values) > 1:
                conflicts.append(ProfileConflict(
                    subject, predicate, scope, values,
                    tuple(sorted({claim.source_id for claim in claims})),
                    tuple(sorted({claim.claim_id for claim in claims})),
                ))
        return tuple(conflicts)


def validate_profile_set(
    profile_set: ProfileSet,
) -> tuple[ProfileConflict, ...]:
    """Validate all provenance and encoding invariants, then report conflicts."""
    profile_set.validate()
    return profile_set.conflicts()
