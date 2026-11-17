import unittest
from dataclasses import replace
from prototype.yixiang_reproducibility_manifest_m49 import *

def manifest(**kw):
 base=dict(run_id="r1",code_commit="abcdef1234567",clean_worktree=True,python_version="3.12",
  platform="linux-x86_64",dependency_lock_ref="lock:v1",dataset_version="d1",
  benchmark_protocol="p1",config_digest="a"*64,random_seed=17,
  split_items=(SplitItem("i1","train","obj1","src1"),SplitItem("i2","validation","obj2","src2"),
               SplitItem("i3","test","obj3","src3")),
  artifacts=(ArtifactRef("scores","artifact://scores","b"*64),),event_ledger_digest="c"*64,
  metric_schema_version="m1")
 base.update(kw); return RunManifest(**base)

class M49Tests(unittest.TestCase):
 def test_complete_manifest_passes(self): self.assertTrue(audit_manifest(manifest()).complete)
 def test_clean_split_is_leakage_free(self): self.assertTrue(audit_manifest(manifest()).leakage_free)
 def test_missing_run_id_fails(self): self.assertIn("required_manifest_field_missing",audit_manifest(manifest(run_id="")).issues)
 def test_invalid_commit_fails(self): self.assertIn("invalid_code_commit",audit_manifest(manifest(code_commit="nope")).issues)
 def test_short_commit_allowed(self): self.assertNotIn("invalid_code_commit",audit_manifest(manifest(code_commit="abcdef1")).issues)
 def test_invalid_config_digest_fails(self): self.assertIn("invalid_config_digest",audit_manifest(manifest(config_digest="x")).issues)
 def test_invalid_ledger_digest_fails(self): self.assertIn("invalid_event_ledger_digest",audit_manifest(manifest(event_ledger_digest="x")).issues)
 def test_negative_seed_fails(self): self.assertIn("negative_random_seed",audit_manifest(manifest(random_seed=-1)).issues)
 def test_dirty_worktree_warns(self): self.assertIn("dirty_worktree",audit_manifest(manifest(clean_worktree=False)).warnings)
 def test_duplicate_item_id_fails(self):
  items=(SplitItem("i","train","o1","s1"),SplitItem("i","test","o2","s2"))
  self.assertIn("duplicate_split_item_id",audit_manifest(manifest(split_items=items)).issues)
 def test_invalid_split_fails(self):
  items=(SplitItem("i","dev","o","s"),)
  self.assertTrue(any(x.startswith("invalid_split") for x in audit_manifest(manifest(split_items=items)).issues))
 def test_object_family_leakage_fails(self):
  items=(SplitItem("i1","train","same","s1"),SplitItem("i2","test","same","s2"))
  self.assertTrue(any(x.startswith("object_family_leakage") for x in audit_manifest(manifest(split_items=items)).issues))
 def test_source_family_leakage_fails(self):
  items=(SplitItem("i1","train","o1","same"),SplitItem("i2","test","o2","same"))
  self.assertTrue(any(x.startswith("source_family_leakage") for x in audit_manifest(manifest(split_items=items)).issues))
 def test_empty_splits_fail(self): self.assertIn("split_items_required",audit_manifest(manifest(split_items=())).issues)
 def test_duplicate_artifact_name_fails(self):
  a=(ArtifactRef("x","u","b"*64),ArtifactRef("x","v","c"*64))
  self.assertIn("duplicate_artifact_name",audit_manifest(manifest(artifacts=a)).issues)
 def test_invalid_artifact_digest_fails(self):
  self.assertIn("invalid_artifact_digest:x",audit_manifest(manifest(artifacts=(ArtifactRef("x","u","bad"),))).issues)
 def test_missing_artifact_uri_fails(self):
  self.assertIn("artifact_reference_missing",audit_manifest(manifest(artifacts=(ArtifactRef("x","","b"*64),))).issues)
 def test_no_artifact_warns(self): self.assertIn("no_result_artifacts_registered",audit_manifest(manifest(artifacts=())).warnings)
 def test_digest_is_stable(self): self.assertEqual(audit_manifest(manifest()).manifest_digest,audit_manifest(manifest()).manifest_digest)
 def test_digest_changes_with_seed(self): self.assertNotEqual(audit_manifest(manifest()).manifest_digest,audit_manifest(manifest(random_seed=18)).manifest_digest)
