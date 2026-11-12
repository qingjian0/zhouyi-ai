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
        report = run_sweep(seeds=(11,), epochs=2, oracle_epochs=2, max_motifs=1)
        self.assertEqual(len(report['records']), 2 * len(RULE_FAMILIES))
        self.assertEqual(set(report['aggregate_by_protocol_and_budget']), {'proposal_split@2', 'legacy_train_ranked@2'})
        self.assertEqual(report['aggregate_by_protocol_and_budget']['proposal_split@2']['experiments'], 3)
        self.assertEqual(report['aggregate_by_protocol_and_budget']['legacy_train_ranked@2']['experiments'], 3)
        for row in report['records']:
            self.assertEqual((row['train_examples'], row['proposal_examples'], row['locked_test_examples']), (40, 12 if row['selection_protocol'] == 'proposal_split' else 0, 12))
            self.assertEqual(len(row['ood_bit_accuracy_by_family']), 2)
            self.assertEqual(len(row['oracle_ood_bit_accuracy_by_family']), 2)
            self.assertTrue(math.isfinite(row['oracle_final_train_loss']))
            self.assertIn(row['selection_protocol'], ('proposal_split', 'legacy_train_ranked'))
            self.assertEqual(row['proposal_examples'], 12 if row['selection_protocol'] == 'proposal_split' else 0)
            self.assertEqual(row['selection_metric_source'], 'proposal' if row['selection_protocol'] == 'proposal_split' else 'train')
            self.assertTrue(math.isfinite(row['selection_bce']))
            for key in ('support_recall', 'locked_test_bit_accuracy', 'oracle_train_bit_accuracy', 'oracle_locked_test_bit_accuracy', 'oracle_full_universe_bit_accuracy'):
                self.assertTrue(math.isfinite(row[key]))
                self.assertGreaterEqual(row[key], 0.0)
                self.assertLessEqual(row[key], 1.0)
            if row['support_precision'] is None:
                self.assertEqual(row['active_edge_count'], 0)
            else:
                self.assertTrue(math.isfinite(row['support_precision']))
                self.assertGreaterEqual(row['support_precision'], 0.0)
                self.assertLessEqual(row['support_precision'], 1.0)

if __name__ == '__main__':
    unittest.main()