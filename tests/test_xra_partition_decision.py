import unittest

from prototype.xra_partition_decision import (
    PairChallengeEvidence,
    PartitionDecision,
    decide_pair_partition,
)


def evidence(action, trial, left="same", right="same", left_next="x", right_next="x"):
    return PairChallengeEvidence(
        action=action,
        trial_id=trial,
        left_outcome=left,
        right_outcome=right,
        left_successor_signature=left_next,
        right_successor_signature=right_next,
    )


class XRAPartitionDecisionTests(unittest.TestCase):
    def test_incomplete_coverage_is_unresolved_not_merge(self):
        result = decide_pair_partition(
            ("observe", "wait"),
            [evidence("observe", "t1")],
        )
        self.assertEqual(result.decision, PartitionDecision.UNRESOLVED)
        self.assertEqual(result.missing_actions, ("wait",))

    def test_complete_matching_evidence_supports_scoped_merge(self):
        result = decide_pair_partition(
            ("observe", "wait"),
            [evidence("observe", "t1"), evidence("wait", "t2")],
        )
        self.assertEqual(result.decision, PartitionDecision.MERGE)
        self.assertEqual(result.missing_actions, ())
        self.assertIn("only", result.scope)

    def test_immediate_outcome_counterexample_forces_split(self):
        result = decide_pair_partition(
            ("observe", "wait"),
            [
                evidence("observe", "t1", left="red", right="blue"),
                evidence("wait", "t2"),
            ],
        )
        self.assertEqual(result.decision, PartitionDecision.SPLIT)
        self.assertEqual(result.counterexample_trials, ("t1",))

    def test_successor_signature_counterexample_forces_split(self):
        result = decide_pair_partition(
            ("observe",),
            [evidence("observe", "t1", left_next="class-a", right_next="class-b")],
        )
        self.assertEqual(result.decision, PartitionDecision.SPLIT)

    def test_split_takes_priority_even_when_other_actions_missing(self):
        result = decide_pair_partition(
            ("observe", "wait"),
            [evidence("observe", "t1", left="different", right="outcome")],
        )
        self.assertEqual(result.decision, PartitionDecision.SPLIT)
        self.assertEqual(result.missing_actions, ("wait",))

    def test_minimum_repetitions_gate_merge(self):
        result = decide_pair_partition(
            ("observe",),
            [evidence("observe", "t1")],
            min_repetitions_per_action=2,
        )
        self.assertEqual(result.decision, PartitionDecision.UNRESOLVED)

    def test_repeated_trial_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            decide_pair_partition(
                ("observe",),
                [evidence("observe", "same"), evidence("observe", "same")],
            )

    def test_undeclared_action_is_rejected(self):
        with self.assertRaises(ValueError):
            decide_pair_partition(
                ("observe",), [evidence("unknown", "t1")]
            )

    def test_empty_actions_and_bad_repetition_count_are_rejected(self):
        with self.assertRaises(ValueError):
            decide_pair_partition((), [])
        with self.assertRaises(ValueError):
            decide_pair_partition(("observe",), [], min_repetitions_per_action=0)


if __name__ == "__main__":
    unittest.main()
