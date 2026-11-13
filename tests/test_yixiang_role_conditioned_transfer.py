import unittest
from prototype.yixiang_role_conditioned_transfer import (
    ContextTransform, MechanismStep, TransferContract, TransferDecision,
    TransferFrame, assess_role_conditioned_transfer,
)

def frame(fid, domain, context="spring", operation="transform", evidence=None):
    return TransferFrame(fid, domain, ("agent", "object", "result"),
        (("supports", "agent", "object", "positive", 0),
         ("produces", "object", "result", "positive", 1)),
        (MechanismStep(operation, "agent", "object", "result", 0),
         MechanismStep("complete", "agent", "result", "result", 1)),
        (("season", context), ("task", "preserve")),
        tuple(evidence if evidence is not None else (fid + "-text",)))

def contract(source=None, target=None, **kw):
    return TransferContract("case", source or frame("s", "source"),
        target or frame("t", "target"),
        (("agent", "agent"), ("object", "object"), ("result", "result")),
        ("season", "task"), **kw)

class M13Tests(unittest.TestCase):
    def test_exact_match_scoped(self):
        r=assess_role_conditioned_transfer(contract())
        self.assertEqual(r.decision, TransferDecision.ACCEPT_SCOPED)
        self.assertEqual(r.preserved_relation_count, 2)
        self.assertEqual(r.preserved_mechanism_steps, 2)
    def test_direction_reversal_rejected(self):
        t=frame("t","target")
        t=TransferFrame(t.frame_id,t.domain,t.roles,(("supports","object","agent","positive",0),t.relation_edges[1]),t.mechanism,t.context_axes,t.evidence_refs)
        self.assertEqual(assess_role_conditioned_transfer(contract(target=t)).decision,TransferDecision.REJECT)
    def test_polarity_reversal_rejected(self):
        t=frame("t","target")
        t=TransferFrame(t.frame_id,t.domain,t.roles,(("supports","agent","object","negative",0),t.relation_edges[1]),t.mechanism,t.context_axes,t.evidence_refs)
        self.assertEqual(assess_role_conditioned_transfer(contract(target=t)).decision,TransferDecision.REJECT)
    def test_mechanism_operation_change_rejected(self):
        self.assertEqual(assess_role_conditioned_transfer(contract(target=frame("t","target",operation="filter"))).decision,TransferDecision.REJECT)
    def test_mechanism_role_change_rejected(self):
        t=frame("t","target")
        steps=(t.mechanism[0],MechanismStep("complete","object","result","result",1))
        t=TransferFrame(t.frame_id,t.domain,t.roles,t.relation_edges,steps,t.context_axes,t.evidence_refs)
        self.assertEqual(assess_role_conditioned_transfer(contract(target=t)).decision,TransferDecision.REJECT)
    def test_mechanism_order_change_rejected(self):
        t=frame("t","target")
        steps=(MechanismStep("complete","agent","result","result",0),MechanismStep("transform","agent","object","result",1))
        t=TransferFrame(t.frame_id,t.domain,t.roles,t.relation_edges,steps,t.context_axes,t.evidence_refs)
        self.assertEqual(assess_role_conditioned_transfer(contract(target=t)).decision,TransferDecision.REJECT)
    def test_context_mismatch_abstains(self):
        r=assess_role_conditioned_transfer(contract(target=frame("t","target",context="winter")))
        self.assertEqual(r.decision,TransferDecision.ABSTAIN)
        self.assertEqual(r.mismatched_context_axes,("season",))
    def test_missing_context_abstains(self):
        t=frame("t","target")
        t=TransferFrame(t.frame_id,t.domain,t.roles,t.relation_edges,t.mechanism,(("task","preserve"),),t.evidence_refs)
        self.assertEqual(assess_role_conditioned_transfer(contract(target=t)).decision,TransferDecision.ABSTAIN)
    def test_evidence_backed_context_transform_scoped(self):
        t=frame("t","target",context="winter")
        x=ContextTransform("season","spring","winter","adapt","temperature bounded","s-text","t-text")
        r=assess_role_conditioned_transfer(contract(target=t,context_transforms=(x,)))
        self.assertEqual(r.decision,TransferDecision.ACCEPT_SCOPED)
        self.assertEqual(r.transformed_context_axes,("season",))
    def test_unanchored_transform_rejected_as_input(self):
        t=frame("t","target",context="winter")
        x=ContextTransform("season","spring","winter","adapt","bounded","bad-ref","t-text")
        with self.assertRaises(ValueError): assess_role_conditioned_transfer(contract(target=t,context_transforms=(x,)))
    def test_wrong_transform_values_abstain(self):
        t=frame("t","target",context="winter")
        x=ContextTransform("season","autumn","winter","adapt","bounded","s-text","t-text")
        self.assertEqual(assess_role_conditioned_transfer(contract(target=t,context_transforms=(x,))).decision,TransferDecision.ABSTAIN)
    def test_missing_evidence_abstains(self):
        self.assertEqual(assess_role_conditioned_transfer(contract(source=frame("s","source",evidence=()))).decision,TransferDecision.ABSTAIN)
    def test_reused_evidence_abstains(self):
        r=assess_role_conditioned_transfer(contract(source=frame("s","source",evidence=("shared",)),target=frame("t","target",evidence=("shared",))))
        self.assertEqual(r.decision,TransferDecision.ABSTAIN)
    def test_unresolved_defeater_abstains(self):
        self.assertEqual(assess_role_conditioned_transfer(contract(unresolved_defeaters=("open-counterexample",))).decision,TransferDecision.ABSTAIN)
    def test_incomplete_role_map_invalid(self):
        c=contract()
        bad=TransferContract(c.transfer_id,c.source,c.target,(("agent","agent"),),c.required_context_axes)
        with self.assertRaises(ValueError): assess_role_conditioned_transfer(bad)
    def test_non_bijective_role_map_invalid(self):
        c=contract()
        bad=TransferContract(c.transfer_id,c.source,c.target,(("agent","agent"),("object","agent"),("result","result")),c.required_context_axes)
        with self.assertRaises(ValueError): assess_role_conditioned_transfer(bad)
    def test_required_predicate_missing_abstains(self):
        self.assertEqual(assess_role_conditioned_transfer(contract(required_relation_predicates=("causes",))).decision,TransferDecision.ABSTAIN)
    def test_required_operation_missing_abstains(self):
        self.assertEqual(assess_role_conditioned_transfer(contract(required_mechanism_operations=("transmit",))).decision,TransferDecision.ABSTAIN)
    def test_never_claims_causality(self):
        r=assess_role_conditioned_transfer(contract())
        self.assertTrue(r.scope_only)
        self.assertFalse(r.causal_transfer_established)

if __name__ == "__main__":
    unittest.main()
