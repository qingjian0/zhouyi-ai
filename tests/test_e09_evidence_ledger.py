import unittest

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example,
)
from prototype.e09_evidence_ledger import (
    EvidenceError, EvidenceLedger, EvidenceRecord,
)


class E09EvidenceLedgerTests(unittest.TestCase):
    def test_append_is_idempotent_for_identical_record(self):
        ledger = EvidenceLedger()
        row = Example((0, 1), "A")
        self.assertTrue(ledger.append("s1", row, source="sensor", source_id="sensor-1"))
        self.assertFalse(ledger.append("s1", row, source="sensor", source_id="sensor-1"))
        self.assertEqual(ledger.adjudication()["total_records"], 1)

    def test_sample_id_is_immutable(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0,), "A"))
        with self.assertRaises(EvidenceError):
            ledger.append("s1", Example((0,), "B"))

    def test_conflicting_labels_are_quarantined_not_overwritten(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0, 0), "A"), source_id="sensor-A")
        ledger.append("s2", Example((0, 0), "B"), source_id="sensor-B")
        ledger.append("s3", Example((1, 0), "B"))
        self.assertEqual(ledger.adjudication()["contested_inputs"], 1)
        self.assertEqual(ledger.training_examples(), (Example((1, 0), "B"),))

    def test_repeated_same_label_deduplicates_for_learning_and_counts_sources(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0, 0), "A"), source_id="sensor-A")
        ledger.append("s2", Example((0, 0), "A"), source_id="sensor-A")
        ledger.append("s3", Example((0, 0), "A"), source_id="sensor-B")
        self.assertEqual(ledger.adjudication()["repeated_same_label_inputs"], 1)
        evidence = ledger.adjudication()["source_evidence"][0]
        self.assertEqual(evidence["labels"][0]["distinct_source_ids"], 2)
        self.assertEqual(len(ledger.training_examples()), 1)

    def test_extend_is_atomic_when_batch_has_conflicting_ids(self):
        ledger = EvidenceLedger()
        ledger.append("existing", Example((0,), "A"))
        batch = [
            EvidenceRecord("new", Example((1,), "B")),
            EvidenceRecord("existing", Example((0,), "different")),
        ]
        with self.assertRaises(EvidenceError):
            ledger.extend(batch)
        self.assertEqual([r.sample_id for r in ledger.records()], ["existing"])

    def test_extend_is_idempotent_for_duplicate_identical_records(self):
        ledger = EvidenceLedger()
        record = EvidenceRecord("s1", Example((0,), "A"), source_id="sensor-1")
        self.assertEqual(ledger.extend([record, record]), 1)
        self.assertEqual(ledger.extend([record]), 0)

    def test_appended_counterexample_invalidates_previous_generalization(self):
        ledger = EvidenceLedger()
        ledger.append("s1", Example((0, 0, 0), "yes"))
        ledger.append("s2", Example((0, 1, 0), "yes"))
        ledger.append("s3", Example((1, 0, 0), "no"))
        ledger.append("s4", Example((1, 1, 0), "no"))
        learner = CounterexampleRuleLearner(
            ((0, 1), (0, 1), (0, 1, 2)), min_support=2
        )
        ledger.fit(learner)
        self.assertEqual(learner.predict((0, 0, 2)), "yes")
        ledger.append("s5", Example((0, 0, 2), "no"), source="new_observation")
        ledger.fit(learner)
        self.assertIsNone(learner.predict((0, 0, 2)))

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
