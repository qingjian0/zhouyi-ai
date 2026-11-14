import unittest

from prototype.yixiang_intercategory import (
    CategoryRef, CrossAxisMapping, InferenceClaim, InferencePermission,
    InterCategoryRelation, RelationKind, audit_intercategory_relations,
)


def rel(kind=RelationKind.SIMILARITY, **changes):
    data = dict(relation_id="r1", source_category_id="form-A", target_category_id="function-B",
                kind=kind, scope="within the stated comparison task", context_id="ctx-1",
                context_version=1, evidence_refs=("e1",), rationale="declared basis",
                direction="directed")
    data.update(changes)
    return InterCategoryRelation(**data)


def claim(permission=InferencePermission.COMPARE_ONLY, **changes):
    data = dict(claim_id="c1", relation_id="r1", permission=permission,
                conclusion="comparison only", scope="bounded task",
                evidence_refs=("e2",), rationale="explicit warrant")
    data.update(changes)
    return InferenceClaim(**data)


class InterCategoryRelationTests(unittest.TestCase):
    def setUp(self):
        self.categories = [CategoryRef("form-A", "form"), CategoryRef("function-B", "function")]

    def test_bounded_similarity_is_valid(self):
        self.assertTrue(audit_intercategory_relations(self.categories, [rel()]).valid)

    def test_structural_relation_allows_relation_transfer(self):
        result = audit_intercategory_relations(self.categories, [rel(RelationKind.STRUCTURAL)],
                                               claims=[claim(InferencePermission.TRANSFER_RELATION)])
        self.assertTrue(result.valid)

    def test_similarity_does_not_authorize_relation_transfer(self):
        result = audit_intercategory_relations(self.categories, [rel()],
                                               claims=[claim(InferencePermission.TRANSFER_RELATION)])
        self.assertIn("relation_transfer_not_supported_by_relation_kind:c1", result.issues)

    def test_causal_hypothesis_requires_causal_relation(self):
        result = audit_intercategory_relations(self.categories, [rel()],
                                               claims=[claim(InferencePermission.CAUSAL_HYPOTHESIS)])
        self.assertIn("causal_claim_without_causal_relation:c1", result.issues)

    def test_causal_relation_must_be_directed(self):
        result = audit_intercategory_relations(self.categories,
                                               [rel(RelationKind.CAUSAL, direction="undirected")])
        self.assertIn("causal_relation_must_be_directed:r1", result.issues)

    def test_relation_requires_evidence(self):
        result = audit_intercategory_relations(self.categories, [rel(evidence_refs=())])
        self.assertIn("missing_relation_evidence:r1", result.issues)

    def test_relation_requires_scope(self):
        result = audit_intercategory_relations(self.categories, [rel(scope="")])
        self.assertIn("missing_relation_scope:r1", result.issues)

    def test_unknown_endpoint_is_rejected(self):
        result = audit_intercategory_relations(self.categories, [rel(target_category_id="unknown")])
        self.assertIn("unknown_relation_endpoint:r1", result.issues)

    def test_context_version_is_required(self):
        result = audit_intercategory_relations(self.categories, [rel(context_version=0)])
        self.assertIn("invalid_relation_context:r1", result.issues)

    def test_cross_axis_mapping_is_valid_when_axes_match_endpoints(self):
        mapping = CrossAxisMapping("m1", "form", "function", "form-A", "function-B",
                                   "map contour to affordance only under task X", "task X",
                                   "ctx-1", 1, ("e3",), "mapping evidence")
        self.assertTrue(audit_intercategory_relations(self.categories, [], [mapping]).valid)

    def test_mapping_cannot_claim_wrong_axis(self):
        mapping = CrossAxisMapping("m1", "time", "function", "form-A", "function-B",
                                   "rule", "scope", "ctx", 1, ("e",), "why")
        result = audit_intercategory_relations(self.categories, [], [mapping])
        self.assertIn("mapping_axis_endpoint_mismatch:m1", result.issues)

    def test_same_axis_is_not_cross_axis_mapping(self):
        mapping = CrossAxisMapping("m1", "form", "form", "form-A", "form-A",
                                   "rule", "scope", "ctx", 1, ("e",), "why")
        result = audit_intercategory_relations(self.categories, [], [mapping])
        self.assertIn("mapping_not_cross_axis:m1", result.issues)

    def test_mapping_requires_evidence(self):
        mapping = CrossAxisMapping("m1", "form", "function", "form-A", "function-B",
                                   "rule", "scope", "ctx", 1, (), "why")
        result = audit_intercategory_relations(self.categories, [], [mapping])
        self.assertIn("missing_mapping_evidence:m1", result.issues)

    def test_unknown_claim_relation_is_rejected(self):
        result = audit_intercategory_relations(self.categories, [], claims=[claim(relation_id="missing")])
        self.assertIn("unknown_claim_relation:c1", result.issues)

    def test_feature_transfer_from_similarity_is_allowed_but_bounded(self):
        result = audit_intercategory_relations(self.categories, [rel()],
                                               claims=[claim(InferencePermission.TRANSFER_FEATURE)])
        self.assertTrue(result.valid)

    def test_feature_transfer_from_temporal_relation_is_rejected(self):
        result = audit_intercategory_relations(self.categories, [rel(RelationKind.TEMPORAL)],
                                               claims=[claim(InferencePermission.TRANSFER_FEATURE)])
        self.assertIn("feature_transfer_not_supported_by_relation_kind:c1", result.issues)

    def test_blocked_claim_cannot_assert_conclusion(self):
        result = audit_intercategory_relations(self.categories, [rel()],
            claims=[claim(InferencePermission.BLOCKED, conclusion="therefore identical")])
        self.assertIn("blocked_claim_must_not_assert_conclusion:c1", result.issues)

    def test_duplicate_relation_id_is_rejected(self):
        result = audit_intercategory_relations(self.categories, [rel(), rel()])
        self.assertIn("duplicate_relation_id:r1", result.issues)

    def test_invalid_direction_is_rejected(self):
        result = audit_intercategory_relations(self.categories, [rel(direction="sideways")])
        self.assertIn("invalid_relation_direction:r1", result.issues)

    def test_duplicate_claim_id_is_rejected(self):
        result = audit_intercategory_relations(self.categories, [rel()], [ ], [claim(), claim()])
        self.assertIn("duplicate_claim_id:c1", result.issues)


if __name__ == "__main__":
    unittest.main()
