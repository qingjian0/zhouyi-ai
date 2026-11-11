import unittest

from prototype.tx02_splits import make_rule_disjoint_splits


class TX02RuleDisjointSplitTests(unittest.TestCase):
    def test_rule_coefficients_are_disjoint_across_splits(self):
        bundle = make_rule_disjoint_splits(
            3, episodes_per_rule=1, support_size=3, query_count=2,
            seed=91, symbol_mappings=("canonical", "permuted"),
        )
        train = set(bundle.rule_families["train"])
        validation = set(bundle.rule_families["validation"])
        test = set(bundle.rule_families["locked_test"])
        self.assertTrue(train.isdisjoint(validation))
        self.assertTrue(train.isdisjoint(test))
        self.assertTrue(validation.isdisjoint(test))
        self.assertEqual(len(train | validation | test), 27)

    def test_locked_test_inputs_do_not_contain_targets_or_hidden_metadata(self):
        bundle = make_rule_disjoint_splits(
            2, episodes_per_rule=1, support_size=2, query_count=1,
            seed=17, symbol_mappings=("permuted",),
        )
        row = bundle.locked_test[0]
        self.assertFalse(hasattr(row.inputs, "targets"))
        self.assertFalse(hasattr(row.inputs, "hidden_rule"))
        self.assertFalse(hasattr(row.inputs, "visible_symbols"))
        self.assertEqual(len(row.targets), 1)

    def test_train_targets_are_separate_from_model_inputs(self):
        bundle = make_rule_disjoint_splits(
            3, episodes_per_rule=1, support_size=3, query_count=2,
            seed=29, symbol_mappings=("canonical",),
        )
        row = bundle.train[0]
        self.assertFalse(hasattr(row.inputs, "targets"))
        self.assertEqual(len(row.targets), 2)

    def test_seed_reproducibility(self):
        args = dict(cardinality=3, episodes_per_rule=1, support_size=3,
                    query_count=2, seed=101, symbol_mappings=("permuted",))
        first = make_rule_disjoint_splits(**args)
        second = make_rule_disjoint_splits(**args)
        self.assertEqual(first, second)

    def test_all_splits_nonempty_for_small_and_larger_cardinalities(self):
        for k, support in ((2, 2), (3, 3), (4, 4), (5, 4)):
            bundle = make_rule_disjoint_splits(
                k, episodes_per_rule=1, support_size=support,
                query_count=1, seed=2026,
                symbol_mappings=("canonical",),
            )
            self.assertTrue(bundle.train)
            self.assertTrue(bundle.validation)
            self.assertTrue(bundle.locked_test)

    def test_rejects_invalid_split_and_episode_settings(self):
        with self.assertRaises(ValueError):
            make_rule_disjoint_splits(3, train_fraction=0.8,
                                      validation_fraction=0.2)
        with self.assertRaises(ValueError):
            make_rule_disjoint_splits(2, support_size=4, query_count=1)


if __name__ == "__main__":
    unittest.main()
