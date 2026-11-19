import unittest

from prototype.classiang_engine import FeatureAtom
from prototype.classiang_discovery import ObjectView, discover_classes


def obj(name, features):
    return ObjectView(name, tuple(sorted(features)), (f"source:{name}",))


class ClassiangDiscoveryTests(unittest.TestCase):
    def test_discovers_recurring_conjunction_and_tracks_evidence(self):
        common = FeatureAtom("function", "transfers-load")
        nuisance = FeatureAtom("attribute", "blue")
        rows = (
            obj("a", (common, nuisance)), obj("b", (common,)),
            obj("c", (common, nuisance)), obj("d", (nuisance,)),
        )
        result = discover_classes(rows, min_support=0.5, max_order=2)
        pair = next(c for c in result.candidates
                    if c.features == tuple(sorted((common, nuisance))))
        self.assertEqual(pair.support_count, 2)
        self.assertEqual(pair.support, 0.5)
        self.assertEqual(pair.member_object_ids, ("a", "c"))
        self.assertEqual(pair.evidence_refs, ("source:a", "source:c"))
        self.assertEqual(pair.status, "unreviewed_candidate")

    def test_apriori_prunes_supersets_of_infrequent_features(self):
        a, b, c = (FeatureAtom("attribute", x) for x in ("a", "b", "c"))
        rows = (obj("1", (a, b)), obj("2", (a, b)),
                obj("3", (a,)), obj("4", (b, c)))
        result = discover_classes(rows, min_support=0.5, max_order=3)
        self.assertNotIn((b, c), [item.features for item in result.candidates])

    def test_budget_exhaustion_is_explicit(self):
        atoms = [FeatureAtom("attribute", str(i)) for i in range(6)]
        rows = tuple(obj(str(i), atoms) for i in range(4))
        result = discover_classes(rows, min_support=0.5, max_order=4,
                                  max_candidate_evaluations=2)
        self.assertTrue(result.search_truncated)
        self.assertEqual(result.candidate_evaluations, 2)

    def test_result_cap_is_distinct_from_search_truncation(self):
        atoms = [FeatureAtom("attribute", str(i)) for i in range(3)]
        rows = tuple(obj(str(i), atoms) for i in range(3))
        result = discover_classes(rows, min_support=0.5, max_order=1, max_results=1)
        self.assertFalse(result.search_truncated)
        self.assertTrue(result.results_truncated)
        self.assertEqual(len(result.candidates), 1)

    def test_deterministic_under_object_order(self):
        a, b = FeatureAtom("attribute", "a"), FeatureAtom("attribute", "b")
        rows = (obj("1", (a, b)), obj("2", (a,)), obj("3", (b,)))
        self.assertEqual(
            discover_classes(rows, min_support=1/3).candidates,
            discover_classes(tuple(reversed(rows)), min_support=1/3).candidates,
        )

    def test_rejects_duplicate_object_ids(self):
        row = obj("same", (FeatureAtom("attribute", "a"),))
        with self.assertRaisesRegex(ValueError, "unique"):
            discover_classes((row, row))

    def test_rejects_unprovenanced_or_unsorted_features(self):
        atom = FeatureAtom("attribute", "a")
        with self.assertRaises(ValueError):
            discover_classes((ObjectView("x", (atom,), ()),))
        with self.assertRaises(ValueError):
            discover_classes((ObjectView("y", (atom, atom), ("e",)),))

    def test_rejects_invalid_budgets_and_support(self):
        row = obj("x", (FeatureAtom("attribute", "a"),))
        for kwargs in (
            {"min_support": 0}, {"min_support": float("nan")},
            {"max_order": True}, {"max_order": 6},
            {"max_candidate_evaluations": 0}, {"max_results": False},
        ):
            with self.assertRaises(ValueError):
                discover_classes((row,), **kwargs)


if __name__ == "__main__":
    unittest.main()
