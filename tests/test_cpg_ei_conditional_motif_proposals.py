import itertools
import random
import unittest

from prototype.cpg_ei_mvp import Example
from prototype.cpg_ei_conditional_motif_proposals import rank_conditional_motifs


def make_parity_rows(count, seed):
    rng = random.Random(seed)
    triples = ((0, 1, 2), (1, 3, 4), (2, 4, 5))
    rows = []
    for _ in range(count):
        state = tuple(rng.randrange(2) for _ in range(6))
        target = tuple(
            sum(state[index] for index in triples[head // 2]) % 2
            for head in range(6)
        )
        rows.append(Example(state, target))
    return rows


class TestConditionalMotifProposals(unittest.TestCase):
    def test_joint_conditional_motifs_recover_three_parity_groups(self):
        train = make_parity_rows(512, 11)
        result = rank_conditional_motifs(train, max_motifs=3)
        selected = {tuple(item["lines"]) for item in result["selected"]}
        expected = {(0, 1, 2), (1, 3, 4), (2, 4, 5)}
        self.assertEqual(result["candidate_count"], 20)
        self.assertEqual(selected, expected)
        self.assertTrue(all(item["score"] > 0.0 for item in result["selected"]))
        self.assertEqual(result["method"], "conditional_four_term_motif")

    def test_proposals_are_deterministic_and_train_only(self):
        train = make_parity_rows(256, 23)
        first = rank_conditional_motifs(train, max_motifs=5)
        second = rank_conditional_motifs(train, max_motifs=5)
        self.assertEqual(first, second)
        self.assertEqual(len(first["selected"]), 5)

    def test_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            rank_conditional_motifs([])
        with self.assertRaisesRegex(ValueError, "max_motifs"):
            rank_conditional_motifs(make_parity_rows(8, 1), max_motifs=0)
        with self.assertRaisesRegex(ValueError, "ridge"):
            rank_conditional_motifs(make_parity_rows(8, 1), ridge=0.0)


if __name__ == "__main__":
    unittest.main()
