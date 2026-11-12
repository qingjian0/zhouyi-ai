import math
import unittest

from prototype.n11_cyclic_composition_ood import (
    make_dataset,
    run,
    run_seed,
)


def phase(row, role_index):
    node = row.assignment[role_index]
    sine_index = 2 if role_index == 0 else 1
    return math.atan2(node.features[sine_index], node.features[0]) % (2.0 * math.pi)


class N11CyclicCompositionOODTests(unittest.TestCase):
    def test_data_is_reproducible_and_regions_are_disjoint(self):
        train = make_dataset(80, 17, "train")
        test = make_dataset(80, 29, "test")
        self.assertEqual(train, make_dataset(80, 17, "train"))
        self.assertEqual(test, make_dataset(80, 29, "test"))
        self.assertTrue(all(phase(row, 0) >= math.pi / 2 for row in train))
        self.assertTrue(all(phase(row, 0) < math.pi / 2 for row in test))
        self.assertEqual({len(row.assignment) for row in train + test}, {3})
        self.assertEqual({len(node.features) for row in train + test
                          for node in row.assignment}, {5})

    def test_labels_match_the_composed_phase_rule(self):
        rows = make_dataset(100, 41, "test")
        for row in rows:
            angles = [phase(row, index) for index in range(3)]
            expected = int(math.cos(sum(angles)) > 0.0)
            self.assertEqual(row.label, expected)

    def test_invalid_dataset_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            make_dataset(0, 1, "train")
        with self.assertRaises(ValueError):
            make_dataset(5, 1, "validation")

    def test_third_order_model_transfers_to_held_out_phase_region(self):
        result = run_seed(7, train_count=1200, test_count=600, epochs=120)
        self.assertGreater(result["unary_pairwise_triple"]["accuracy"], 0.80)
        self.assertLess(result["unary_only"]["accuracy"], 0.70)
        self.assertLess(result["triple_model_after_triple_mask"]["accuracy"], 0.40)
        self.assertEqual(result["parameter_counts"]["full_model_total"], 35)

    def test_multiseed_summary_is_reproducible_in_shape(self):
        result = run(seed_count=2, start_seed=7,
                     train_count=120, test_count=60, epochs=5)
        self.assertEqual(result["seed_count"], 2)
        self.assertEqual(len(result["per_seed"]), 2)
        self.assertIn(
            "unary_pairwise_triple.accuracy",
            result["summary"],
        )
        self.assertIn(
            "sample_stddev",
            result["summary"]["unary_pairwise_triple.accuracy"],
        )


if __name__ == "__main__":
    unittest.main()
