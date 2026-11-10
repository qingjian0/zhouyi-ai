import unittest

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example,
)
from prototype.e09_evidence_ledger import EvidenceError, EvidenceLedger


class E09EvidenceLedgerTests(unittest.TestCase):
    def test_append_is_idempotent_for_identical_record(self):
        ledger = EvidenceLedger()
        row = Example((0, 1), "A")
        self.assertTrue(ledger.append("s1", row, source="sensor"))
        self.assertFalse(ledger.append("s1", row, source="sensor"))
        self.assertEqual(ledger.adjudication()["total_records"], 1)

    def test_sample_id_is_immutable(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0,), "A"))
        with self.assertRaises(EvidenceError):
            ledger.append("s1", Example((0,), "B"))

    def test_conflicting_labels_are_quarantined_not_overwritten(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0, 0), "A"))
        ledger.append("s2", Example((0, 0), "B"))
        ledger.append("s3", Example((1, 0), "B"))
        self.assertEqual(ledger.adjudication()["contested_inputs"], 1)
        self.assertEqual(ledger.training_examples(), (Example((1, 0), "B"),))

    def test_repeated_same_label_deduplicates_for_learning(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0, 0), "A"))
        ledger.append("s2", Example((0, 0), "A"))
        self.assertEqual(ledger.adjudication()["repeated_same_label_inputs"], 1)
        self.assertEqual(len(ledger.training_examples()), 1)

    def test_ledger_fits_existing_non_gradient_learner(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0, 0), "A"))
        ledger.append("s2", Example((0, 1), "A"))
        ledger.append("s3", Example((1, 0), "B"))
        ledger.append("s4", Example((1, 1), "B"))
        learner = CounterexampleRuleLearner(((0, 1), (0, 1)), min_support=2)
        ledger.fit(learner)
        self.assertEqual(learner.predict((0, 0)), "A")
        self.assertEqual(learner.predict((1, 1)), "B")


if __name__ == "__main__":
    unittest.main()
