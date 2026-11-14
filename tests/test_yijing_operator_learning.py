import unittest

from prototype.yijing_operator_induction import (
    EvidenceKind, ExperimentQuery, Node, Relation, RelationalState,
    TransitionObservation,
)
from prototype.yijing_operator_learning import (
    CandidateLifecycle, EvidenceCase, EvidenceSplit, LearningLoopError,
    OperatorLearningCoordinator,
)


def state(phase="growth"):
    nodes = (Node("a", "agent", "actor"), Node("b", "resource", "target"))
    return RelationalState(
        nodes, (Relation("a", "b", "supports"),), (("phase", phase),)
    )


def changed(relation="constrains", phase="growth"):
    nodes = (Node("a", "agent", "actor"), Node("b", "resource", "target"))
    return RelationalState(
        nodes,
        tuple(sorted((
            Relation("a", "b", "supports"),
            Relation("b", "a", relation),
        ))),
        (("phase", phase),),
    )


def case(before, after, evidence_id, split, kind=EvidenceKind.INTERVENTIONAL):
    return EvidenceCase(
        TransitionObservation(before, after, "allocate", evidence_id, kind, "d1"),
        split,
    )


class UnifiedOperatorLearningTests(unittest.TestCase):
    def setUp(self):
        self.loop = OperatorLearningCoordinator(min_support=1)

    def discover_one(self):
        records = self.loop.propose([
            case(state(), changed(), "d-1", EvidenceSplit.DISCOVERY)
        ])
        self.assertEqual(len(records), 1)
        return records[0]

    def test_discovery_split_only(self):
        with self.assertRaises(LearningLoopError):
            self.loop.propose([
                case(state(), changed(), "v-1", EvidenceSplit.VALIDATION)
            ])

    def test_validation_promotes_but_test_does_not(self):
        record = self.discover_one()
        validation = self.loop.evaluate(
            record.candidate.candidate_id,
            [case(state(), changed(), "v-1", EvidenceSplit.VALIDATION)],
            split=EvidenceSplit.VALIDATION,
        )
        promoted = self.loop.validate(validation)
        self.assertEqual(promoted.lifecycle, CandidateLifecycle.VALIDATED)

        second = OperatorLearningCoordinator(min_support=1)
        candidate = second.propose([
            case(state(), changed(), "d-2", EvidenceSplit.DISCOVERY)
        ])[0]
        test_report = second.evaluate(
            candidate.candidate.candidate_id,
            [case(state(), changed(), "t-1", EvidenceSplit.TEST)],
            split=EvidenceSplit.TEST,
        )
        with self.assertRaises(LearningLoopError):
            second.validate(test_report)

    def test_wrong_validation_does_not_promote(self):
        record = self.discover_one()
        report = self.loop.evaluate(
            record.candidate.candidate_id,
            [case(state(), changed("blocks"), "v-wrong", EvidenceSplit.VALIDATION)],
            split=EvidenceSplit.VALIDATION,
        )
        updated = self.loop.validate(report)
        self.assertEqual(updated.lifecycle, CandidateLifecycle.PROPOSED)
        self.assertEqual(report.incorrect_evidence_ids, ("v-wrong",))

    def test_discovery_evidence_cannot_be_reused(self):
        record = self.discover_one()
        with self.assertRaises(LearningLoopError):
            self.loop.evaluate(
                record.candidate.candidate_id,
                [case(state(), changed(), "d-1", EvidenceSplit.VALIDATION)],
                split=EvidenceSplit.VALIDATION,
            )

    def test_two_candidates_produce_discriminating_query(self):
        self.loop.propose([
            case(state(), changed("constrains"), "d-a", EvidenceSplit.DISCOVERY),
            case(state(), changed("enables"), "d-b", EvidenceSplit.DISCOVERY),
        ])
        query = ExperimentQuery(state(), "allocate", "d1", "q-1")
        ranked = self.loop.rank_queries([query])
        self.assertEqual(ranked[0].query_id, "q-1")
        self.loop.commit_experiment(query)

    def test_counterexample_suspends_candidate_and_is_retained(self):
        record = self.discover_one()
        query = ExperimentQuery(state(), "allocate", "d1", "q-2")
        # Only one candidate exists, so use a second competing candidate.
        self.loop.propose([
            case(state(), changed("enables"), "d-2", EvidenceSplit.DISCOVERY)
        ])
        self.loop.commit_experiment(query)
        feedback = self.loop.reveal_experiment(
            "q-2", changed("blocks"), evidence_id="intervention-1",
            evidence_kind=EvidenceKind.INTERVENTIONAL,
        )
        self.assertIn(record.candidate.candidate_id, feedback.contradicted_candidate_ids)
        self.assertEqual(
            self.loop.candidates[0].lifecycle, CandidateLifecycle.SUSPENDED
        )
        self.assertIn("intervention-1", self.loop.candidates[0].counterexample_ids)

    def test_outcome_requires_committed_query(self):
        self.discover_one()
        with self.assertRaises(LearningLoopError):
            self.loop.reveal_experiment(
                "unknown", changed(), evidence_id="x",
                evidence_kind=EvidenceKind.OBSERVATIONAL,
            )

    def test_query_cannot_be_revealed_twice(self):
        self.loop.propose([
            case(state(), changed("constrains"), "d-a", EvidenceSplit.DISCOVERY),
            case(state(), changed("enables"), "d-b", EvidenceSplit.DISCOVERY),
        ])
        query = ExperimentQuery(state(), "allocate", "d1", "q-3")
        self.loop.commit_experiment(query)
        self.loop.reveal_experiment(
            "q-3", changed("constrains"), evidence_id="intervention-2",
            evidence_kind=EvidenceKind.INTERVENTIONAL,
        )
        with self.assertRaises(LearningLoopError):
            self.loop.reveal_experiment(
                "q-3", changed("constrains"), evidence_id="intervention-3",
                evidence_kind=EvidenceKind.INTERVENTIONAL,
            )

    def test_evaluation_split_evidence_is_not_reused(self):
        record = self.discover_one()
        rows = [case(state(), changed(), "v-2", EvidenceSplit.VALIDATION)]
        self.loop.evaluate(
            record.candidate.candidate_id, rows, split=EvidenceSplit.VALIDATION
        )
        with self.assertRaises(LearningLoopError):
            self.loop.evaluate(
                record.candidate.candidate_id, rows, split=EvidenceSplit.VALIDATION
            )

    def test_evidence_id_cannot_cross_validation_and_test(self):
        record = self.discover_one()
        self.loop.evaluate(
            record.candidate.candidate_id,
            [case(state(), changed(), "shared-id", EvidenceSplit.VALIDATION)],
            split=EvidenceSplit.VALIDATION,
        )
        with self.assertRaises(LearningLoopError):
            self.loop.evaluate(
                record.candidate.candidate_id,
                [case(state(), changed(), "shared-id", EvidenceSplit.TEST)],
                split=EvidenceSplit.TEST,
            )

    def test_candidate_accumulates_evidence_across_discovery_batches(self):
        loop = OperatorLearningCoordinator(min_support=2)
        first = loop.propose([
            case(state("growth"), changed(phase="growth"), "batch-a", EvidenceSplit.DISCOVERY)
        ])[0]
        second = loop.propose([
            case(state("decline"), changed(phase="decline"), "batch-b", EvidenceSplit.DISCOVERY)
        ])[0]
        self.assertEqual(first.candidate.candidate_id, second.candidate.candidate_id)
        self.assertEqual(second.candidate.version, 2)
        self.assertEqual(second.candidate.evidence_ids, ("batch-a", "batch-b"))
        self.assertEqual(second.candidate.status.value, "INTERVENTION_SUPPORTED")


if __name__ == "__main__":
    unittest.main()
