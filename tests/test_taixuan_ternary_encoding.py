import unittest

from prototype.taixuan_ternary_encoding import (
    HEAD_COUNT,
    PRAISE_COUNT,
    STATE_COUNT,
    decode_head_praise,
    decode_index,
    encode_head_praise,
    encode_trits,
    iter_all_indices,
)


class TaixuanTernaryEncodingTests(unittest.TestCase):
    def test_cardinality_matches_research_structure(self):
        self.assertEqual(HEAD_COUNT, 81)
        self.assertEqual(PRAISE_COUNT, 9)
        self.assertEqual(STATE_COUNT, 729)

    def test_all_729_indices_are_unique_and_reversible(self):
        indices = tuple(iter_all_indices())
        self.assertEqual(len(indices), 729)
        self.assertEqual(len(set(indices)), 729)
        for index in indices:
            self.assertEqual(encode_trits(decode_index(index)), index)

    def test_head_praise_round_trip(self):
        head = (2, 0, 1, 2)
        praise = (1, 0)
        index = encode_head_praise(head, praise)
        self.assertEqual(decode_head_praise(index), (head, praise))

    def test_rejects_invalid_trits_and_indices(self):
        with self.assertRaises(ValueError):
            encode_trits((0, 1, 2, 0, 1, 3))
        with self.assertRaises(ValueError):
            decode_index(729)
        with self.assertRaises(ValueError):
            decode_index(-1)


if __name__ == "__main__":
    unittest.main()
