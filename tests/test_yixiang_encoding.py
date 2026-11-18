import unittest

from prototype.yixiang_encoding import (
    all_hexagram_states,
    change_lines,
    encode_hexagram,
    transition_hexagram,
    trigram_name,
)


class YixiangEncodingTests(unittest.TestCase):
    def test_eight_trigrams(self):
        expected = {
            (1, 1, 1): "乾", (1, 1, 0): "兑",
            (1, 0, 1): "离", (1, 0, 0): "震",
            (0, 1, 1): "巽", (0, 1, 0): "坎",
            (0, 0, 1): "艮", (0, 0, 0): "坤",
        }
        for lines, name in expected.items():
            self.assertEqual(trigram_name(lines), name)

    def test_hexagram_splits_lower_and_upper_trigrams(self):
        state = encode_hexagram((1, 1, 1, 0, 0, 0))
        self.assertEqual(state.binary_id, 7)
        self.assertEqual(state.lower_trigram, "乾")
        self.assertEqual(state.upper_trigram, "坤")

    def test_all_64_binary_states_are_unique(self):
        states = all_hexagram_states()
        self.assertEqual(len(states), 64)
        self.assertEqual(len({state.binary_id for state in states}), 64)

    def test_line_change_uses_bottom_zero_index(self):
        self.assertEqual(change_lines((0, 0, 0, 0, 0, 0), [0, 5]), (1, 0, 0, 0, 0, 1))

    def test_invalid_line_value_rejected(self):
        with self.assertRaises(ValueError):
            trigram_name((0, 1, 2))

    def test_non_integer_and_boolean_lines_are_rejected(self):
        invalid_values = (0.0, 1.0, 0.5, "0", "1", False, True)
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    trigram_name((0, value, 1))

    def test_non_integer_and_boolean_change_indices_are_rejected(self):
        invalid_indices = (0.0, 1.5, "0", False, True)
        for index in invalid_indices:
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    change_lines((0, 0, 0, 0, 0, 0), [index])

    
    def test_rejects_duplicate_changing_line_indices(self):
        with self.assertRaises(ValueError):
            change_lines((0, 0, 0, 0, 0, 0), [2, 2])

    def test_transition_retains_before_after_and_moving_line_positions(self):
        transition = transition_hexagram((0, 0, 0, 0, 0, 0), [0, 5])
        self.assertEqual(transition.before.lines_bottom_to_top, (0, 0, 0, 0, 0, 0))
        self.assertEqual(transition.after.lines_bottom_to_top, (1, 0, 0, 0, 0, 1))
        self.assertEqual(transition.changing_indices_bottom_to_top, (0, 5))
        self.assertEqual(transition.before.binary_id ^ transition.after.binary_id, 33)

    def test_empty_moving_lines_is_identity_transition(self):
        transition = transition_hexagram((1, 0, 1, 0, 1, 0), [])
        self.assertEqual(transition.before, transition.after)


if __name__ == "__main__":
    unittest.main()
