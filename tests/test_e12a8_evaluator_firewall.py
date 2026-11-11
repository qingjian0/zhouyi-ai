import json
import unittest
from dataclasses import FrozenInstanceError
from prototype.e12a8_evaluator_firewall import Evaluator, PredictionCommit, commit_payload, run_learner_process

class E12A8EvaluatorFirewallTests(unittest.TestCase):
    def setUp(self):
        self.support = ((0, 0, 1), (1, 0, 0), (0, 1, 2), (1, 1, 1), (2, 0, 2), (0, 2, 0))
        self.query = (2, 2)

    def test_hidden_label_mutation_does_not_change_learner_commit(self):
        first = run_learner_process("episode-1", self.support, self.query)
        second = run_learner_process("episode-1", self.support, self.query)
        self.assertEqual(commit_payload(first), commit_payload(second))
        verdict_a = Evaluator({"episode-1": 0}).evaluate(first)
        verdict_b = Evaluator({"episode-1": 2}).evaluate(second)
        self.assertNotEqual(verdict_a.gold_label, verdict_b.gold_label)
        self.assertEqual(verdict_a.commit_digest, verdict_b.commit_digest)

    def test_candidate_order_and_support_order_are_canonicalized(self):
        a = run_learner_process("episode-2", self.support, self.query)
        b = run_learner_process("episode-2", tuple(reversed(self.support)), self.query)
        self.assertEqual(commit_payload(a), commit_payload(b))

    def test_prediction_commit_is_immutable(self):
        commit = run_learner_process("episode-3", self.support, self.query)
        with self.assertRaises(FrozenInstanceError):
            commit.prediction = 2

    def test_commit_digest_tampering_is_rejected(self):
        commit = run_learner_process("episode-4", self.support, self.query)
        payload = commit_payload(commit)
        payload["prediction"] = 2 if commit.prediction != 2 else 1
        with self.assertRaises(ValueError):
            PredictionCommit.from_worker_payload(payload)

    def test_duplicate_evaluation_is_rejected(self):
        commit = run_learner_process("episode-5", self.support, self.query)
        evaluator = Evaluator({"episode-5": 1})
        evaluator.evaluate(commit)
        with self.assertRaises(ValueError):
            evaluator.evaluate(commit)

    def test_unknown_episode_is_not_scored(self):
        commit = run_learner_process("episode-6", self.support, self.query)
        with self.assertRaises(KeyError):
            Evaluator({}).evaluate(commit)

    def test_public_worker_payload_contains_no_gold_field(self):
        commit = run_learner_process("episode-7", self.support, self.query)
        payload = json.loads(json.dumps(commit_payload(commit)))
        self.assertNotIn("gold", payload)
        self.assertNotIn("label", payload)
        self.assertNotIn("verdict", payload)

if __name__ == "__main__":
    unittest.main()
