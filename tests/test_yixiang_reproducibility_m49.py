import unittest
from prototype.yixiang_reproducibility_m49 import *

def manifest(**kw):
 d=dict(benchmark_id="b1",code_commit="abc123",dataset_version="1",generator_version="1",
 seeds=(1,2),train_scenarios=("a","b"),validation_scenarios=("c",),test_scenarios=("d",),
 metric_names=("f1","shd"),method_names=("baseline","zhouyi"),config_ref="config",environment_ref="env")
 d.update(kw); return BenchmarkManifest(**d)

class M49Tests(unittest.TestCase):
 def test_valid_manifest(self): self.assertTrue(audit_manifest(manifest()).valid)
 def test_missing_commit(self): self.assertIn("missing_manifest_identity_or_environment",audit_manifest(manifest(code_commit="")).issues)
 def test_duplicate_seeds(self): self.assertIn("missing_or_duplicate_seeds",audit_manifest(manifest(seeds=(1,1))).issues)
 def test_missing_seeds(self): self.assertIn("missing_or_duplicate_seeds",audit_manifest(manifest(seeds=())).issues)
 def test_empty_train_split(self): self.assertIn("empty_data_split",audit_manifest(manifest(train_scenarios=())).issues)
 def test_overlap_train_validation(self): self.assertIn("scenario_leakage_across_splits",audit_manifest(manifest(validation_scenarios=("a",))).issues)
 def test_overlap_test_validation(self): self.assertIn("scenario_leakage_across_splits",audit_manifest(manifest(test_scenarios=("c",))).issues)
 def test_missing_metrics(self): self.assertIn("missing_metrics_or_methods",audit_manifest(manifest(metric_names=())).issues)
 def test_missing_methods(self): self.assertIn("missing_metrics_or_methods",audit_manifest(manifest(method_names=())).issues)
 def test_build_report(self):
  a=audit_manifest(manifest()); r=build_report(manifest(),a,{("m","full"):{"runs":2,"mean_f1":.7,"mean_shd":1.5}})
  self.assertEqual(r["benchmark_id"],"b1"); self.assertEqual(r["results"][0]["mean_f1"],.7)
 def test_invalid_manifest_cannot_report(self):
  m=manifest(test_scenarios=("a",)); 
  with self.assertRaises(ValueError): build_report(m,audit_manifest(m),{})
 def test_report_records_limitations(self):
  m=manifest(); r=build_report(m,audit_manifest(m),{}); self.assertIn("environment_not_independently_verified",r["limitations"])
