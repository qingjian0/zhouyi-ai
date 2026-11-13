import unittest
from prototype.yixiang_relation_invariants import (
    InvariantCheck, InvariantDecision, RelationEdge, RelationFrame,
    RelationTransferContract, assess_relation_transfer,
)

class RelationInvariantTests(unittest.TestCase):
    def frame(self, fid, domain, roles, edges, conditions=(("phase","stable"),), evidence=("witness:1",)):
        return RelationFrame(fid, domain, roles, edges, conditions, evidence)
    def contract(self, **changes):
        source = self.frame("source","source-domain",("agent","tool","goal"),(
            RelationEdge("uses","agent","tool"), RelationEdge("achieves","agent","goal",order=1)))
        target = self.frame("target","target-domain",("actor","means","end"),(
            RelationEdge("uses","actor","means"), RelationEdge("achieves","actor","end",order=1)),evidence=("witness:2",))
        values=dict(transfer_id="ri-001",source=source,target=target,
            role_mapping=(("agent","actor"),("tool","means"),("goal","end")),
            required_context_axes=("phase",), required_invariants=("goal_relation",),
            invariant_checks=(InvariantCheck("goal_relation","same-goal","same-goal","src:1","tgt:1"),))
        values.update(changes)
        return RelationTransferContract(**values)
    def test_isomorphic_role_mapped_relation_is_accepted_scoped(self):
        r=assess_relation_transfer(self.contract())
        self.assertEqual(r.decision,InvariantDecision.ACCEPT_SCOPED)
        self.assertIn("goal_relation",r.preserved_invariants)
        self.assertFalse(r.empirical_causality_established)
    def test_reversed_edge_direction_is_rejected(self):
        t=self.frame("target","target-domain",("actor","means","end"),(
            RelationEdge("uses","means","actor"),RelationEdge("achieves","actor","end",order=1)),evidence=("witness:2",))
        r=assess_relation_transfer(self.contract(target=t))
        self.assertEqual(r.decision,InvariantDecision.REJECT)
        self.assertIn("RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH",r.reason_codes)
    def test_process_order_change_is_rejected(self):
        t=self.frame("target","target-domain",("actor","means","end"),(
            RelationEdge("uses","actor","means",order=1),
            RelationEdge("achieves","actor","end",order=0)),evidence=("witness:2",))
        r=assess_relation_transfer(self.contract(target=t))
        self.assertEqual(r.decision,InvariantDecision.REJECT)
        self.assertIn("RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH",r.reason_codes)
    def test_same_goal_different_mechanism_is_rejected(self):
        t=self.frame("target","target-domain",("actor","means","end"),(
            RelationEdge("delegates_to","actor","means"),RelationEdge("achieves","means","end",order=1)),evidence=("witness:2",))
        self.assertEqual(assess_relation_transfer(self.contract(target=t)).decision,InvariantDecision.REJECT)
    def test_incomplete_role_mapping_abstains(self):
        r=assess_relation_transfer(self.contract(role_mapping=(("agent","actor"),("tool","means"))))
        self.assertEqual(r.decision,InvariantDecision.ABSTAIN)
        self.assertIn("ROLE_MAPPING_INCOMPLETE",r.reason_codes)
    def test_unmapped_target_role_abstains_before_topology_comparison(self):
        t=self.frame("target","target-domain",("actor","means","end","observer"),(
            RelationEdge("uses","actor","means"),
            RelationEdge("achieves","actor","end",order=1),
            RelationEdge("observes","observer","end",order=2)),evidence=("witness:2",))
        r=assess_relation_transfer(self.contract(target=t))
        self.assertEqual(r.decision,InvariantDecision.ABSTAIN)
        self.assertIn("ROLE_MAPPING_INCOMPLETE",r.reason_codes)
    def test_critical_invariant_mismatch_is_rejected(self):
        c=InvariantCheck("goal_relation","same-goal","different-goal","src:1","tgt:1")
        self.assertEqual(assess_relation_transfer(self.contract(invariant_checks=(c,))).decision,InvariantDecision.REJECT)
    def test_context_mismatch_abstains(self):
        t=self.frame("target","target-domain",("actor","means","end"),(
            RelationEdge("uses","actor","means"),RelationEdge("achieves","actor","end",order=1)),
            conditions=(("phase","transitional"),),evidence=("witness:2",))
        r=assess_relation_transfer(self.contract(target=t))
        self.assertEqual(r.decision,InvariantDecision.ABSTAIN)
        self.assertIn("REQUIRED_CONTEXT_AXIS_MISMATCH",r.reason_codes)
    def test_missing_side_evidence_abstains(self):
        s=self.frame("source","source-domain",("agent","tool","goal"),(
            RelationEdge("uses","agent","tool"),RelationEdge("achieves","agent","goal",order=1)),evidence=())
        self.assertIn("SIDE_SPECIFIC_EVIDENCE_MISSING",assess_relation_transfer(self.contract(source=s)).reason_codes)
    def test_unresolved_defeater_abstains(self):
        self.assertEqual(assess_relation_transfer(self.contract(unresolved_defeaters=("mechanism unknown",))).decision,InvariantDecision.ABSTAIN)
    def test_causal_transfer_never_self_certifies(self):
        r=assess_relation_transfer(self.contract(causal_transfer=True))
        self.assertIn("CAUSAL_TRANSFER_WITHOUT_CAUSAL_EVIDENCE",r.reason_codes)
        self.assertFalse(r.empirical_causality_established)
        r=assess_relation_transfer(self.contract(causal_transfer=True,causal_evidence_refs=("study:1",)))
        self.assertFalse(r.empirical_causality_established)
    def test_required_invariant_cannot_be_omitted(self):
        r=assess_relation_transfer(self.contract(invariant_checks=()))
        self.assertEqual(r.decision,InvariantDecision.ABSTAIN)
        self.assertIn("REQUIRED_INVARIANT_NOT_ASSESSED",r.reason_codes)
    def test_duplicate_role_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError,"one-to-one"):
            assess_relation_transfer(self.contract(role_mapping=(("agent","actor"),("tool","actor"),("goal","end"))))
    def test_duplicate_invariant_names_rejected(self):
        x=InvariantCheck("same","x","x","s","t")
        with self.assertRaisesRegex(ValueError,"unique"):
            assess_relation_transfer(self.contract(invariant_checks=(x,x)))

if __name__=="__main__": unittest.main()
