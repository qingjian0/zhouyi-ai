import copy
import random
import unittest

from prototype.cpg_ei_active_query_discovery import (
    _max_disagreement_position, run_active_query_benchmark,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class TestActiveQueryDiscovery(unittest.TestCase):
    def setUp(self):
        self.corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=711
        )
        self.budgets = (2, 4, 8)

    def test_bit_sliced_disagreement_matches_naive_reference(self):
        for seed in range(30):
            rng = random.Random(seed)
            patterns = [rng.getrandbits(16) for _ in range(25)]
            unique = set(patterns)
            positions = list(range(16))
            counts = [
                sum((pattern >> position) & 1 for pattern in unique)
                for position in positions
            ]
            scores = [min(count, len(unique) - count) for count in counts]
            expected_score = max(scores)
            expected = (
                next(position for position, score in enumerate(scores)
                     if score == expected_score)
                if expected_score else None
            )
            self.assertEqual(
                _max_disagreement_position(patterns, positions), expected
            )

    def test_active_query_trace_is_deterministic_and_train_only(self):
        first = run_active_query_benchmark(
            self.corpus, query_budgets=self.budgets, seed=17
        )
        second = run_active_query_benchmark(
            self.corpus, query_budgets=self.budgets, seed=17
        )
        train_indices = {
            int("".join(str(bit) for bit in row["state"]), 2)
            for row in self.corpus["rows"] if row["state_split"] == "train"
        }
        for first_family, second_family in zip(
            first["family_results"], second["family_results"]
        ):
            for first_output, second_output in zip(
                first_family["output_results"], second_family["output_results"]
            ):
                self.assertEqual(
                    first_output["active_query_order"],
                    second_output["active_query_order"],
                )
                self.assertEqual(
                    first_output["random_query_order"],
                    second_output["random_query_order"],
                )
                for budget_result in first_output["budget_results"]:
                    for method in ("active", "random"):
                        record = budget_result[method]
                        self.assertEqual(len(record["query_state_indices"]),
                                         len(set(record["query_state_indices"])))
                        self.assertLessEqual(record["query_count"], record["budget"])
                        self.assertTrue(
                            set(record["query_state_indices"]).issubset(train_indices)
                        )

    def test_development_and_locked_labels_do_not_change_query_acquisition(self):
        original = run_active_query_benchmark(
            self.corpus, query_budgets=self.budgets, seed=29
        )
        changed = copy.deepcopy(self.corpus)
        for row in changed["rows"]:
            if row["state_split"] in ("development", "locked"):
                row["target"] = [1 - bit for bit in row["target"]]
        mutated = run_active_query_benchmark(
            changed, query_budgets=self.budgets, seed=29
        )
        for left_family, right_family in zip(
            original["family_results"], mutated["family_results"]
        ):
            for left_output, right_output in zip(
                left_family["output_results"], right_family["output_results"]
            ):
                self.assertEqual(
                    left_output["active_query_order"],
                    right_output["active_query_order"],
                )
                self.assertEqual(
                    left_output["random_query_order"],
                    right_output["random_query_order"],
                )
                for left_budget, right_budget in zip(
                    left_output["budget_results"], right_output["budget_results"]
                ):
                    for method in ("active", "random"):
                        self.assertEqual(
                            left_budget[method]["train_pattern_version_space_size"],
                            right_budget[method]["train_pattern_version_space_size"],
                        )
                        self.assertEqual(
                            left_budget[method]["full_function_version_space_size"],
                            right_budget[method]["full_function_version_space_size"],
                        )

    def test_locked_labels_do_not_change_selected_candidates(self):
        original = run_active_query_benchmark(
            self.corpus, query_budgets=self.budgets, seed=31
        )
        changed = copy.deepcopy(self.corpus)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        mutated = run_active_query_benchmark(
            changed, query_budgets=self.budgets, seed=31
        )
        for left_family, right_family in zip(
            original["family_results"], mutated["family_results"]
        ):
            for left_output, right_output in zip(
                left_family["output_results"], right_family["output_results"]
            ):
                for left_budget, right_budget in zip(
                    left_output["budget_results"], right_output["budget_results"]
                ):
                    for method in ("active", "random"):
                        self.assertEqual(
                            left_budget[method]["selected_rule"],
                            right_budget[method]["selected_rule"],
                        )

    def test_budget_validation(self):
        with self.assertRaises(ValueError):
            run_active_query_benchmark(
                self.corpus, query_budgets=(4, 2), seed=1
            )
        with self.assertRaises(ValueError):
            run_active_query_benchmark(
                self.corpus, query_budgets=(9,), seed=1
            )


if __name__ == "__main__":
    unittest.main()
