import unittest

from prototype.yixiang_taxonomic_scope import (
    PredicateScope, TaxonomicDecision, TaxonomicRelation,
    TaxonomicTransferClaim, assess_taxonomic_transfer,
)


class TaxonomicScopeTests(unittest.TestCase):
    def claim(self, **overrides):
        values = dict(
            claim_id="tax-001",
            source_category="four-footed-beasts",
            target_category="horses",
            relation=TaxonomicRelation.TARGET_SUBCLASS_OF_SOURCE,
            predicate="has-four-feet",
            predicate_scope=PredicateScope.UNIVERSAL,
            shared_basis=("category inclusion relation",),
            membership_evidence=("taxonomy:horse-is-four-footed-beast",),
            scope_conditions=("ordinary adult horses",),
            inheritance_evidence=("definition:four-footed-beast",),
        )
        values.update(overrides)
        return TaxonomicTransferClaim(**values)

    def test_universal_parent_predicate_can_be_applied_downward_with_membership(self):
        result = assess_taxonomic_transfer(self.claim())
        self.assertEqual(result.decision, TaxonomicDecision.SCOPE_RECORDED)
        self.assertTrue(result.predicate_inheritance_authorized)

    def test_individual_property_cannot_be_inherited_downward(self):
        result = assess_taxonomic_transfer(self.claim(
            predicate_scope=PredicateScope.INDIVIDUAL_SPECIFIC,
        ))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("PREDICATE_NOT_INHERITABLE_TO_SUBCLASS", result.reason_codes)

    def test_subclass_specific_property_cannot_be_promoted_to_parent(self):
        result = assess_taxonomic_transfer(self.claim(
            relation=TaxonomicRelation.SOURCE_SUBCLASS_OF_TARGET,
            predicate_scope=PredicateScope.SUBCLASS_SPECIFIC,
            counterexample_search_performed=True,
        ))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("NON_UNIVERSAL_PREDICATE_CANNOT_BE_PROMOTED_UPWARD",
                      result.reason_codes)

    def test_upward_generalization_requires_counterexample_search(self):
        result = assess_taxonomic_transfer(self.claim(
            relation=TaxonomicRelation.SOURCE_SUBCLASS_OF_TARGET,
            predicate_scope=PredicateScope.UNIVERSAL,
        ))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("UPWARD_GENERALIZATION_REQUIRES_COUNTEREXAMPLE_SEARCH",
                      result.reason_codes)

    def test_universal_upward_transfer_requires_inheritance_evidence(self):
        result = assess_taxonomic_transfer(self.claim(
            relation=TaxonomicRelation.SOURCE_SUBCLASS_OF_TARGET,
            predicate_scope=PredicateScope.UNIVERSAL,
            inheritance_evidence=(),
            counterexample_search_performed=True,
        ))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("UNIVERSAL_SCOPE_EVIDENCE_MISSING", result.reason_codes)

    def test_upward_generalization_with_counterexample_is_not_accepted_blindly(self):
        result = assess_taxonomic_transfer(self.claim(
            relation=TaxonomicRelation.SOURCE_SUBCLASS_OF_TARGET,
            predicate_scope=PredicateScope.UNIVERSAL,
            counterexample_search_performed=True,
            counterexample_refs=("counterexample:nonmember",),
        ))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("COUNTEREXAMPLE_REQUIRES_SCOPE_REFINEMENT", result.reason_codes)

    def test_sibling_transfer_requires_shared_universal_rule(self):
        result = assess_taxonomic_transfer(self.claim(
            relation=TaxonomicRelation.SIBLING_CATEGORIES,
            inheritance_evidence=(),
        ))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("SIBLING_TRANSFER_REQUIRES_SHARED_RULE_EVIDENCE",
                      result.reason_codes)

    def test_missing_shared_basis_is_rejected(self):
        result = assess_taxonomic_transfer(self.claim(shared_basis=()))
        self.assertEqual(result.decision, TaxonomicDecision.REJECT)
        self.assertIn("SHARED_BASIS_MISSING", result.reason_codes)

    def test_missing_membership_evidence_abstains(self):
        result = assess_taxonomic_transfer(self.claim(membership_evidence=()))
        self.assertEqual(result.decision, TaxonomicDecision.ABSTAIN)
        self.assertIn("CATEGORY_MEMBERSHIP_UNGROUNDED", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
