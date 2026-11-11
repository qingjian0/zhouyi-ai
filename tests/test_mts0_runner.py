import unittest

from prototype.mts0_runner import (
    ConsumerRole,
    EvidenceLedger,
    EvidenceSplit,
    run_mts0,
)


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = EvidenceLedger()
        self.commit = self.ledger.commit(
            commit_id="c1",
            query_id="q1",
            scope="world-a",
            input_payload={"x": [1, 2]},
            model_version="model-1",
            prediction=(0, 2),
        )

    def test_reveal_must_follow_commit(self):
        with self.assertRaises(ValueError):
            self.ledger.reveal(
                evidence_id="e1",
                commit_id="missing",
                scope="world-a",
                split=EvidenceSplit.SUPPORT,
                outcome=(0, 2),
            )

    def test_reveal_binds_scope_and_commit_digest(self):
        with self.assertRaises(ValueError):
            self.ledger.reveal(
                evidence_id="e1",
                commit_id="c1",
                scope="world-b",
                split=EvidenceSplit.SUPPORT,
                outcome=(0, 2),
            )
        reveal = self.ledger.reveal(
            evidence_id="e1",
            commit_id="c1",
            scope="world-a",
            split=EvidenceSplit.LOCKED_TEST,
            outcome=(0, 2),
        )
        self.assertEqual(reveal.commit_digest, self.commit.commit_digest)

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.commit(
                commit_id="c1", query_id="q2", scope="world-a",
                input_payload={}, model_version="model-1", prediction=(1,),
            )

    def test_locked_test_visibility_is_evaluator_only(self):
        self.ledger.reveal(
            evidence_id="locked",
            commit_id="c1",
            scope="world-a",
            split=EvidenceSplit.LOCKED_TEST,
            outcome=(0, 2),
        )
        self.assertEqual(self.ledger.visible_reveals(ConsumerRole.LEARNER), ())
        self.assertEqual(self.ledger.visible_reveals(ConsumerRole.SELECTOR), ())
        self.assertEqual(len(self.ledger.visible_reveals(ConsumerRole.EVALUATOR)), 1)

    def test_support_is_visible_to_learner_and_selector(self):
        self.ledger.reveal(
            evidence_id="support",
            commit_id="c1",
            scope="world-a",
            split=EvidenceSplit.SUPPORT,
            outcome=(0, 2),
        )
        self.assertEqual(len(self.ledger.visible_reveals(ConsumerRole.LEARNER)), 1)
        self.assertEqual(len(self.ledger.visible_reveals(ConsumerRole.SELECTOR)), 1)

    def test_bad_prediction_indices_are_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.commit(
                commit_id="bad", query_id="q", scope="w", input_payload={},
                model_version="m", prediction=(True,),
            )


class MTS0RunnerTests(unittest.TestCase):
    def test_runner_commits_before_locked_reveal(self):
        result = run_mts0(seed=3, train_count=100, locked_test_count=40, epochs=40)
        audit = result["audit"]
        self.assertEqual(audit["prediction_commits"], 40)
        self.assertEqual(audit["locked_test_reveals"], 40)
        self.assertEqual(audit["learner_visible_locked_test_reveals"], 0)
        self.assertEqual(audit["selector_visible_locked_test_reveals"], 0)
        self.assertEqual(audit["evaluator_visible_locked_test_reveals"], 40)
        self.assertTrue(audit["all_predictions_committed_before_reveal"])

    def test_runner_is_reproducible(self):
        first = run_mts0(seed=9, train_count=80, locked_test_count=30, epochs=30)
        second = run_mts0(seed=9, train_count=80, locked_test_count=30, epochs=30)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
