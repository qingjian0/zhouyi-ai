import unittest
from dataclasses import replace

from prototype.e12a_identifiability import (
    EvaluatorTruth,
    LearnerView,
    Observation,
    apply_probe,
    infer,
    make_episode,
    run_suite,
)


class E12AIdentifiabilityTests(unittest.TestCase):
    def test_identifiable_support_selects_unique_candidate(self):
        for seed in range(10):
            view, truth = make_episode("identifiable", seed)
            result = infer(view)
            self.assertEqual(result["status"], "IDENTIFIABLE")
            self.assertEqual(result["selected"], truth.primitive_id)

    def test_observationally_equivalent_worlds_remain_ambiguous(self):
        for seed in range(10):
            view, _ = make_episode("ambiguous", seed)
            self.assertEqual(infer(view)["status"], "AMBIGUOUS")

    def test_pending_intervention_is_ambiguous_before_probe(self):
        view, _ = make_episode("intervention_pending", 11)
        self.assertEqual(infer(view)["status"], "AMBIGUOUS")

    def test_permitted_probe_resolves_ambiguity(self):
        for seed in range(10):
            view, truth = make_episode("intervention_pending", seed)
            updated = apply_probe(view, truth, 3)
            result = infer(updated)
            self.assertEqual(result["status"], "IDENTIFIABLE")
            self.assertEqual(result["selected"], truth.primitive_id)

    def test_unobservable_alternatives_remain_ambiguous(self):
        view, _ = make_episode("unobservable", 5)
        self.assertEqual(infer(view)["status"], "AMBIGUOUS")
        self.assertEqual(view.allowed_probe_values, ())

    def test_contradictory_evidence_is_inconsistent(self):
        view, _ = make_episode("inconsistent", 5)
        self.assertEqual(infer(view)["status"], "INCONSISTENT")

    def test_truth_mutation_cannot_change_learner_result(self):
        view, truth = make_episode("ambiguous", 13)
        mutated_truth = replace(truth, primitive_id=(
            "eq2" if truth.primitive_id == "ge2" else "ge2"
        ))
        self.assertEqual(infer(view), infer(view))
        self.assertEqual(infer(view), infer(view))
        self.assertNotEqual(truth.primitive_id, mutated_truth.primitive_id)

    def test_budget_exhaustion_is_explicit(self):
        view, _ = make_episode("identifiable", 3)
        self.assertEqual(infer(view, candidate_budget=1)["status"],
                         "BUDGET_EXHAUSTED")

    def test_probe_must_be_authorized(self):
        view, truth = make_episode("ambiguous", 3)
        with self.assertRaises(ValueError):
            apply_probe(view, truth, 3)

    def test_suite_reports_all_families(self):
        result = run_suite(seeds=2, start_seed=7)
        self.assertEqual(set(result["status_counts"]), {
            "identifiable", "ambiguous", "intervention_pending",
            "unobservable", "inconsistent"
        })
        self.assertEqual(result["intervention_probe_recovery"], 1.0)


if __name__ == "__main__":
    unittest.main()
