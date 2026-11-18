import copy
import unittest

from prototype.cpg_ei_empirical_bayes_meta_learner import (
    learn_candidate_prior,
    run_meta_benchmark,
)
from prototype.cpg_ei_heldout_family_protocol import build_heldout_family_protocol
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import (
    _truth_mask,
    enumerate_rule_hypotheses,
)


class EmpiricalBayesMetaLearnerTests(unittest.TestCase):
    def _small_protocol(self):
        corpus = generate_mixed_corpus(
            family_count=20, input_dim=4, output_dim=3, seed=1901,
        )
        return build_heldout_family_protocol(
            corpus, support_size=4, seed=1902,
        )

    def test_candidate_prior_is_normalized_and_deterministic(self):
        protocol = self._small_protocol()
        candidates = enumerate_rule_hypotheses(4)
        masks = tuple(_truth_mask(rule, 4) for rule in candidates)
        first = learn_candidate_prior(
            protocol["learner_view"]["meta_train_episodes"], masks, 4,
        )
        second = learn_candidate_prior(
            protocol["learner_view"]["meta_train_episodes"], masks, 4,
        )
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(first), 1.0)
        self.assertTrue(all(value > 0.0 for value in first))

    def test_locked_query_labels_cannot_change_meta_train_prior(self):
        protocol = self._small_protocol()
        changed = copy.deepcopy(protocol)
        for row in changed["evaluator_view"]["test_query_targets"]:
            row["query_targets"] = [
                [1 - bit for bit in target] for target in row["query_targets"]
            ]
        candidates = enumerate_rule_hypotheses(4)
        masks = tuple(_truth_mask(rule, 4) for rule in candidates)
        prior_a = learn_candidate_prior(
            protocol["learner_view"]["meta_train_episodes"], masks, 4,
        )
        prior_b = learn_candidate_prior(
            changed["learner_view"]["meta_train_episodes"], masks, 4,
        )
        self.assertEqual(prior_a, prior_b)

    def test_benchmark_runs_and_selects_alpha_on_validation_only(self):
        report = run_meta_benchmark(
            family_count=20,
            input_dim=4,
            output_dim=3,
            seeds=(1903,),
            support_sizes=(4, 8),
            alpha_grid=(0.0, 0.1),
        )
        self.assertEqual(report["benchmark_id"],
                         "zhouyi-cpg-ei-heldout-family-empirical-bayes-v1")
        self.assertEqual(len(report["results"]), 2)
        for result in report["results"]:
            self.assertIn(result["selected_alpha"], (0.0, 0.1))
            self.assertEqual(result["meta_train_families"], 12)
            self.assertEqual(result["validation_families"], 4)
            self.assertEqual(result["test_families"], 4)
            self.assertEqual(len(result["prior_sha256"]), 64)
            self.assertGreaterEqual(
                result["test"]["summary"]["empirical_bayes_bit_accuracy_mean"], 0.0,
            )
            self.assertEqual(
                result["deterministic_symbolic_baseline"]["families"], 4.0,
            )
        self.assertEqual(len(report["aggregate_test_results"]), 8)

    def test_rejects_invalid_prior_smoothing(self):
        protocol = self._small_protocol()
        candidates = enumerate_rule_hypotheses(4)
        masks = tuple(_truth_mask(rule, 4) for rule in candidates)
        with self.assertRaises(ValueError):
            learn_candidate_prior(
                protocol["learner_view"]["meta_train_episodes"],
                masks, 4, smoothing=0.0,
            )


if __name__ == "__main__":
    unittest.main()
