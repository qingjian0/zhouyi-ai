"""Gold extraction dataset manifest and leakage-safe split validation."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum

from prototype.m2_extraction_evaluation import ExtractionGoldCase
from prototype.observation_contract import EvidenceRef, canonical_json, record_digest


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    OOD_TEST = "ood_test"


class AnnotationStatus(str, Enum):
    REVIEWED = "reviewed"
    ADJUDICATED = "adjudicated"


@dataclass(frozen=True)
class AnnotatedExtractionRecord:
    case: ExtractionGoldCase
    split: DatasetSplit
    source_lineage_ids: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    annotation_status: AnnotationStatus

    def __post_init__(self) -> None:
        if not isinstance(self.case, ExtractionGoldCase):
            raise TypeError("case must be ExtractionGoldCase")
        if not isinstance(self.split, DatasetSplit):
            raise TypeError("split must be DatasetSplit")
        if not isinstance(self.annotation_status, AnnotationStatus):
            raise TypeError("annotation_status must be AnnotationStatus")
        if not self.source_lineage_ids or any(
            not isinstance(item, str) or not item.strip()
            for item in self.source_lineage_ids
        ):
            raise ValueError("source_lineage_ids must contain non-empty lineage IDs")
        if len(self.source_lineage_ids) != len(set(self.source_lineage_ids)):
            raise ValueError("source_lineage_ids must be unique within a record")
        if not self.evidence_refs or any(
            not isinstance(item, EvidenceRef) for item in self.evidence_refs
        ):
            raise ValueError("evidence_refs must contain at least one EvidenceRef")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique within a record")
        if self.split in (DatasetSplit.VALIDATION, DatasetSplit.TEST, DatasetSplit.OOD_TEST):
            if self.annotation_status is not AnnotationStatus.ADJUDICATED:
                raise ValueError("validation/test annotations must be adjudicated")


@dataclass(frozen=True)
class ExtractionDatasetManifest:
    dataset_id: str
    dataset_version: str
    annotation_schema_version: str
    records: tuple[AnnotatedExtractionRecord, ...]

    def __post_init__(self) -> None:
        for field_name in ("dataset_id", "dataset_version", "annotation_schema_version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        if not self.records:
            raise ValueError("dataset manifest must contain at least one record")
        if any(not isinstance(item, AnnotatedExtractionRecord) for item in self.records):
            raise TypeError("records must contain AnnotatedExtractionRecord values")
        case_ids = [item.case.case_id for item in self.records]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case IDs must be globally unique in a dataset manifest")

        lineage_splits: dict[str, DatasetSplit] = {}
        document_splits: dict[str, DatasetSplit] = {}
        evidence_splits: dict[EvidenceRef, DatasetSplit] = {}
        non_ood_domains: set[str] = set()
        ood_domains: set[str] = set()
        for item in self.records:
            for lineage_id in item.source_lineage_ids:
                previous = lineage_splits.setdefault(lineage_id, item.split)
                if previous is not item.split:
                    raise ValueError(
                        f"source lineage leakage across splits: {lineage_id} "
                        f"appears in {previous.value} and {item.split.value}"
                    )
            for reference in item.evidence_refs:
                previous = document_splits.setdefault(reference.document_id, item.split)
                if previous is not item.split:
                    raise ValueError(
                        f"document leakage across splits: {reference.document_id} "
                        f"appears in {previous.value} and {item.split.value}"
                    )
                previous_ref_split = evidence_splits.setdefault(reference, item.split)
                if previous_ref_split is not item.split:
                    raise ValueError("identical evidence reference appears in multiple splits")
            domain = item.case.domain
            if item.split is DatasetSplit.OOD_TEST:
                if domain in non_ood_domains:
                    raise ValueError(f"OOD domain leakage: {domain} also appears outside ood_test")
                ood_domains.add(domain)
            else:
                if domain in ood_domains:
                    raise ValueError(f"OOD domain leakage: {domain} also appears in {item.split.value}")
                non_ood_domains.add(domain)

    def split_summary(self) -> dict:
        split_counts = Counter(item.split.value for item in self.records)
        domain_counts: dict[str, Counter] = defaultdict(Counter)
        source_counts: dict[str, set[str]] = defaultdict(set)
        for item in self.records:
            domain_counts[item.split.value][item.case.domain] += 1
            source_counts[item.split.value].update(item.source_lineage_ids)
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "annotation_schema_version": self.annotation_schema_version,
            "case_count": len(self.records),
            "split_case_counts": {
                split.value: split_counts[split.value] for split in DatasetSplit
            },
            "domain_case_counts": {
                split: dict(sorted(counts.items()))
                for split, counts in sorted(domain_counts.items())
            },
            "unique_source_lineage_counts": {
                split.value: len(source_counts[split.value]) for split in DatasetSplit
            },
            "manifest_sha256": record_digest(self),
        }

    def to_canonical_json(self) -> str:
        """Stable serialized manifest; parsing is intentionally a separate versioned step."""
        return canonical_json(self)
