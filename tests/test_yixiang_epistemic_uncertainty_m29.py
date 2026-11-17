import unittest
from prototype.yixiang_epistemic_uncertainty_m29 import *
def ev(i,c,p=EvidencePolarity.SUPPORT,r=EvidenceReview.REVIEWED,reviewers=("r1",)):
 return EvidenceItem(i,c,p,r,tuple(reviewers),"Reviewed against the cited witness and scope.")
def j(c,s,**kw):
 return ClaimJudgement(c,s,"Explicit human adjudication with scope and counterevidence review.",("reviewer-1",),**kw)
def d(i,a,b,s=DependencyStrength.HARD):return ClaimDependency(i,a,b,s,"derived_from")
class M29Tests(unittest.TestCase):
 def run_graph(self,claims,e=(),jgs=(),conds=(),deps=()):return audit_epistemic_graph(tuple(claims),tuple(e),tuple(jgs),tuple(conds),tuple(deps))
 def state(self,r,c):return {x.claim_id:x.effective_state for x in r.records}[c]
 def test_no_evidence_unknown(self):self.assertEqual(self.state(self.run_graph(["a"]),"a"),EpistemicState.UNKNOWN)
 def test_unreviewed_requires_review(self):self.assertEqual(self.state(self.run_graph(["a"],[ev("e","a",r=EvidenceReview.UNREVIEWED,reviewers=())]),"a"),EpistemicState.REVIEW_REQUIRED)
 def test_reviewed_without_judgement_insufficient(self):self.assertEqual(self.state(self.run_graph(["a"],[ev("e","a")]),"a"),EpistemicState.INSUFFICIENT)
 def test_provisional_requires_support(self):self.assertEqual(self.state(self.run_graph(["a"],[ev("e","a")],[j("a",EpistemicState.PROVISIONAL)]),"a"),EpistemicState.PROVISIONAL)
 def test_counter_blocks_provisional(self):self.assertFalse(self.run_graph(["a"],[ev("s","a"),ev("c","a",EvidencePolarity.COUNTER)],[j("a",EpistemicState.PROVISIONAL)]).valid_graph)
 def test_conflict_requires_both_sides(self):self.assertEqual(self.state(self.run_graph(["a"],[ev("s","a"),ev("c","a",EvidencePolarity.COUNTER)],[j("a",EpistemicState.CONFLICTED)]),"a"),EpistemicState.CONFLICTED)
 def test_weakened_requires_counter(self):self.assertEqual(self.state(self.run_graph(["a"],[ev("c","a",EvidencePolarity.COUNTER)],[j("a",EpistemicState.WEAKENED)]),"a"),EpistemicState.WEAKENED)
 def test_conditional_requires_open_condition(self):
  c=Condition("c1","a",ConditionState.UNKNOWN,"scope remains stable")
  self.assertEqual(self.state(self.run_graph(["a"],jgs=[j("a",EpistemicState.CONDITIONAL,condition_refs=("c1",))],conds=[c]),"a"),EpistemicState.CONDITIONAL)
 def test_conditional_all_satisfied_rejected(self):
  c=Condition("c1","a",ConditionState.SATISFIED,"already satisfied")
  self.assertFalse(self.run_graph(["a"],jgs=[j("a",EpistemicState.CONDITIONAL,condition_refs=("c1",))],conds=[c]).valid_graph)
 def test_hard_conflict_propagates(self):
  r=self.run_graph(["a","b"],[ev("s","a"),ev("c","a",EvidencePolarity.COUNTER)],[j("a",EpistemicState.CONFLICTED)],deps=[d("d","a","b")])
  self.assertEqual(self.state(r,"b"),EpistemicState.CONFLICTED)
 def test_soft_uncertainty_review(self):
  r=self.run_graph(["a","b"],[ev("e","a",r=EvidenceReview.UNREVIEWED,reviewers=())],deps=[d("d","a","b",DependencyStrength.SOFT)])
  self.assertEqual(self.state(r,"b"),EpistemicState.REVIEW_REQUIRED)
 def test_hard_unknown_prerequisite_becomes_insufficient(self):
  r=self.run_graph(["a","b"],deps=[d("d","a","b")])
  self.assertEqual(self.state(r,"b"),EpistemicState.INSUFFICIENT)
 def test_hard_insufficient_propagates(self):
  r=self.run_graph(["a","b"],[ev("e","a")],deps=[d("d","a","b")]);self.assertEqual(self.state(r,"b"),EpistemicState.INSUFFICIENT)
 def test_m27_adapter(self):
  class F:stale_node_ids=("n1",);review_node_ids=("n2",)
  out=adapt_m27_invalidation(F(),(("n1","a"),("n2","b")))
  self.assertEqual(out[0][1],EpistemicState.STALE);self.assertEqual(out[1][1],EpistemicState.REVIEW_REQUIRED)
 def test_invalid_m27_graph_rejected(self):
  class F:valid_graph=False;stale_node_ids=();review_node_ids=()
  with self.assertRaises(ValueError):adapt_m27_invalidation(F(),())
 def test_m27_unmapped_rejected(self):
  class F:stale_node_ids=("n1",);review_node_ids=()
  with self.assertRaises(ValueError):adapt_m27_invalidation(F(),())
 def test_revalidation_barrier(self):
  evs=[ev("c","a",EvidencePolarity.COUNTER)]
  js=[j("a",EpistemicState.WEAKENED),ClaimJudgement("b",EpistemicState.REVALIDATED,"Rechecked current evidence and context.",("r2",),revalidation_of="rev-2")]
  r=self.run_graph(["a","b"],evs,js,deps=[d("d","a","b")]);self.assertEqual(self.state(r,"b"),EpistemicState.REVALIDATED)
 def test_cycle_rejected(self):self.assertFalse(self.run_graph(["a","b"],deps=[d("1","a","b"),d("2","b","a")]).valid_graph)
 def test_self_edge_rejected(self):self.assertFalse(self.run_graph(["a"],deps=[d("d","a","a")]).valid_graph)
 def test_duplicate_evidence_rejected(self):self.assertFalse(self.run_graph(["a"],[ev("e","a"),ev("e","a")]).valid_graph)
 def test_unknown_claim_rejected(self):self.assertFalse(self.run_graph(["a"],[ev("e","missing")]).valid_graph)
 def test_conflict_not_erased(self):
  r=self.run_graph(["a"],[ev("s","a"),ev("c","a",EvidencePolarity.COUNTER)],[j("a",EpistemicState.CONFLICTED)])
  self.assertEqual(self.state(r,"a"),EpistemicState.CONFLICTED)
 def test_semantic_truth_not_established(self):
  r=self.run_graph(["a"],[ev("e","a")],[j("a",EpistemicState.PROVISIONAL)])
  self.assertFalse(r.records[0].semantic_truth_established)
 def test_independent_branch_unaffected(self):
  r=self.run_graph(["a","b","z"],[ev("c","a",EvidencePolarity.COUNTER)],[j("a",EpistemicState.WEAKENED)],[ ],[d("d","a","b")])
  self.assertEqual(self.state(r,"z"),EpistemicState.UNKNOWN)
 def test_hard_stale_propagates(self):
  jg=ClaimJudgement("a",EpistemicState.STALE,"Source revision invalidated current support.")
  r=self.run_graph(["a","b"],jgs=[jg],deps=[d("d","a","b")]);self.assertEqual(self.state(r,"b"),EpistemicState.STALE)
 def test_qualifier_does_not_count_as_support(self):
  r=self.run_graph(["a"],[ev("q","a",EvidencePolarity.QUALIFIER)])
  self.assertEqual(self.state(r,"a"),EpistemicState.INSUFFICIENT)
 def test_revalidation_requires_revision_id(self):
  bad=ClaimJudgement("a",EpistemicState.REVALIDATED,"Reviewed.",("r",))
  self.assertFalse(self.run_graph(["a"],jgs=[bad]).valid_graph)
if __name__=="__main__":unittest.main()
