"""Reproducibility manifest and benchmark report validation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class BenchmarkManifest:
    benchmark_id: str
    code_commit: str
    dataset_version: str
    generator_version: str
    seeds: tuple
    train_scenarios: tuple
    validation_scenarios: tuple
    test_scenarios: tuple
    metric_names: tuple
    method_names: tuple
    config_ref: str
    environment_ref: str

@dataclass(frozen=True)
class ReproducibilityAudit:
    valid: bool
    issues: tuple
    warnings: tuple

def audit_manifest(m):
    issues=[]; warnings=[]
    required=(m.benchmark_id,m.code_commit,m.dataset_version,m.generator_version,m.config_ref,m.environment_ref)
    if not all(required): issues.append("missing_manifest_identity_or_environment")
    if not m.seeds or len(set(m.seeds))!=len(m.seeds): issues.append("missing_or_duplicate_seeds")
    if not m.metric_names or not m.method_names: issues.append("missing_metrics_or_methods")
    splits=(set(m.train_scenarios),set(m.validation_scenarios),set(m.test_scenarios))
    if not all(splits): issues.append("empty_data_split")
    if splits[0]&splits[1] or splits[0]&splits[2] or splits[1]&splits[2]: issues.append("scenario_leakage_across_splits")
    if not m.test_scenarios: warnings.append("no_held_out_test_scenarios")
    warnings.append("manifest_records_claimed_environment_but_does_not_verify_it")
    return ReproducibilityAudit(not issues,tuple(sorted(set(issues))),tuple(sorted(set(warnings))))

def build_report(manifest,audit,results):
    if not audit.valid: raise ValueError("invalid_manifest")
    rows=[]
    for key,value in sorted(results.items()):
        rows.append({"method":key[0],"ablation":key[1],"runs":value["runs"],
                     "mean_f1":value["mean_f1"],"mean_shd":value["mean_shd"]})
    return {"benchmark_id":manifest.benchmark_id,"code_commit":manifest.code_commit,
            "dataset_version":manifest.dataset_version,"generator_version":manifest.generator_version,
            "seeds":manifest.seeds,"metrics":manifest.metric_names,"methods":manifest.method_names,
            "results":tuple(rows),"limitations":("summary_statistics_only","environment_not_independently_verified")}
