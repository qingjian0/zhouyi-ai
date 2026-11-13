import unittest

from prototype.yixiang_process import (
    Edge, Observation, classify_observation, derive_pattern, revise_pattern,
)


class YixiangProcessTests(unittest.TestCase):
    def setUp(self):
        self.a = Observation(
            "a", "river", {"flow": "directed", "boundary": "channel", "season": "wet"},
            (Edge("a", "b", "feeds"),), {"scale": "local"}, ("source:a",),
        )
        self.b = Observation(
            "b", "vascular", {"flow": "directed", "boundary": "vessel", "season": "all"},
            (Edge("b", "c", "feeds"),), {"scale": "micro"}, ("source:b",),
        )

    def test_derives_only_shared_invariants(self):
        p = derive_pattern((self.a, self.b), pattern_id="flow-pattern",
                           dimensions=("process", "relation"), scope="illustrative only")
        self.assertEqual(p.invariant_features, {"flow": "directed"})
        self.assertEqual(set(p.variable_features), {"boundary", "season"})
        self.assertEqual(set(p.evidence_refs), {"source:a", "source:b"})

    def test_classifies_with_evidence_and_explicit_threshold(self):
        p = derive_pattern((self.a, self.b), pattern_id="flow-pattern",
                           dimensions=("process",), scope="test scope")
        candidate = Observation("c", "software", {"flow": "directed"},
                                (), {}, ("source:c",))
        result = classify_observation(p, candidate)
        self.assertTrue(result.accepted)
        self.assertEqual(result.score, 1.0)

    def test_rejects_missing_evidence_and_mismatched_invariant(self):
        p = derive_pattern((self.a, self.b), pattern_id="flow-pattern",
                           dimensions=("process",), scope="test scope")
        candidate = Observation("c", "software", {"flow": "cyclic"}, (), {}, ())
        result = classify_observation(p, candidate)
        self.assertFalse(result.accepted)
        self.assertIn("INVARIANT_FEATURE_MISMATCH", result.reason_codes)
        self.assertIn("MISSING_OBSERVATION_EVIDENCE", result.reason_codes)

    def test_counterexample_removes_false_universal_and_records_exclusion(self):
        p = derive_pattern((self.a, self.b), pattern_id="flow-pattern",
                           dimensions=("process",), scope="test scope")
        counter = Observation("x", "blocked-river", {"flow": "directed", "boundary": "channel"},
                              (), {}, ("source:x",))
        revised = revise_pattern(p, positive_examples=(self.a, self.b),
                                 counterexamples=(counter,))
        self.assertEqual(revised.version, 2)
        self.assertEqual(revised.invariant_features, {"flow": "directed"})
        self.assertEqual(revised.excluded_patterns, ((("boundary", "channel"), ("flow", "directed")),))
        negative = Observation("x2", "blocked-river", {"flow": "directed", "boundary": "channel"}, (), {}, ("source:x2",))
        positive = Observation("y", "vascular", {"flow": "directed", "boundary": "vessel"}, (), {}, ("source:y",))
        self.assertFalse(classify_observation(revised, negative).accepted)
        self.assertTrue(classify_observation(revised, positive).accepted)
        self.assertEqual(revised.counterexample_ids, ("x",))

    def test_support_threshold_and_tied_values_are_not_overclaimed(self):
        c = Observation("c", "machine", {"flow": "directed"}, (), {}, ("source:c",))
        p = derive_pattern((self.a, self.b, c), pattern_id="majority",
                           dimensions=("process",), min_support_ratio=2/3, scope="sample scope")
        self.assertEqual(p.invariant_features, {"flow": "directed"})
        tie = Observation("d", "machine", {"flow": "cyclic"}, (), {}, ("source:d",))
        ambiguous = derive_pattern((self.a, tie), pattern_id="ambiguous",
                                    dimensions=("process",), min_support_ratio=0.5, scope="sample scope")
        self.assertNotIn("flow", ambiguous.invariant_features)
        self.assertIn("flow", ambiguous.variable_features)

    def test_rejects_duplicate_example_ids(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            revise_pattern(
                derive_pattern((self.a, self.b), pattern_id="p",
                               dimensions=("process",), scope="s"),
                positive_examples=(self.a,),
                counterexamples=(self.a,),
            )

    def test_requires_valid_dimensions_and_support_ratio(self):
        with self.assertRaises(ValueError):
            derive_pattern((self.a, self.b), pattern_id="p",
                           dimensions=("unknown",), scope="s")
        with self.assertRaises(ValueError):
            derive_pattern((self.a, self.b), pattern_id="p",
                           dimensions=("process",), scope="s", min_support_ratio=0)


if __name__ == "__main__":
    unittest.main()
