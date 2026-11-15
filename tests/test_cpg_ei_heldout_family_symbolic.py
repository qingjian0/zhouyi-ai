import copy
import unittest

from prototype.cpg_ei_heldout_family_symbolic import run_fewshot_benchmark
from prototype.cpg_ei_heldout_family_protocol import build_heldout_family_protocol
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import enumerate_rule_hypotheses, _truth_mask
from prototype.cpg_ei_heldout_family_symbolic import evaluate_protocol_views


class HeldoutFamilyFewshotSymbolicTests(unittest.TestCase):
    def test_small_benchmark_returns_metrics(self):
        report = run_fewshot_benchmark(
            family_count=20, input_dim=4, output_dim=3,
            seeds=(901,), support_sizes=(4, 8),
        )
        self.assertEqual(len(report["results"]), 2)
        for result in report["results"]:
            self.assertEqual(result["test"]["summary"]["families"], 4)
            self.assertEqual(len(result["corpus_sha256"]), 64)
            self.assertGreaterEqual(result["evaluation_wall_seconds"], 0.0)
            self.assertGreaterEqual(result["test"]["summary"]["symbolic_bit_accuracy_mean"], 0.0)
            self.assertGreaterEqual(result["test"]["summary"]["majority_bit_accuracy_mean"], 0.0)
        test_aggregate = next(
            row for row in report["aggregate_results"]
            if row["support_size"] == 4 and row["split"] == "test"
        )
        self.assertEqual(
            test_aggregate["methods"]["symbolic"]["bit_accuracy"]["families_across_seeds"],
            4,
        )

    def test_locked_query_labels_do_not_change_selected_rules(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=902)
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["family_split"] == "locked" and row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        candidates = enumerate_rule_hypotheses(4)
        masks = tuple(_truth_mask(rule, 4) for rule in candidates)
        a = evaluate_protocol_views(
            build_heldout_family_protocol(corpus, support_size=8, seed=903),
            candidates, masks, 4,
        )
        b = evaluate_protocol_views(
            build_heldout_family_protocol(changed, support_size=8, seed=903),
            candidates, masks, 4,
        )
        self.assertEqual(a["test"]["selection_digest"], b["test"]["selection_digest"])
        self.assertEqual(
            [row["selected_rule_digest"] for row in a["test"]["family_results"]],
            [row["selected_rule_digest"] for row in b["test"]["family_results"]],
        )

    def test_support_sizes_are_nested_for_fixed_seed(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=904)
        a = build_heldout_family_protocol(corpus, support_size=4, seed=905)
        b = build_heldout_family_protocol(corpus, support_size=8, seed=905)
        for left, right in zip(a["learner_view"]["test_episodes"],
                               b["learner_view"]["test_episodes"]):
            self.assertEqual(left["support"], right["support"][:4])


if __name__ == "__main__":
    unittest.main()
