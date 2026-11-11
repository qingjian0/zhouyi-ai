import unittest

from prototype.mts0_runner import (
    ConsumerRole,
    EvidenceLedger,
    EvidenceSplit,
    run_mts0,
    run_mts0_multiseed,
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

    def test_reveal_requires_sealed_batch_and_existing_commit(self):
        with self.assertRaisesRegex(ValueError, "must be sealed"):
            self.ledger.reveal(
                evidence_id="e1",
                commit_id="c1",
                scope="world-a",
                split=EvidenceSplit.SUPPORT,
                outcome=(0, 2),
            )
        self.ledger.seal_commits()
        with self.assertRaisesRegex(ValueError, "existing prediction commit"):
            self.ledger.reveal(
                evidence_id="e1",
                commit_id="missing",
                scope="world-a",
                split=EvidenceSplit.SUPPORT,
                outcome=(0, 2),
            )

    def test_commit_is_rejected_after_batch_is_sealed(self):
        self.ledger.seal_commits()
        with self.assertRaisesRegex(ValueError, "after the commit phase is sealed"):
            self.ledger.commit(
                commit_id="c2", query_id="q2", scope="world-a",
                input_payload={}, model_version="model-1", prediction=(1,),
            )

    def test_reveal_binds_scope_and_commit_digest(self):
        self.ledger.seal_commits()
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
        self.ledger.seal_commits()
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
        self.ledger.seal_commits()
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
        self.assertTrue(audit["prediction_batch_sealed_before_reveal"])
        self.assertTrue(audit["all_predictions_committed_before_reveal"])
        self.assertTrue(audit["learner_and_evaluator_are_distinct_processes"])
        self.assertTrue(audit["evaluator_started_after_batch_seal"])
        self.assertEqual(audit["learner_received_locked_test_label_count"], 0)
        self.assertEqual(audit["evaluator_received_locked_test_label_count"], 40)
        self.assertNotEqual(audit["learner_pid"], audit["evaluator_pid"])

    def test_multiseed_runner_reports_mean_stddev_and_audits(self):
        result = run_mts0_multiseed(
            start_seed=20,
            seed_count=5,
            train_count=80,
            locked_test_count=30,
            epochs=30,
        )
        self.assertEqual(result["seed_count"], 5)
        self.assertEqual(len(result["per_seed"]), 5)
        self.assertIn("sample_stddev", result["summary"]["exact_match"])
        self.assertTrue(all(
            row["audit"]["all_predictions_committed_before_reveal"]
            for row in result["per_seed"]
        ))

    def test_multiseed_requires_at_least_two_seeds(self):
        with self.assertRaisesRegex(ValueError, "at least 2"):
            run_mts0_multiseed(seed_count=1, train_count=5, locked_test_count=2)

    def test_runner_is_reproducible(self):
        first = run_mts0(seed=9, train_count=80, locked_test_count=30, epochs=30)
        second = run_mts0(seed=9, train_count=80, locked_test_count=30, epochs=30)
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual(first["model_version"], second["model_version"])
        self.assertEqual(first["learned_weights"], second["learned_weights"])
        first_audit = {
            key: value for key, value in first["audit"].items()
            if not key.endswith("_pid")
        }
        second_audit = {
            key: value for key, value in second["audit"].items()
            if not key.endswith("_pid")
        }
        self.assertEqual(first_audit, second_audit)


if __name__ == "__main__":
    unittest.main()
