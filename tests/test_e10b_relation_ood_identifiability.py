import unittest

from prototype.e10b_relation_ood_identifiability import run


class E10BRelationOODIdentifiabilityTests(unittest.TestCase):
    def test_opaque_unseen_relation_is_unidentifiable_without_side_information(self):
        result = run(seed=2702, instances_per_template=3)
        self.assertTrue(result["checks"]["same_visible_input"])
        self.assertTrue(result["checks"]["opposite_hidden_labels"])
        self.assertTrue(result["checks"]["unseen_relation_rejected"])
        self.assertEqual(
            result["forced_binary_predictor_mean_accuracy_upper_bound"], 0.5
        )
        self.assertEqual(result["abstaining_predictor_coverage"], 0.0)


if __name__ == "__main__":
    unittest.main()
