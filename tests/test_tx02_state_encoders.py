import unittest

from prototype.tx02_state_encoders import (
    FAMILIES,
    build_codebook,
)


class TX02StateEncoderTests(unittest.TestCase):
    def test_all_families_are_injective_and_reversible(self):
        for k in (2, 3, 4, 5, 7, 9):
            for family in FAMILIES:
                with self.subTest(k=k, family=family):
                    codebook = build_codebook(k, family, seed=13)
                    self.assertEqual(len(codebook.codewords), k)
                    self.assertEqual(len(set(codebook.codewords)), k)
                    for symbol in range(k):
                        self.assertEqual(codebook.decode(codebook.encode(symbol)), symbol)

    def test_expected_dimensions(self):
        self.assertEqual(build_codebook(5, "BINARY").dimension, 3)
        self.assertEqual(build_codebook(5, "TERNARY").dimension, 2)
        self.assertEqual(build_codebook(5, "HYBRID").dimension, 5)
        self.assertEqual(build_codebook(5, "ONE_HOT").dimension, 5)

    def test_learned_initialization_is_seeded(self):
        first = build_codebook(5, "LEARNED_INIT", seed=22)
        second = build_codebook(5, "LEARNED_INIT", seed=22)
        other = build_codebook(5, "LEARNED_INIT", seed=23)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_permuted_control_preserves_codeword_set(self):
        base = build_codebook(5, "TERNARY", seed=1)
        permuted = build_codebook(5, "PERMUTED", seed=5)
        self.assertEqual(set(base.codewords), set(permuted.codewords))
        self.assertNotEqual(base.codewords, permuted.codewords)

    def test_rejects_invalid_symbols_and_codewords(self):
        codebook = build_codebook(3, "TERNARY")
        with self.assertRaises(ValueError):
            codebook.encode(3)
        with self.assertRaises(ValueError):
            codebook.encode(-1)
        with self.assertRaises(ValueError):
            codebook.decode((9.0, 9.0))
        with self.assertRaises(ValueError):
            build_codebook(1, "BINARY")
        with self.assertRaises(ValueError):
            build_codebook(3, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
