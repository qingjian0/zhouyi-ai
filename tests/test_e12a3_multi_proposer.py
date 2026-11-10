import unittest

from prototype.e12a3_multi_proposer import (
    CandidateSignature, LifecycleState, Observation, PredicateExpr,
    allocate_equal_budget, allocate_round_robin, demo_rows, evaluate_gate,
    group_empirical_equivalence, lifecycle_transition, observed_signature,
    propose_exhaustive, propose_random, propose_relational, propose_statistical,
    run_demo, validate_observations,
)


class E12A3MultiProposerTests(unittest.TestCase):
    def test_statistical_proposals_are_deterministic_and_grounded(self):
        rows = demo_rows()
        a = propose_statistical(rows)
        b = propose_statistical(tuple(reversed(rows)))
        self.assertEqual(a, b)
        self.assertTrue(any(p.expression.feature == "temperature" for p in a))
        self.assertTrue(all(p.source_observation_ids == ("o1", "o2", "o3", "o4") for p in a))

    def test_relational_proposer_discovers_numeric_and_categorical_relations(self):
        proposals = propose_relational(demo_rows())
        operators = {p.expression.operator for p in proposals}
        self.assertIn("DIFF_GE", operators)
        self.assertIn("SAME", operators)

    def test_random_proposer_is_seed_reproducible(self):
        rows = demo_rows()
        self.assertEqual(propose_random(rows, 42, 20), propose_random(rows, 42, 20))
        self.assertNotEqual(propose_random(rows, 42, 20), propose_random(rows, 43, 20))

    def test_exhaustive_proposer_respects_limit(self):
        self.assertEqual(len(propose_exhaustive(demo_rows(), 3)), 3)
        self.assertEqual(propose_exhaustive(demo_rows(), 0), ())

    def test_equal_budget_conserves_budget_and_remainder(self):
        allocation = allocate_equal_budget(("C", "A", "B"), 11).as_dict()
        self.assertEqual(allocation, {"A": 4, "B": 4, "C": 3})
        self.assertEqual(sum(allocation.values()), 11)

    def test_round_robin_is_deterministic_and_budget_bounded(self):
        rows = demo_rows()
        families = {
            "STAT": propose_statistical(rows),
            "RELATIONAL": propose_relational(rows),
            "RANDOM": propose_random(rows, 7, 30),
        }
        selected = allocate_round_robin(families, 7)
        self.assertEqual(len(selected), 7)
        counts = {name: sum(p.family == name for p in selected) for name in families}
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_empirical_equivalence_is_dataset_scoped(self):
        rows = demo_rows()
        proposals = propose_statistical(rows)
        groups = group_empirical_equivalence(proposals, rows, "support-v1")
        self.assertTrue(groups)
        self.assertTrue(all(isinstance(sig, CandidateSignature) for sig in groups))
        self.assertEqual(
            observed_signature(proposals[0], rows, "support-v1").dataset_id,
            "support-v1",
        )

    def test_gate_evaluation_is_separate_from_proposal_generation(self):
        rows = demo_rows()
        proposals = propose_statistical(rows)
        gate = (Observation("g1", (("temperature", 30), ("speed", 5), ("weather", "wet")), 1),)
        result = evaluate_gate(proposals, gate)
        self.assertTrue(result)
        self.assertTrue(all(item["gate_observation_ids"] == ["g1"] for item in result.values()))

    def test_invalid_schema_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            validate_observations((Observation("x", (("a", 1),), 0),
                                   Observation("x", (("a", 2),), 1)))
        with self.assertRaises(ValueError):
            validate_observations((Observation("x", (("a", 1),), 0),
                                   Observation("y", (("b", 2),), 1)))

    def test_expression_type_errors_are_explicit(self):
        with self.assertRaises(TypeError):
            PredicateExpr("a", "PARITY", 0).evaluate({"a": "not-number"})
        with self.assertRaises(TypeError):
            PredicateExpr("a", "DIFF_GE", 0, "b").evaluate({"a": "x", "b": "y"})

    def test_lifecycle_is_append_only_and_rejects_invalid_transition(self):
        first = lifecycle_transition("c1", None, LifecycleState.PROPOSED, ("o1",), "generated")
        self.assertEqual(first.to_state, "PROPOSED")
        with self.assertRaises(ValueError):
            lifecycle_transition("c1", LifecycleState.PROPOSED,
                                 LifecycleState.ACCEPTED, ("g1",), "skip gates")
        accepted = lifecycle_transition("c1", LifecycleState.GATE_VALIDATED,
                                        LifecycleState.ACCEPTED, ("g1",), "passed gate")
        self.assertEqual(accepted.from_state, "GATE_VALIDATED")

    def test_demo_reports_smoke_test_not_benchmark(self):
        result = run_demo()
        self.assertEqual(result["selected_count"], result["budget"])
        self.assertIn("not a benchmark", result["note"])


if __name__ == "__main__":
    unittest.main()
