import unittest

from prototype.cpg_ei_expanded_mixed_corpus import (
    DATASET_ID, generate_expanded_corpus,
)


class ExpandedMixedCorpusTests(unittest.TestCase):
    def test_generator_rejects_too_few_families(self):
        with self.assertRaises(ValueError):
            generate_expanded_corpus(family_count=4)

    def test_small_expanded_fixture_is_deterministic_and_balanced(self):
        a = generate_expanded_corpus(family_count=8, seed=991)
        b = generate_expanded_corpus(family_count=8, seed=991)
        manifest = a["manifest"]
        self.assertEqual(manifest["dataset_id"], DATASET_ID)
        self.assertEqual(manifest["row_count"], 8 * 256)
        self.assertEqual(manifest["teacher_rule_count"], 8 * 8)
        self.assertEqual(manifest["corpus_sha256"], b["manifest"]["corpus_sha256"])
        self.assertEqual(manifest["expansion_factor_vs_reference"], 0.02)
        self.assertEqual(manifest["family_split_counts"],
                         {"development": 1, "locked": 2, "train": 5})
        self.assertEqual(len({t["teacher_digest"] for t in a["teachers"]}), 8)

    def test_operator_coverage_is_round_robin_balanced(self):
        corpus = generate_expanded_corpus(family_count=10, seed=992)
        counts = list(corpus["manifest"]["operator_rule_counts"].values())
        self.assertEqual(len(counts), 7)
        self.assertLessEqual(max(counts) - min(counts), 1)

    def test_expanded_manifest_records_fourfold_target(self):
        corpus = generate_expanded_corpus(family_count=400, seed=993)
        manifest = corpus["manifest"]
        self.assertEqual(manifest["expansion_factor_vs_reference"], 1.0)
        self.assertEqual(manifest["row_count"], 400 * 256)
        self.assertEqual(manifest["expansion_axis"], "independent_teacher_families")


if __name__ == "__main__":
    unittest.main()
