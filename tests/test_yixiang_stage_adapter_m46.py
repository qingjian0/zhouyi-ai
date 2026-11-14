import unittest
from prototype.yixiang_stage_adapter_m46 import *

def source(**kw):
 d=dict(stage_id="M37",schema_version="0.1",artifact_ref="artifact",evidence_ref="evidence",
 context_id="ctx",run_id="run",validation_status="validated"); d.update(kw); return StageArtifact(**d)
def contract(**kw):
 d=dict(source_stage="M37",target_stage="M38",accepted_schema_versions=("0.1",),required_context_match=True); d.update(kw); return AdapterContract(**d)

class M46Tests(unittest.TestCase):
 def test_compatible_source(self): self.assertEqual(audit_adapter(source(),contract(),"ctx").status,StageStatus.PRESENT)
 def test_wrong_source_stage(self): self.assertIn("source_stage_mismatch",audit_adapter(source(stage_id="M36"),contract(),"ctx").issues)
 def test_unsupported_version(self): self.assertIn("unsupported_schema_version",audit_adapter(source(schema_version="2.0"),contract(),"ctx").issues)
 def test_missing_artifact(self): self.assertIn("missing_artifact_evidence_or_run",audit_adapter(source(artifact_ref=""),contract(),"ctx").issues)
 def test_context_mismatch(self): self.assertIn("context_mismatch",audit_adapter(source(context_id="a"),contract(),"b").issues)
 def test_context_match_optional(self): self.assertEqual(audit_adapter(source(context_id="a"),contract(required_context_match=False),"b").status,StageStatus.PRESENT)
 def test_unvalidated_source_unverified(self): self.assertEqual(audit_adapter(source(validation_status="pending"),contract(),"ctx").status,StageStatus.UNVERIFIED)
 def test_multiple_versions(self): self.assertEqual(audit_adapter(source(schema_version="0.2"),contract(accepted_schema_versions=("0.1","0.2")),"ctx").status,StageStatus.PRESENT)
 def test_no_evidence(self): self.assertIn("missing_artifact_evidence_or_run",audit_adapter(source(evidence_ref=""),contract(),"ctx").issues)
 def test_no_run(self): self.assertIn("missing_artifact_evidence_or_run",audit_adapter(source(run_id=""),contract(),"ctx").issues)
 def test_unverified_not_incompatible(self): self.assertEqual(audit_adapter(source(validation_status="draft"),contract(),"ctx").status,StageStatus.UNVERIFIED)
