import unittest
from prototype.yixiang_analogy_transfer_audit import *

def proposal(**changes):
    values=dict(proposal_id="p1",source_case_id="source",target_case_id="target",shared_features=("same category label",),transferred_claim="transfer predicate P",source_warrant="source warrant",target_warrant="target warrant",source_relation_signature=("agent","acts_on","object"),target_relation_signature=("agent","acts_on","object"),source_scope="same stated domain",target_scope="same stated domain",evidence_refs=("text:1",),condition_refs=("condition:1",),counterexample_refs=(),reviewed=True,warrant_comparable=True,relation_preserved=True,scope_compatible=True)
    values.update(changes)
    return AnalogyProposal(**values)

class M17Tests(unittest.TestCase):
    def test_all_declared_gates_pass_only_provisionally(self):
        result=assess_analogy_transfer(proposal())
        self.assertEqual(result.status,TransferStatus.PROVISIONAL_TRANSFER)
        self.assertFalse(result.transfer_truth_established)
        self.assertFalse(result.semantic_validity_established)
    def test_unreviewed_proposal_never_passes(self): self.assertEqual(assess_analogy_transfer(proposal(reviewed=False)).status,TransferStatus.UNREVIEWED)
    def test_explicit_counterexample_blocks_transfer(self): self.assertEqual(assess_analogy_transfer(proposal(counterexample_refs=("counterexample:1",))).status,TransferStatus.COUNTEREXAMPLE_BLOCKED)
    def test_warrant_mismatch_blocks(self): self.assertEqual(assess_analogy_transfer(proposal(warrant_comparable=False)).status,TransferStatus.WARRANT_MISMATCH)
    def test_relation_mismatch_blocks(self): self.assertEqual(assess_analogy_transfer(proposal(relation_preserved=False)).status,TransferStatus.RELATION_MISMATCH)
    def test_scope_mismatch_blocks(self): self.assertEqual(assess_analogy_transfer(proposal(scope_compatible=False)).status,TransferStatus.SCOPE_MISMATCH)
    def test_missing_evidence_does_not_pass(self): self.assertEqual(assess_analogy_transfer(proposal(evidence_refs=())).status,TransferStatus.MISSING_EVIDENCE)
    def test_unknown_gate_remains_indeterminate(self):
        result=assess_analogy_transfer(proposal(warrant_comparable=None))
        self.assertEqual(result.status,TransferStatus.INDETERMINATE)
        self.assertEqual(result.unresolved_gates,("warrant_comparable",))
    def test_multiple_failed_gates_are_preserved(self): self.assertEqual(assess_analogy_transfer(proposal(warrant_comparable=False,relation_preserved=False)).failed_gates,("warrant_comparable","relation_preserved"))
    def test_counterexample_precedes_other_failed_gates_after_review(self): self.assertEqual(assess_analogy_transfer(proposal(counterexample_refs=("ce:1",),scope_compatible=False)).status,TransferStatus.COUNTEREXAMPLE_BLOCKED)
    def test_shared_features_cannot_replace_warrant(self): self.assertEqual(assess_analogy_transfer(proposal(shared_features=("same appearance","same name"),warrant_comparable=None)).status,TransferStatus.INDETERMINATE)
    def test_source_and_target_must_be_distinct(self):
        with self.assertRaises(ValueError): assess_analogy_transfer(proposal(target_case_id="source"))
    def test_duplicate_evidence_refs_rejected(self):
        with self.assertRaises(ValueError): assess_analogy_transfer(proposal(evidence_refs=("text:1","text:1")))
    def test_relation_signatures_are_explicit(self): self.assertEqual(assess_analogy_transfer(proposal(target_relation_signature=("agent","owns","object"),relation_preserved=False)).status,TransferStatus.RELATION_MISMATCH)
    def test_truth_fields_are_never_certified(self):
        result=assess_analogy_transfer(proposal())
        self.assertFalse(result.transfer_truth_established)
        self.assertFalse(result.semantic_validity_established)
        self.assertEqual(result.adjudication,"human_review_required")

if __name__=="__main__": unittest.main()