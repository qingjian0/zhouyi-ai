"""Typed stage-reference contracts and compatibility checks."""
from dataclasses import dataclass
from enum import Enum

class StageStatus(str, Enum):
    PRESENT="present"
    MISSING="missing"
    INCOMPATIBLE="incompatible"
    UNVERIFIED="unverified"

@dataclass(frozen=True)
class StageArtifact:
    stage_id: str
    schema_version: str
    artifact_ref: str
    evidence_ref: str
    context_id: str
    run_id: str
    validation_status: str

@dataclass(frozen=True)
class AdapterContract:
    source_stage: str
    target_stage: str
    accepted_schema_versions: tuple
    required_context_match: bool = True

@dataclass(frozen=True)
class AdapterAudit:
    status: StageStatus
    issues: tuple
    warnings: tuple

def audit_adapter(source, contract, target_context_id):
    issues=[]; warnings=[]
    if source.stage_id!=contract.source_stage: issues.append("source_stage_mismatch")
    if not source.artifact_ref or not source.evidence_ref or not source.run_id: issues.append("missing_artifact_evidence_or_run")
    if source.schema_version not in contract.accepted_schema_versions: issues.append("unsupported_schema_version")
    if contract.required_context_match and source.context_id!=target_context_id: issues.append("context_mismatch")
    if source.validation_status!="validated": warnings.append("source_artifact_not_runtime_validated")
    if issues: return AdapterAudit(StageStatus.INCOMPATIBLE,tuple(sorted(set(issues))),tuple(warnings))
    if warnings: return AdapterAudit(StageStatus.UNVERIFIED,(),tuple(warnings))
    return AdapterAudit(StageStatus.PRESENT,(),())
