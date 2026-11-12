import unittest

from prototype.cpg_ei_selection_split_sweep import (
    SPLIT_CONFIGS,
    partition_states,
)


class CpgEiSelectionSplitSizeSweepTests(unittest.TestCase):
    def test_split_configs_are_deterministic_disjoint_and_complete(self):
        universe = {
            tuple((value >> bit) & 1 for bit in range(6))
            for value in range(64)
        }
        for train_size, proposal_size, locked_size in SPLIT_CONFIGS:
            first = partition_states(47, train_size, proposal_size, locked_size)
            second = partition_states(47, train_size, proposal_size, locked_size)
            self.assertEqual(first, second)
            train, proposal, locked = map(set, first)
            self.assertEqual((len(train), len(proposal), len(locked)),
                             (train_size, proposal_size, locked_size))
            self.assertFalse(train & proposal)
            self.assertFalse(train & locked)
            self.assertFalse(proposal & locked)
            self.assertEqual(train | proposal | locked, universe)

    def test_partition_rejects_invalid_sizes(self):
        with self.assertRaises(ValueError):
            partition_states(1, 40, 12, 11)
        with self.assertRaises(ValueError):
            partition_states(1, 0, 52, 12)


if __name__ == "__main__":
    unittest.main()
