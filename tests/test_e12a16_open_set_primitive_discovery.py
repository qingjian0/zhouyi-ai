import unittest

from prototype.e12a16_open_set_primitive_discovery import (
    DiscoveryConfig, PrimitiveObservation, discover_primitives,
)


def make_rows():
    rows = []
    # Non-contiguous sparse dependency: a,c,e jointly predict "signal".
    for i in range(40):
        active = (i % 2 == 0)
        atoms = ["a", "b", "c", "d", "e"]
        outcome = "signal" if active else "background"
        if not active:
            atoms = ["b", "d"]
        rows.append(PrimitiveObservation(f"obs-{i:03}", tuple(sorted(atoms)), outcome,
                                         0.01 if active else 0.8))
    return rows


class OpenSetPrimitiveDiscoveryTests(unittest.TestCase):
    def test_discovers_sparse_noncontiguous_primitive(self):
        result = discover_primitives(make_rows(), parent_refs=("root@1",),
            config=DiscoveryConfig(max_arity=3, min_train_support=3,
                min_validation_support=2, max_candidates=1000,
                max_complexity_bits=30, validation_fraction=0.25))
        self.assertTrue(result.candidates)
        self.assertIn(("a", "c", "e"), [candidate.atoms for candidate in result.candidates])
        candidate = next(c for c in result.candidates if c.atoms == ("a", "c", "e"))
        self.assertGreater(candidate.description_length_gain_bits, 0)
        self.assertEqual(candidate.parent_refs, ("root@1",))

    def test_random_or_uninformative_pattern_is_not_admitted(self):
        rows = [PrimitiveObservation(f"u-{i:03}", ("a", "b"), "yes" if i % 2 else "no")
                for i in range(30)]
        result = discover_primitives(rows, config=DiscoveryConfig(
            max_arity=2, min_train_support=3, min_validation_support=2,
            max_candidates=100, max_complexity_bits=20, validation_fraction=0.3))
        self.assertEqual(result.candidates, ())

    def test_complexity_budget_blocks_overfit_rules(self):
        result = discover_primitives(make_rows(), config=DiscoveryConfig(
            max_arity=3, min_train_support=3, min_validation_support=2,
            max_candidates=1000, max_complexity_bits=1, validation_fraction=0.25))
        self.assertEqual(result.candidates, ())

    def test_candidate_budget_is_deterministic_and_bounded(self):
        result = discover_primitives(make_rows(), config=DiscoveryConfig(
            max_arity=4, max_candidates=3, validation_fraction=0.25))
        self.assertEqual(result.generated_candidate_count, 3)
        self.assertTrue(result.truncated)

    def test_novelty_signal_uses_incumbent_likelihood_not_pattern_guess(self):
        result = discover_primitives(make_rows(), config=DiscoveryConfig(
            max_arity=3, min_train_support=3, min_validation_support=2,
            max_candidates=1000, max_complexity_bits=30, validation_fraction=0.25))
        self.assertTrue(result.novelty.novelty_detected)
        self.assertEqual(result.novelty.low_likelihood_count, 20)

    def test_duplicate_ids_and_invalid_probability_are_rejected(self):
        with self.assertRaises(ValueError):
            discover_primitives([PrimitiveObservation("same", ("a",), "x")] * 4)
        with self.assertRaises(ValueError):
            PrimitiveObservation("bad", ("a",), "x", 0.0)

    def test_empty_validation_mode_uses_training_gain(self):
        rows = make_rows()
        result = discover_primitives(rows, config=DiscoveryConfig(
            max_arity=3, min_train_support=3, min_validation_support=2,
            max_candidates=1000, max_complexity_bits=30, validation_fraction=0))
        self.assertTrue(result.candidates)


if __name__ == "__main__":
    unittest.main()
