import math, unittest
from prototype.cpg_ei_selection_sweep import RULE_FAMILIES, partition_states, run_sweep

class CpgEiSelectionSweepTests(unittest.TestCase):
    def test_partitions_cover_all_states_without_overlap(self):
        parts = partition_states(77)
        self.assertEqual(tuple(map(len, parts)), (40, 12, 12))
        sets = tuple(set(part) for part in parts)
        self.assertEqual(len(set.union(*sets)), 64)
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertFalse(sets[i] & sets[j])

    def test_small_multifamily_sweep_reports_separate_metrics(self):
        report = run_sweep(seeds=(11,), epochs=2, max_motifs=1)
        self.assertEqual(report['aggregate']['experiments'], len(RULE_FAMILIES))
        self.assertEqual(len(report['records']), 3)
        for row in report['records']:
            self.assertEqual((row['train_examples'], row['proposal_examples'], row['locked_test_examples']), (40, 12, 12))
            self.assertEqual(len(row['ood_bit_accuracy_by_family']), 2)
            for key in ('support_precision', 'support_recall', 'locked_test_bit_accuracy'):
                self.assertTrue(math.isfinite(row[key]))
                self.assertGreaterEqual(row[key], 0.0)
                self.assertLessEqual(row[key], 1.0)

if __name__ == '__main__':
    unittest.main()