"""Typed M2 observation and grounding DTOs.

This module validates provenance-bearing records only. It does not infer truth,
write a second event log, or turn a grounded observation into a true assertion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any


class ContractError(ValueError):
    """An M2 record violates its versioned data contract."""


class Modality(str, Enum):
    TEXT = "TEXT"
    PDF = "PDF"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    TABLE = "TABLE"


class ParseStatus(str, Enum):
    PARSED = "PARSED"
    PARTIAL = "PARTIAL"
    UNPARSEABLE = "UNPARSEABLE"
    REJECTED = "REJECTED"


class UnitKind(str, Enum):
    ENTITY = "ENTITY"
    CONCEPT = "CONCEPT"
    EVENT = "EVENT"
    ATTRIBUTE = "ATTRIBUTE"
    STATE = "STATE"
    MEASUREMENT = "MEASUREMENT"
    ACTION = "ACTION"
    TIME = "TIME"
    PLACE = "PLACE"
    UNKNOWN = "UNKNOWN"


class GroundingStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    GROUNDED = "GROUNDED"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class EpistemicStatus(str, Enum):
    ASSERTED = "ASSERTED"
    INFERRED = "INFERRED"
    HYPOTHETICAL = "HYPOTHETICAL"
    NEGATED = "NEGATED"
    UNKNOWN = "UNKNOWN"


class TruthStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    CONFLICTED = "CONFLICTED"


class ExtractionMethod(str, Enum):
    RULE = "RULE"
    MODEL = "MODEL"
    HUMAN = "HUMAN"
    TOOL = "TOOL"
    FUSION = "FUSION"


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")


def _enum(value: Any, cls: type[Enum], field: str) -> None:
    if not isinstance(value, cls):
        raise ContractError(f"{field} must be {cls.__name__}")


def _probability(value: float | None, field: str) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or not 0.0 <= value <= 1.0
    ):
        raise ContractError(f"{field} must be a finite probability in [0, 1]")


@dataclass(frozen=True)
class EvidenceRef:
    """Exact reference to an immutable M1 chunk; never embeds source text."""

    document_id: str
    chunk_id: str
    content_sha256: str
    byte_start: int
    byte_end: int
    source_version: str

    def __post_init__(self) -> None:
        for name in ("document_id", "chunk_id", "source_version"):
            _nonempty(getattr(self, name), name)
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_sha256):
            raise ContractError("content_sha256 must be lowercase SHA-256 hex")
        if (isinstance(self.byte_start, bool) or not isinstance(self.byte_start, int)
                or isinstance(self.byte_end, bool) or not isinstance(self.byte_end, int)
                or self.byte_start < 0 or self.byte_end <= self.byte_start):
            raise ContractError("EvidenceRef requires a non-empty half-open byte span")


@dataclass(frozen=True)
class SourceLocator:
    """Modality-specific locator bound to an immutable payload version."""

    modality: Modality
    payload_version: str
    byte_start: int | None = None
    byte_end: int | None = None
    page_number: int | None = None
    region_xywh: tuple[float, float, float, float] | None = None
    time_start_ms: int | None = None
    time_end_ms: int | None = None
    table_sheet: str | None = None
    table_range: str | None = None

    def __post_init__(self) -> None:
        _enum(self.modality, Modality, "modality")
        _nonempty(self.payload_version, "payload_version")
        if (self.byte_start is None) != (self.byte_end is None):
            raise ContractError("byte_start and byte_end must be supplied together")
        if self.byte_start is not None and (
            isinstance(self.byte_start, bool) or isinstance(self.byte_end, bool)
            or not isinstance(self.byte_start, int) or not isinstance(self.byte_end, int)
            or self.byte_start < 0 or self.byte_end <= self.byte_start
        ):
            raise ContractError("invalid locator byte span")
        if self.page_number is not None and (
            isinstance(self.page_number, bool) or not isinstance(self.page_number, int)
            or self.page_number < 1
        ):
            raise ContractError("page_number must be a positive 1-based integer")
        if self.region_xywh is not None:
            if (len(self.region_xywh) != 4 or
                    any(isinstance(x, bool) or not isinstance(x, (int, float))
                        or not math.isfinite(x) or x < 0 for x in self.region_xywh) or
                    self.region_xywh[2] <= 0 or self.region_xywh[3] <= 0):
                raise ContractError("region_xywh must contain finite non-negative x/y and positive w/h")
        if (self.time_start_ms is None) != (self.time_end_ms is None):
            raise ContractError("time_start_ms and time_end_ms must be supplied together")
        if self.time_start_ms is not None and (
            isinstance(self.time_start_ms, bool) or isinstance(self.time_end_ms, bool)
            or not isinstance(self.time_start_ms, int) or not isinstance(self.time_end_ms, int)
            or self.time_start_ms < 0 or self.time_end_ms <= self.time_start_ms
        ):
            raise ContractError("invalid media time interval")
        if self.modality == Modality.TEXT and self.byte_start is None:
            raise ContractError("TEXT locator requires an exact byte span")
        if self.modality == Modality.PDF and self.page_number is None:
            raise ContractError("PDF locator requires a page number")
        if self.modality == Modality.IMAGE and self.region_xywh is None:
            raise ContractError("IMAGE locator requires a region")
        if self.modality in (Modality.AUDIO, Modality.VIDEO) and self.time_start_ms is None:
            raise ContractError("AUDIO/VIDEO locator requires a time interval")
        if self.modality == Modality.TABLE:
            _nonempty(self.table_sheet or "", "table_sheet")
            _nonempty(self.table_range or "", "table_range")


@dataclass(frozen=True)
class Score:
    """A numeric score with an explicit, non-interchangeable meaning."""

    value: float
    semantics: str

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise ContractError("score value must be finite")
        _nonempty(self.semantics, "score semantics")


@dataclass(frozen=True)
class RecordEnvelope:
    schema_version: str
    record_id: str
    record_kind: str
    producer: str
    producer_version: str
    recorded_at: str
    scope: str
    source_refs: tuple[EvidenceRef, ...]
    derivation_refs: tuple[str, ...] = ()
    valid_time_start: str | None = None
    valid_time_end: str | None = None

    def __post_init__(self) -> None:
        for field in ("schema_version", "record_id", "record_kind", "producer",
                      "producer_version", "recorded_at", "scope"):
            _nonempty(getattr(self, field), field)
        if not self.source_refs:
            raise ContractError("source_refs must not be empty")
        if any(not isinstance(x, EvidenceRef) for x in self.source_refs):
            raise ContractError("source_refs must contain EvidenceRef values")
        if any(not isinstance(x, str) or not x.strip() for x in self.derivation_refs):
            raise ContractError("derivation_refs must contain non-empty IDs")
        if (self.valid_time_start is None) != (self.valid_time_end is None):
            raise ContractError("valid-time endpoints must be supplied together")


@dataclass(frozen=True)
class Observation:
    envelope: RecordEnvelope
    modality: Modality
    source_locator: SourceLocator
    extractor_id: str
    extractor_version: str
    extraction_method: ExtractionMethod
    parse_status: ParseStatus
    extraction_score: Score | None = None
    language: str | None = None
    speaker: str | None = None

    def __post_init__(self) -> None:
        if self.envelope.record_kind != "Observation":
            raise ContractError("Observation envelope record_kind mismatch")
        _enum(self.modality, Modality, "modality")
        _enum(self.extraction_method, ExtractionMethod, "extraction_method")
        _enum(self.parse_status, ParseStatus, "parse_status")
        if self.source_locator.modality != self.modality:
            raise ContractError("locator modality must match observation modality")
        _nonempty(self.extractor_id, "extractor_id")
        _nonempty(self.extractor_version, "extractor_version")
        if self.extraction_score is not None and not isinstance(self.extraction_score, Score):
            raise ContractError("extraction_score must be a typed Score")


@dataclass(frozen=True)
class TypedAttribute:
    name: str
    value_type: str
    value: Any
    unit: str | None = None
    source_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.name, "attribute name")
        _nonempty(self.value_type, "attribute value_type")
        if not self.source_refs or any(not isinstance(x, EvidenceRef) for x in self.source_refs):
            raise ContractError("typed attribute requires evidence references")
        if self.unit is not None:
            _nonempty(self.unit, "attribute unit")


@dataclass(frozen=True)
class RoleBinding:
    role_name: str
    target_ref: str

    def __post_init__(self) -> None:
        _nonempty(self.role_name, "role_name")
        _nonempty(self.target_ref, "target_ref")


@dataclass(frozen=True)
class SemanticUnitCandidate:
    envelope: RecordEnvelope
    kind: UnitKind
    surface_forms: tuple[str, ...]
    typed_attributes: tuple[TypedAttribute, ...] = ()
    role_bindings: tuple[RoleBinding, ...] = ()
    canonical_key: str | None = None
    grounding_status: GroundingStatus = GroundingStatus.UNRESOLVED
    epistemic_status: EpistemicStatus = EpistemicStatus.UNKNOWN
    extractor_confidence: float | None = None
    source_reliability: float | None = None
    truth_status: TruthStatus = TruthStatus.UNKNOWN
    calibrated_probability: float | None = None
    ranking_score: Score | None = None

    def __post_init__(self) -> None:
        if self.envelope.record_kind != "SemanticUnitCandidate":
            raise ContractError("candidate envelope record_kind mismatch")
        _enum(self.kind, UnitKind, "kind")
        _enum(self.grounding_status, GroundingStatus, "grounding_status")
        _enum(self.epistemic_status, EpistemicStatus, "epistemic_status")
        _enum(self.truth_status, TruthStatus, "truth_status")
        if not self.surface_forms or any(not isinstance(x, str) or not x.strip() for x in self.surface_forms):
            raise ContractError("surface_forms must contain non-empty source expressions")
        if self.canonical_key is not None:
            _nonempty(self.canonical_key, "canonical_key")
        for name in ("extractor_confidence", "source_reliability", "calibrated_probability"):
            _probability(getattr(self, name), name)
        if any(not isinstance(x, TypedAttribute) for x in self.typed_attributes):
            raise ContractError("typed_attributes must contain TypedAttribute values")
        if any(not isinstance(x, RoleBinding) for x in self.role_bindings):
            raise ContractError("role_bindings must contain RoleBinding values")
        if self.ranking_score is not None and not isinstance(self.ranking_score, Score):
            raise ContractError("ranking_score must be a typed Score")
        # Grounding and truth remain independent typed dimensions. A grounded
        # candidate may later be supported/refuted by a separate adjudication;
        # neither state is inferred from the other here.


def canonical_json(record: Any) -> str:
    """Stable JSON representation for hashing and idempotency keys."""
    def normalize(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if hasattr(value, "__dataclass_fields__"):
            return {key: normalize(item) for key, item in asdict(value).items()}
        if isinstance(value, dict):
            return {str(k): normalize(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [normalize(item) for item in value]
        return value
    try:
        return json.dumps(normalize(record), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"record is not canonically serializable: {exc}") from exc


def record_digest(record: Any) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
