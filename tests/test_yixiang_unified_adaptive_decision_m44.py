import unittest
from prototype.yixiang_adaptive_policy_search_m40 import *
from prototype.yixiang_adaptive_stopping_m41 import *
from prototype.yixiang_model_robustness_m42 import *
from prototype.yixiang_policy_transport_m43 import *
from prototype.yixiang_unified_adaptive_decision_m44 import *

def bundle(stop=Decision.CONTINUE,robust=RobustnessStatus.ROBUST_WITHIN_DECLARED_SET,
           transport=TransportStatus.CONDITIONALLY_TRANSPORTABLE,refs=None):
 p=PolicyNode(None,(),(.9,),0)
 sr=SearchResult(p,(("s",.9),),.9,1,"stop_policy",(),())
 st=StopAudit(stop,.8,.9,.1,(),())
 ro=RobustnessAudit(robust,.9,.8,.9,.1,(("s",.8),),(),())
 tr=TransportAudit(transport,.8,(),())
 refs=refs if refs is not None else tuple(StageReference(x,"artifact-"+x,"evidence-"+x) for x in REQUIRED_STAGES)
 return PipelineInput(sr,st,ro,tr,refs)

class M44Tests(unittest.TestCase):
 def test_complete_chain_ready(self): self.assertEqual(audit_pipeline(bundle()).status,PipelineStatus.READY_FOR_HUMAN_REVIEW)
 def test_stop_chain_stopped_for_review(self): self.assertEqual(audit_pipeline(bundle(stop=Decision.STOP)).status,PipelineStatus.STOPPED_FOR_HUMAN_REVIEW)
 def test_missing_stage_requires_review(self):
  refs=tuple(x for x in bundle().stage_references if x.stage!="M38")
  self.assertEqual(audit_pipeline(bundle(refs=refs)).status,PipelineStatus.REVIEW_REQUIRED)
 def test_duplicate_stage_blocks(self):
  refs=bundle().stage_references+(StageReference("M40","x","y"),)
  self.assertEqual(audit_pipeline(bundle(refs=refs)).status,PipelineStatus.BLOCKED)
 def test_empty_reference_blocks(self):
  refs=list(bundle().stage_references); refs[0]=StageReference("M37","","e")
  self.assertEqual(audit_pipeline(bundle(refs=tuple(refs))).status,PipelineStatus.BLOCKED)
 def test_policy_search_blocked(self):
  b=bundle(); p=SearchResult(None,(),0,0,"blocked",("bad",),())
  self.assertEqual(audit_pipeline(PipelineInput(p,b.stopping,b.robustness,b.transport,b.stage_references)).status,PipelineStatus.BLOCKED)
 def test_stopping_review_requires_review(self): self.assertEqual(audit_pipeline(bundle(stop=Decision.REVIEW)).status,PipelineStatus.REVIEW_REQUIRED)
 def test_robustness_blocked(self): self.assertEqual(audit_pipeline(bundle(robust=RobustnessStatus.BLOCKED)).status,PipelineStatus.BLOCKED)
 def test_robustness_fragile_requires_review(self): self.assertEqual(audit_pipeline(bundle(robust=RobustnessStatus.FRAGILE)).status,PipelineStatus.REVIEW_REQUIRED)
 def test_transport_blocked(self): self.assertEqual(audit_pipeline(bundle(transport=TransportStatus.BLOCKED)).status,PipelineStatus.BLOCKED)
 def test_transport_review_required(self): self.assertEqual(audit_pipeline(bundle(transport=TransportStatus.REVIEW_REQUIRED)).status,PipelineStatus.REVIEW_REQUIRED)
 def test_no_execution_authority(self): self.assertFalse(audit_pipeline(bundle()).execution_authorized)
 def test_no_truth_certification(self): self.assertFalse(audit_pipeline(bundle()).causal_truth_established)
 def test_next_step_for_continue(self): self.assertIn("before_any_execution",audit_pipeline(bundle()).next_step)
 def test_next_step_for_stop(self): self.assertIn("terminal_decision",audit_pipeline(bundle(stop=Decision.STOP)).next_step)
 def test_all_required_stages_named(self): self.assertEqual(REQUIRED_STAGES,("M37","M38","M39","M40","M41","M42","M43"))
 def test_completed_stages_reported(self): self.assertEqual(len(audit_pipeline(bundle()).completed_stages),7)
 def test_blocker_dominates_review(self):
  b=bundle(robust=RobustnessStatus.BLOCKED,stop=Decision.REVIEW)
  self.assertEqual(audit_pipeline(b).status,PipelineStatus.BLOCKED)
