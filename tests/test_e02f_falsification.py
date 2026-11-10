import unittest

from prototype.e02f_falsification import (
    candidates, make_split, run_episode,
)


class E02FFalsificationTests(unittest.TestCase):
    def test_train_only_nuisance_is_selected_but_rejected_by_gate(self):
        result = run_episode(seed=111, nuisance="train_only")
        self.assertEqual(result["winner"], [8])
        self.assertFalse(result["created"])
        self.assertLess(result["gate_accuracy"], 0.65)

    def test_clean_condition_can_still_discover_target_relation(self):
        result = run_episode(seed=112, nuisance="none")
        self.assertTrue(result["target_recovered"])
        self.assertTrue(result["created"])
        self.assertGreater(result["test_accuracy"], 0.9)

    def test_gate_and_test_do_not_contain_train_only_nuisance(self):
        target = (0, 2, 5)
        train = make_split(seed=1, count=32, target=target,
                           nuisance="train_only")
        gate = make_split(seed=2, count=32, target=target, nuisance="none")
        self.assertTrue(all(r.values[-1] == r.label for r in train))
        self.assertEqual({r.values[-1] for r in gate}, {-1, 1})

    def test_candidate_search_includes_singleton_competing_explanations(self):
        rows = make_split(seed=3, count=128, target=(0, 2, 5),
                          nuisance="train_only")
        self.assertEqual(candidates(rows)[0].members, (8,))


if __name__ == "__main__":
    unittest.main()
