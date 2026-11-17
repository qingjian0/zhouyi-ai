"""M49 reproducibility manifest and cross-split leakage audit."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

SPLITS={"train","validation","test"}

@dataclass(frozen=True)
class SplitItem:
    item_id: str
    split: str
    object_family: str
    source_family: str

@dataclass(frozen=True)
class ArtifactRef:
    name: str
    uri: str
    digest: str

@dataclass(frozen=True)
class RunManifest:
    run_id: str
    code_commit: str
    clean_worktree: bool
    python_version: str
    platform: str
    dependency_lock_ref: str
    dataset_version: str
    benchmark_protocol: str
    config_digest: str
    random_seed: int
    split_items: tuple
    artifacts: tuple
    event_ledger_digest: str
    metric_schema_version: str

@dataclass(frozen=True)
class ReproducibilityAudit:
    complete: bool
    leakage_free: bool
    issues: tuple
    warnings: tuple
    manifest_digest: str

def _digest(manifest):
    payload={k:getattr(manifest,k) for k in manifest.__dataclass_fields__}
    payload["split_items"]=[vars(x) for x in manifest.split_items]
    payload["artifacts"]=[vars(x) for x in manifest.artifacts]
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return sha256(raw.encode("utf-8")).hexdigest()

def audit_manifest(m):
    issues=[]; warnings=[]
    required=(m.run_id,m.code_commit,m.python_version,m.platform,m.dependency_lock_ref,
              m.dataset_version,m.benchmark_protocol,m.config_digest,m.event_ledger_digest,
              m.metric_schema_version)
    if any(not isinstance(x,str) or not x.strip() for x in required):
        issues.append("required_manifest_field_missing")
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}",m.code_commit): issues.append("invalid_code_commit")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",m.config_digest): issues.append("invalid_config_digest")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",m.event_ledger_digest): issues.append("invalid_event_ledger_digest")
    if m.random_seed<0: issues.append("negative_random_seed")
    if not m.clean_worktree: warnings.append("dirty_worktree")
    if not m.split_items: issues.append("split_items_required")
    ids=[x.item_id for x in m.split_items]
    if len(ids)!=len(set(ids)): issues.append("duplicate_split_item_id")
    object_splits={}; source_splits={}
    for item in m.split_items:
        if not item.item_id or not item.object_family or not item.source_family:
            issues.append("incomplete_split_item")
        if item.split not in SPLITS: issues.append("invalid_split:"+item.item_id)
        object_splits.setdefault(item.object_family,set()).add(item.split)
        source_splits.setdefault(item.source_family,set()).add(item.split)
    object_leaks=sorted(k for k,v in object_splits.items() if len(v)>1)
    source_leaks=sorted(k for k,v in source_splits.items() if len(v)>1)
    if object_leaks: issues.append("object_family_leakage:"+",".join(object_leaks))
    if source_leaks: issues.append("source_family_leakage:"+",".join(source_leaks))
    artifact_names=[a.name for a in m.artifacts]
    if len(artifact_names)!=len(set(artifact_names)): issues.append("duplicate_artifact_name")
    for a in m.artifacts:
        if not a.name or not a.uri: issues.append("artifact_reference_missing")
        if not re.fullmatch(r"[0-9a-fA-F]{64}",a.digest): issues.append("invalid_artifact_digest:"+a.name)
    if not m.artifacts: warnings.append("no_result_artifacts_registered")
    leakage=not object_leaks and not source_leaks
    complete=not issues
    return ReproducibilityAudit(complete,leakage,tuple(sorted(set(issues))),
                                tuple(sorted(set(warnings))),_digest(m))
