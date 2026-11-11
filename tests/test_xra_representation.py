import unittest

from prototype.xra_representation import (
    RadixCodebook,
    canonical_codebook,
    minimum_digits,
    permuted_codebook,
)


class XRARepresentationTests(unittest.TestCase):
    def test_three_semantic_states_fit_binary_and_ternary(self):
        binary = canonical_codebook(3, 2)
        ternary = canonical_codebook(3, 3)
        self.assertEqual(binary.semantic_cardinality, 3)
        self.assertEqual(ternary.semantic_cardinality, 3)
        self.assertEqual(binary.digits, 2)
        self.assertEqual(ternary.digits, 1)
        self.assertEqual(binary.capacity, 4)
        self.assertEqual(ternary.capacity, 3)

    def test_round_trip_all_states_for_multiple_radices(self):
        for cardinality in range(1, 20):
            for radix in range(2, 7):
                codebook = canonical_codebook(cardinality, radix)
                for symbol_id in range(cardinality):
                    self.assertEqual(
                        codebook.decode(codebook.encode(symbol_id)), symbol_id
                    )

    def test_permuted_codebook_preserves_semantic_round_trip(self):
        codebook = permuted_codebook(3, 2, (3, 1, 0))
        self.assertEqual(codebook.encode(0), (1, 1))
        self.assertEqual(codebook.encode(1), (0, 1))
        self.assertEqual(codebook.encode(2), (0, 0))
        for symbol_id in range(3):
            self.assertEqual(codebook.decode(codebook.encode(symbol_id)), symbol_id)

    def test_unused_codeword_decodes_to_none(self):
        codebook = canonical_codebook(3, 2)
        self.assertEqual(codebook.unused_codes, 1)
        self.assertIsNone(codebook.decode((1, 1)))

    def test_minimum_digits(self):
        self.assertEqual(minimum_digits(1, 2), 1)
        self.assertEqual(minimum_digits(3, 2), 2)
        self.assertEqual(minimum_digits(3, 3), 1)
        self.assertEqual(minimum_digits(64, 2), 6)
        self.assertEqual(minimum_digits(64, 3), 4)

    def test_rejects_duplicate_or_out_of_range_codewords(self):
        with self.assertRaises(ValueError):
            RadixCodebook(2, 2, (0, 1, 1))
        with self.assertRaises(ValueError):
            RadixCodebook(2, 2, (0, 4))

    def test_rejects_invalid_radix_and_digit_width(self):
        with self.assertRaises(ValueError):
            canonical_codebook(3, 1)
        with self.assertRaises(ValueError):
            RadixCodebook(3, 0, (0,))

    def test_rejects_invalid_symbol_ids_and_digits(self):
        codebook = canonical_codebook(3, 3)
        for symbol_id in (-1, 3, True, 1.0):
            with self.assertRaises(ValueError):
                codebook.encode(symbol_id)
        for digits in ((3,), (-1,), (1, 2), (True,)):
            with self.assertRaises(ValueError):
                codebook.decode(digits)

    def test_rejects_non_permutation_codebook_assignments(self):
        with self.assertRaises(ValueError):
            permuted_codebook(3, 2, (0, 0, 1))
        with self.assertRaises(ValueError):
            permuted_codebook(3, 2, (0, 1))


if __name__ == "__main__":
    unittest.main()
