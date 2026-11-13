import copy
import unittest

from prototype.cpg_ei_heldout_family_protocol import build_heldout_family_protocol
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class HeldoutFamilyProtocolTests(unittest.TestCase):
    def test_family_disjoint_fewshot_views(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=881)
        protocol = build_heldout_family_protocol(corpus, support_size=8, seed=882)
        learner = protocol["learner_view"]
        evaluator = protocol["evaluator_view"]
        self.assertEqual(learner["summary"]["training_families"], 12)
        self.assertEqual(learner["summary"]["validation_families"], 4)
        self.assertEqual(learner["summary"]["test_families"], 4)
        self.assertEqual(len(learner["meta_train_episodes"]), 12)
        self.assertEqual(len(learner["validation_episodes"]), 4)
        self.assertEqual(len(learner["test_episodes"]), 4)
        self.assertEqual(len(evaluator["test_query_targets"]), 4)
        for episode in learner["validation_episodes"] + learner["test_episodes"]:
            self.assertEqual(len(episode["support"]), 8)
            self.assertTrue(episode["query_states"])
            self.assertNotIn("query_targets", episode)
            self.assertNotIn("meta_train_query_targets", episode)

    def test_heldout_query_label_mutation_cannot_change_learner_view(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=883)
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["family_split"] == "locked" and row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        a = build_heldout_family_protocol(corpus, support_size=8, seed=884)
        b = build_heldout_family_protocol(changed, support_size=8, seed=884)
        self.assertEqual(a["learner_view"], b["learner_view"])
        self.assertNotEqual(a["evaluator_view"], b["evaluator_view"])

    def test_support_size_is_bounded_by_training_states(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=885)
        with self.assertRaises(ValueError):
            build_heldout_family_protocol(corpus, support_size=129)

    def test_query_targets_are_separate_for_heldout_families(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=886)
        protocol = build_heldout_family_protocol(corpus, support_size=16, seed=887)
        learner = protocol["learner_view"]
        self.assertTrue(all("query_targets" not in row for row in learner["validation_episodes"]))
        self.assertTrue(all("query_targets" not in row for row in learner["test_episodes"]))
        self.assertEqual(len(protocol["evaluator_view"]["test_query_targets"]), 4)

    def test_rejects_family_with_missing_state_partition(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=888)
        family_id = corpus["rows"][0]["family_id"]
        for row in corpus["rows"]:
            if row["family_id"] == family_id and row["state_split"] == "locked":
                row["state_split"] = "train"
        with self.assertRaises(ValueError):
            build_heldout_family_protocol(corpus, support_size=4, seed=889)

    def test_rejects_teacher_family_cross_split_contamination(self):
        corpus = generate_mixed_corpus(family_count=20, input_dim=4, output_dim=3, seed=890)
        family_id = corpus["rows"][0]["family_id"]
        for row in corpus["rows"]:
            if row["family_id"] == family_id:
                row["family_split"] = "locked"
                break
        with self.assertRaises(ValueError):
            build_heldout_family_protocol(corpus, support_size=4, seed=891)


if __name__ == "__main__":
    unittest.main()
