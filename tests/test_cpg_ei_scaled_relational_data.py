import unittest
from collections import Counter

from prototype.cpg_ei_scaled_relational_data import (
    candidate_supports,
    generate_corpus,
    label_state,
    make_teacher,
)


class TestScaledRelationalData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = generate_corpus()

    def test_default_corpus_is_sixteen_times_reference_size(self):
        manifest = self.corpus["manifest"]
        self.assertEqual(manifest["input_dim"], 8)
        self.assertEqual(manifest["output_dim"], 8)
        self.assertEqual(manifest["family_count"], 40)
        self.assertEqual(manifest["states_per_family"], 256)
        self.assertEqual(manifest["row_count"], 10_240)
        self.assertEqual(manifest["candidate_support_count"], 238)
        self.assertEqual(len(set(manifest["teacher_digests"])), 40)

    def test_state_splits_are_disjoint_and_complete_for_every_teacher(self):
        rows_by_family = {}
        for row in self.corpus["rows"]:
            rows_by_family.setdefault(row["family_id"], []).append(row)
        for family_rows in rows_by_family.values():
            split_states = {
                split: {tuple(row["state"]) for row in family_rows
                        if row["state_split"] == split}
                for split in ("train", "development", "locked")
            }
            self.assertEqual(len(split_states["train"]), 128)
            self.assertEqual(len(split_states["development"]), 64)
            self.assertEqual(len(split_states["locked"]), 64)
            self.assertFalse(split_states["train"] & split_states["development"])
            self.assertFalse(split_states["train"] & split_states["locked"])
            self.assertFalse(split_states["development"] & split_states["locked"])
            self.assertEqual(
                set.union(*split_states.values()),
                {tuple(row["state"]) for row in family_rows},
            )

    def test_teacher_family_split_is_24_8_8_and_fewshot_queries_are_disjoint(self):
        manifest = self.corpus["manifest"]
        self.assertEqual(
            manifest["family_split_counts"],
            {"development": 8, "locked": 8, "train": 24},
        )
        rows_by_family = {}
        for row in self.corpus["rows"]:
            rows_by_family.setdefault(row["family_id"], []).append(row)
        for rows in rows_by_family.values():
            split = rows[0]["family_split"]
            self.assertTrue(all(row["family_split"] == split for row in rows))
            if split == "train":
                self.assertTrue(all(row["fewshot_role"] == "meta_train" for row in rows))
            else:
                support = {tuple(row["state"]) for row in rows
                           if row["fewshot_role"] == "support"}
                query_role = "query_development" if split == "development" else "query_locked"
                query = {tuple(row["state"]) for row in rows
                         if row["fewshot_role"] == query_role}
                self.assertEqual(len(support), 64)
                self.assertEqual(len(query), 192)
                self.assertFalse(support & query)
                self.assertEqual(len(support | query), 256)

    def test_teacher_labels_match_declared_supports(self):
        teacher_by_digest = {teacher.digest: teacher for teacher in self.corpus["teachers"]}
        for row in self.corpus["rows"][::97]:
            teacher = teacher_by_digest[row["teacher_digest"]]
            self.assertEqual(
                tuple(row["target"]),
                label_state(tuple(row["state"]), teacher.supports),
            )

    def test_generator_is_deterministic_and_dimension_generic(self):
        first = generate_corpus(
            family_count=5, input_dim=4, output_dim=3,
            min_arity=2, max_arity=3, seed=71,
        )
        second = generate_corpus(
            family_count=5, input_dim=4, output_dim=3,
            min_arity=2, max_arity=3, seed=71,
        )
        self.assertEqual(first["manifest"], second["manifest"])
        self.assertEqual(first["rows"], second["rows"])
        self.assertEqual(first["manifest"]["row_count"], 5 * 16)
        self.assertEqual(first["manifest"]["candidate_support_count"], 10)

    def test_candidate_support_count_and_arity_are_exact(self):
        supports = candidate_supports(8, 2, 6)
        self.assertEqual(len(supports), 238)
        self.assertEqual(len(supports), len(set(supports)))
        self.assertTrue(all(2 <= len(support) <= 6 for support in supports))

    def test_invalid_dimensions_and_arity_are_rejected(self):
        with self.assertRaises(ValueError):
            candidate_supports(1)
        with self.assertRaises(ValueError):
            candidate_supports(8, 1, 6)
        with self.assertRaises(ValueError):
            make_teacher(7, input_dim=8, output_dim=239)
        with self.assertRaises(ValueError):
            generate_corpus(family_count=4)


if __name__ == "__main__":
    unittest.main()
