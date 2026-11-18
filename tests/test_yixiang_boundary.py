import unittest

from prototype.yixiang_boundary import (
    BoundaryCase, BoundaryStatus, CategoryDefinition, CategoryLifecycle,
    CategoryMembership, audit_categories,
)


def cat(cid, **changes):
    data = dict(category_id=cid, name=cid.title(), axis="form", criterion="shares the declared contour")
    data.update(changes)
    return CategoryDefinition(**data)


def member(mid, cid, **changes):
    data = dict(membership_id=mid, subject_id="object-1", category_id=cid,
                context_id="ctx-A", context_version=1, status=BoundaryStatus.INCLUDED,
                feature_refs=("f-1",), evidence_refs=("e-1",), rationale="criterion supported")
    data.update(changes)
    return CategoryMembership(**data)


class BoundaryHierarchyTests(unittest.TestCase):
    def test_multiple_categories_are_allowed(self):
        result = audit_categories([cat("animal"), cat("tool")],
                                  [member("m1", "animal"), member("m2", "tool")],
                                  known_features=["f-1"])
        self.assertTrue(result.valid)
        self.assertEqual(result.multi_membership_groups, (("object-1", "ctx-A", ("animal", "tool")),))

    def test_hierarchy_is_allowed(self):
        result = audit_categories([cat("living"), cat("animal", parent_ids=("living",))], [])
        self.assertTrue(result.valid)

    def test_unknown_parent_is_rejected(self):
        result = audit_categories([cat("animal", parent_ids=("living",))], [])
        self.assertIn("unknown_parent:animal:living", result.issues)

    def test_hierarchy_cycle_is_rejected(self):
        result = audit_categories([cat("a", parent_ids=("b",)), cat("b", parent_ids=("a",))], [])
        self.assertIn("category_hierarchy_cycle", result.issues)

    def test_missing_criterion_is_rejected(self):
        result = audit_categories([cat("a", criterion="")], [])
        self.assertIn("missing_category_criterion:a", result.issues)

    def test_missing_membership_evidence_is_rejected(self):
        result = audit_categories([cat("a")], [member("m", "a", evidence_refs=())])
        self.assertIn("missing_membership_evidence:m", result.issues)

    def test_unknown_feature_is_rejected_when_registry_supplied(self):
        result = audit_categories([cat("a")], [member("m", "a")], known_features=["f-2"])
        self.assertIn("unknown_feature_reference:m", result.issues)

    def test_context_versions_are_separate_groups(self):
        result = audit_categories([cat("a"), cat("b")],
            [member("m1", "a"), member("m2", "b", context_id="ctx-B")])
        self.assertEqual(result.multi_membership_groups, ())

    def test_undecided_does_not_count_as_membership(self):
        result = audit_categories([cat("a"), cat("b")],
            [member("m1", "a"), member("m2", "b", status=BoundaryStatus.UNDECIDED)])
        self.assertEqual(result.multi_membership_groups, ())

    def test_excluded_case_is_preserved_as_boundary_record(self):
        case = BoundaryCase("b1", "object-1", "a", "ctx-A", 1, BoundaryStatus.EXCLUDED,
                            "fails contour criterion", ("e-2",), "similar surface but wrong structure")
        result = audit_categories([cat("a")], [], [case])
        self.assertTrue(result.valid)

    def test_deprecated_category_requires_successor(self):
        result = audit_categories([cat("old", lifecycle=CategoryLifecycle.DEPRECATED)], [])
        self.assertIn("deprecated_without_successor:old", result.issues)

    def test_deprecated_membership_is_flagged(self):
        result = audit_categories(
            [cat("old", lifecycle=CategoryLifecycle.DEPRECATED, successor_ids=("new",)), cat("new")],
            [member("m", "old")])
        self.assertIn("membership_in_deprecated_category:m", result.issues)

    def test_unknown_successor_is_rejected(self):
        result = audit_categories([cat("old", lifecycle=CategoryLifecycle.DEPRECATED,
                                       successor_ids=("missing",))], [])
        self.assertIn("unknown_successor:old:missing", result.issues)

    def test_duplicate_category_id_is_rejected(self):
        result = audit_categories([cat("a"), cat("a")], [])
        self.assertIn("duplicate_category_id", result.issues)

    def test_duplicate_membership_id_is_rejected(self):
        result = audit_categories([cat("a")], [member("m", "a"), member("m", "a")])
        self.assertIn("duplicate_membership_id:m", result.issues)

    def test_unknown_category_membership_is_rejected(self):
        result = audit_categories([cat("a")], [member("m", "missing")])
        self.assertIn("unknown_membership_category:m", result.issues)

    def test_missing_boundary_evidence_is_rejected(self):
        case = BoundaryCase("b1", "o", "a", "c", 1, BoundaryStatus.UNDECIDED,
                            "criterion", (), "review pending")
        result = audit_categories([cat("a")], [], [case])
        self.assertIn("missing_boundary_evidence:b1", result.issues)

    def test_invalid_context_version_is_rejected(self):
        result = audit_categories([cat("a")], [member("m", "a", context_version=0)])
        self.assertIn("invalid_membership_context:m", result.issues)


if __name__ == "__main__":
    unittest.main()
