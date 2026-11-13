import unittest

from prototype.classical_lexical_analysis import (
    EvidenceStatus, LexicalComparison, LexicalDecision, LexicalOccurrence,
    LexicalRelation, assess_lexical_comparison,
)


class LexicalAnalysisTests(unittest.TestCase):
    def occurrence(self, oid, form, sense, referent):
        return LexicalOccurrence(
            occurrence_id=oid, surface_form=form, work_id="work-a",
            passage_ref=f"chapter:{oid}", sense_id=sense, referent_id=referent,
            period="pre_qin", evidence_status=EvidenceStatus.VERIFIED_PRIMARY_WITNESS,
            context="足够的原文上下文",
        )

    def comparison(self, relation, left=None, right=None, **kw):
        return LexicalComparison(
            comparison_id="cmp-1", left=left or self.occurrence("a", "象", "sense-a", "referent-a"),
            right=right or self.occurrence("b", "象", "sense-b", "referent-b"),
            proposed_relation=relation, left_witness_refs=("edition-a:p1",),
            right_witness_refs=("edition-b:p2",),
            scope_conditions=("限定于所引篇章",), **kw,
        )

    def test_same_form_different_sense_requires_distinction(self):
        item = self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE,
                               distinction_notes=("两处语境义不同",))
        self.assertEqual(assess_lexical_comparison(item).decision, LexicalDecision.ACCEPT_AS_SCOPED)

    def test_same_form_different_sense_without_note_abstains(self):
        result = assess_lexical_comparison(self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE))
        self.assertEqual(result.decision, LexicalDecision.ABSTAIN)
        self.assertIn("MISSING_SENSE_DISTINCTION", result.reason_codes)

    def test_different_forms_same_referent_requires_basis(self):
        left = self.occurrence("a", "马", "sense-horse", "animal-1")
        right = self.occurrence("b", "骊", "sense-black-horse", "animal-1")
        item = self.comparison(LexicalRelation.DIFFERENT_FORM_SAME_REFERENT,
                               left, right, distinction_notes=("文献与名物证据链",))
        self.assertEqual(assess_lexical_comparison(item).decision, LexicalDecision.ACCEPT_AS_SCOPED)

    def test_surface_similarity_cannot_prove_same_referent(self):
        left = self.occurrence("a", "马", "sense-a", "animal-1")
        right = self.occurrence("b", "骊", "sense-b", "animal-2")
        item = self.comparison(LexicalRelation.DIFFERENT_FORM_SAME_REFERENT,
                               left, right, distinction_notes=("仅凭词形",))
        self.assertEqual(assess_lexical_comparison(item).decision, LexicalDecision.REJECT)

    def test_model_generated_witness_abstains(self):
        left = self.occurrence("a", "类", "sense-a", "r1")
        right = self.occurrence("b", "类", "sense-b", "r2")
        right = LexicalOccurrence(**{**right.__dict__, "evidence_status": EvidenceStatus.MODEL_PROPOSAL})
        item = self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE, left, right,
                               distinction_notes=("待核",))
        self.assertEqual(assess_lexical_comparison(item).decision, LexicalDecision.ABSTAIN)

    def test_missing_contextual_scope_abstains(self):
        item = self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE,
                               distinction_notes=("语义差别",), scope_conditions=())
        result = assess_lexical_comparison(item)
        self.assertEqual(result.decision, LexicalDecision.ABSTAIN)
        self.assertIn("MISSING_SCOPE_CONDITIONS", result.reason_codes)

    def test_secondary_quotation_cannot_be_primary_witness(self):
        left = self.occurrence("a", "名", "s1", "r1")
        right = self.occurrence("b", "名", "s2", "r2")
        right = LexicalOccurrence(**{**right.__dict__, "evidence_status": EvidenceStatus.SECONDARY_QUOTATION})
        item = self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE, left, right,
                               distinction_notes=("语境差异",))
        result = assess_lexical_comparison(item)
        self.assertEqual(result.decision, LexicalDecision.ABSTAIN)

    def test_each_side_needs_its_own_witness_reference(self):
        item = self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE,
                               distinction_notes=("语境差异",), right_witness_refs=())
        result = assess_lexical_comparison(item)
        self.assertEqual(result.decision, LexicalDecision.ABSTAIN)
        self.assertIn("MISSING_SIDE_SPECIFIC_WITNESS_REFERENCES", result.reason_codes)

    def test_inconsistent_relation_is_rejected(self):
        left = self.occurrence("a", "类", "s1", "r1")
        right = self.occurrence("b", "象", "s2", "r2")
        item = self.comparison(LexicalRelation.SAME_FORM_DIFFERENT_SENSE, left, right,
                               distinction_notes=("不同字形",))
        self.assertEqual(assess_lexical_comparison(item).decision, LexicalDecision.REJECT)


if __name__ == "__main__":
    unittest.main()
