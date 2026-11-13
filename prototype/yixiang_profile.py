"""Source-versioned trigram profiles with explicit provenance.

The module deliberately stores claims without inventing canonical meanings.
Binary trigram encoding is computational structure; semantic claims must be
provided by a named textual tradition/edition and a precise source locator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

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

    def validate(self) -> None:
        if not all(value.strip() for value in (
            self.source_id, self.work, self.edition, self.locator
        )):
            raise ValueError("source id, work, edition, and locator are required")


@dataclass(frozen=True)
class SourcedClaim:
    subject: str
    predicate: str
    object: str
    source_id: str
    scope: str
    claim_id: str

    def validate(self) -> None:
        if not all(value.strip() for value in (
            self.subject, self.predicate, self.object, self.source_id,
            self.scope, self.claim_id
        )):
            raise ValueError("claim fields must be non-empty")


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
                if claim.source_id not in known_sources:
                    raise ValueError(
                        f"claim {claim.claim_id} references unknown source "
                        f"{claim.source_id}"
                    )

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
                ))
        return tuple(conflicts)


def validate_profile_set(
    profile_set: ProfileSet,
) -> tuple[ProfileConflict, ...]:
    """Validate all provenance and encoding invariants, then report conflicts."""
    profile_set.validate()
    return profile_set.conflicts()
