import unittest

from prototype.e12m2_independent_stability_gate import validate_motif_candidates


class E12M2IndependentStabilityGateTests(unittest.TestCase):
    def test_repeated_motif_is_retained_on_independent_observations(self):
        proposal = [
            {"a", "c", "x"}, {"a", "c", "y"}, {"a", "c", "z"},
            {"a", "c", "w"}, {"b", "x"}, {"d", "y"},
        ]
        validation = [
            {"a", "c", "u"}, {"a", "c", "v"}, {"a", "c", "w"},
            {"b", "u"}, {"d", "v"},
        ]
        results = validate_motif_candidates(
            proposal, validation,
            proposal_min_support=0.5, proposal_min_lift=1.2,
            validation_min_support=0.5, validation_min_lift=1.2,
            validation_min_count=3, max_order=2,
        )
        pair = next(result for result in results if result.members == ("a", "c"))
        self.assertEqual(pair.status, "STABLE_MOTIF")
        self.assertEqual(pair.validation_count, 3)

    def test_proposal_that_does_not_recur_is_rejected(self):
        proposal = [
            {"a", "c", "x"}, {"a", "c", "y"}, {"a", "c", "z"},
            {"a", "c", "w"}, {"b", "x"}, {"d", "y"},
        ]
        validation = [{"a", "x"}, {"c", "y"}, {"b", "z"}, {"d", "w"}]
        results = validate_motif_candidates(
            proposal, validation,
            proposal_min_support=0.5, proposal_min_lift=1.2,
            validation_min_support=0.2, validation_min_lift=1.0,
            validation_min_count=2, max_order=2,
        )
        pair = next(result for result in results if result.members == ("a", "c"))
        self.assertEqual(pair.status, "REJECTED")
        self.assertIn("insufficient_validation_count", pair.reason)

    def test_validation_only_pattern_cannot_become_a_candidate(self):
        proposal = [{"a", "x"}, {"b", "y"}, {"c", "z"}, {"d", "w"}]
        validation = [{"q", "r"}] * 8
        results = validate_motif_candidates(
            proposal, validation,
            proposal_min_support=0.1, proposal_min_lift=1.0,
            validation_min_support=0.1, validation_min_lift=1.0,
            validation_min_count=1, max_order=2,
        )
        self.assertFalse(any(result.members == ("q", "r") for result in results))

    def test_empty_validation_partition_rejects_all_candidates(self):
        proposal = [{"a", "c"}, {"a", "c"}, {"a", "c"}, {"b"}, {"d"}]
        results = validate_motif_candidates(
            proposal, [],
            proposal_min_support=0.3, proposal_min_lift=1.0,
            max_order=2,
        )
        self.assertTrue(results)
        self.assertTrue(all(result.status == "REJECTED" for result in results))
        self.assertTrue(all("empty_validation_partition" in result.reason for result in results))

    def test_invalid_validation_parameters_are_rejected(self):
        for kwargs in (
            {"validation_min_support": 0},
            {"validation_min_support": 1.1},
            {"validation_min_lift": 0},
            {"validation_min_count": 0},
            {"validation_min_count": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    validate_motif_candidates([{"a", "b"}], [{"a", "b"}], **kwargs)

    def test_input_order_does_not_change_validation_results(self):
        proposal = [{"a", "c", "x"}, {"a", "c", "y"}, {"a", "c", "z"}, {"b", "x"}]
        validation = [{"a", "c"}, {"a", "c"}, {"b", "x"}]
        first = validate_motif_candidates(
            proposal, validation, proposal_min_support=0.5,
            proposal_min_lift=1.0, validation_min_support=0.5,
            validation_min_lift=1.0, validation_min_count=2, max_order=2,
        )
        second = validate_motif_candidates(
            reversed(proposal), reversed(validation), proposal_min_support=0.5,
            proposal_min_lift=1.0, validation_min_support=0.5,
            validation_min_lift=1.0, validation_min_count=2, max_order=2,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
