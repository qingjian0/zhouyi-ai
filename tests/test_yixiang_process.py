import unittest

from prototype.yixiang_process import (
    Edge, Observation, classify_observation, derive_pattern, revise_pattern,
)


def dimensions(**overrides):
    result = {
        "flow": "process",
        "boundary": "morphology",
        "season": "spatiotemporal",
    }
    result.update(overrides)
    return result


class YixiangProcessTests(unittest.TestCase):
    def setUp(self):
        self.a = Observation(
            "a", "river",
            {"flow": "directed", "boundary": "channel", "season": "wet"},
            (Edge("a", "b", "feeds"),), {"scale": "local"}, ("source:a",),
            dimensions(),
        )
        self.b = Observation(
            "b", "vascular",
            {"flow": "directed", "boundary": "vessel", "season": "all"},
            (Edge("b", "c", "feeds"),), {"scale": "micro"}, ("source:b",),
            dimensions(),
        )

    def test_derives_only_shared_invariants_in_selected_dimensions(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="flow-pattern",
            dimensions=("process", "morphology", "spatiotemporal"),
            scope="illustrative only",
        )
        self.assertEqual(pattern.invariant_features, {"flow": "directed"})
        self.assertEqual(set(pattern.variable_features), {"boundary", "season"})
        self.assertEqual(pattern.feature_dimensions["flow"], "process")
        self.assertEqual(set(pattern.evidence_refs), {"source:a", "source:b"})

    def test_ignores_features_outside_selected_dimensions(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="process-only",
            dimensions=("process",), scope="process dimension only",
        )
        self.assertEqual(pattern.invariant_features, {"flow": "directed"})
        self.assertEqual(pattern.variable_features, ())

    def test_rejects_unmapped_feature_dimensions(self):
        invalid = Observation(
            "bad", "domain", {"flow": "directed"}, (), {}, ("source:bad",), {},
        )
        with self.assertRaisesRegex(ValueError, "exactly one declared dimension"):
            derive_pattern(
                (invalid,), pattern_id="bad", dimensions=("process",), scope="test",
            )

    def test_classifies_with_evidence_and_explicit_threshold(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="flow-pattern",
            dimensions=("process",), scope="test scope",
        )
        candidate = Observation(
            "c", "software", {"flow": "directed"}, (), {}, ("source:c",),
            {"flow": "process"},
        )
        result = classify_observation(pattern, candidate)
        self.assertTrue(result.accepted)
        self.assertEqual(result.score, 1.0)

    def test_rejects_dimension_mismatch_even_when_feature_value_matches(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="flow-pattern",
            dimensions=("process",), scope="test scope",
        )
        candidate = Observation(
            "c", "software", {"flow": "directed"}, (), {}, ("source:c",),
            {"flow": "attribute"},
        )
        result = classify_observation(pattern, candidate)
        self.assertFalse(result.accepted)
        self.assertIn("INVARIANT_FEATURE_MISMATCH", result.reason_codes)

    def test_rejects_missing_evidence_and_mismatched_invariant(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="flow-pattern",
            dimensions=("process",), scope="test scope",
        )
        candidate = Observation(
            "c", "software", {"flow": "cyclic"}, (), {}, (),
            {"flow": "process"},
        )
        result = classify_observation(pattern, candidate)
        self.assertFalse(result.accepted)
        self.assertIn("INVARIANT_FEATURE_MISMATCH", result.reason_codes)
        self.assertIn("MISSING_OBSERVATION_EVIDENCE", result.reason_codes)

    def test_counterexample_records_exclusion_without_overwriting_old_version(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="flow-pattern",
            dimensions=("process", "morphology"), scope="test scope",
        )
        counter = Observation(
            "x", "blocked-river",
            {"flow": "directed", "boundary": "channel"}, (), {}, ("source:x",),
            {"flow": "process", "boundary": "morphology"},
        )
        revised = revise_pattern(
            pattern, positive_examples=(self.a, self.b), counterexamples=(counter,),
        )
        self.assertEqual(pattern.version, 1)
        self.assertEqual(revised.version, 2)
        self.assertEqual(revised.invariant_features, {"flow": "directed"})
        self.assertEqual(
            revised.excluded_patterns,
            ((("boundary", "channel"), ("flow", "directed")),),
        )
        negative = Observation(
            "x2", "blocked-river",
            {"flow": "directed", "boundary": "channel"}, (), {}, ("source:x2",),
            {"flow": "process", "boundary": "morphology"},
        )
        positive = Observation(
            "y", "vascular",
            {"flow": "directed", "boundary": "vessel"}, (), {}, ("source:y",),
            {"flow": "process", "boundary": "morphology"},
        )
        self.assertFalse(classify_observation(revised, negative).accepted)
        self.assertTrue(classify_observation(revised, positive).accepted)
        self.assertEqual(revised.counterexample_ids, ("x",))

    def test_support_threshold_and_tied_values_are_not_overclaimed(self):
        c = Observation(
            "c", "machine", {"flow": "directed"}, (), {}, ("source:c",),
            {"flow": "process"},
        )
        pattern = derive_pattern(
            (self.a, self.b, c), pattern_id="majority",
            dimensions=("process",), min_support_ratio=2/3, scope="sample scope",
        )
        self.assertEqual(pattern.invariant_features, {"flow": "directed"})
        tie = Observation(
            "d", "machine", {"flow": "cyclic"}, (), {}, ("source:d",),
            {"flow": "process"},
        )
        ambiguous = derive_pattern(
            (self.a, tie), pattern_id="ambiguous",
            dimensions=("process",), min_support_ratio=0.5, scope="sample scope",
        )
        self.assertNotIn("flow", ambiguous.invariant_features)
        self.assertIn("flow", ambiguous.variable_features)

    def test_rejects_duplicate_example_ids(self):
        pattern = derive_pattern(
            (self.a, self.b), pattern_id="p", dimensions=("process",), scope="s",
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            revise_pattern(
                pattern, positive_examples=(self.a,), counterexamples=(self.a,),
            )

    def test_requires_valid_dimensions_and_support_ratio(self):
        with self.assertRaises(ValueError):
            derive_pattern(
                (self.a, self.b), pattern_id="p",
                dimensions=("unknown",), scope="s",
            )
        with self.assertRaises(ValueError):
            derive_pattern(
                (self.a, self.b), pattern_id="p",
                dimensions=("process",), scope="s", min_support_ratio=0,
            )


if __name__ == "__main__":
    unittest.main()
