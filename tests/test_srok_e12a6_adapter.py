import unittest
from dataclasses import replace

from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, CandidateState, LifecycleLedger,
)
from prototype.srok0_kernel import (
    ComposedCandidate, Node, OperatorSpec, RoleSpec, SparseRoleComposer,
)
from prototype.srok_e12a6_adapter import adapt_composed_candidate


class SROKE12A6AdapterTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {
            "a": Node("a", "A", score=0.9, evidence_ids=("ev-a",)),
            "b": Node("b", "B", score=0.8, evidence_ids=("ev-b",)),
            "c": Node("c", "C", score=0.7, evidence_ids=("ev-c",)),
        }
        spec = OperatorSpec(
            "triple", "supports",
            (RoleSpec("source", frozenset({"A"})),
             RoleSpec("context", frozenset({"B"})),
             RoleSpec("target", frozenset({"C"}))),
        )
        report = SparseRoleComposer(self.nodes.values()).compose(spec)
        self.composed = report.candidates[0]

    def test_projects_to_observed_candidate_and_shared_dtos(self):
        result = adapt_composed_candidate(
            self.composed, self.nodes, scope="world/test", grammar_version="srok-v1"
        )
        self.assertIs(result.native_candidate.state, CandidateState.OBSERVED)
        self.assertEqual(result.native_candidate.proposer_family, "srok0")
        self.assertEqual(result.native_candidate.input_types, ("A", "B", "C"))
        self.assertEqual(result.interchange.proposal.track_id, "e12a6")
        self.assertEqual(result.interchange.proposal.candidate_ref,
                         result.interchange.structure.ref)
        self.assertEqual(result.interchange.proposal.definition_digest,
                         result.interchange.structure.definition_digest)
        self.assertEqual(result.interchange.proposal.evidence_refs,
                         ("ev-a", "ev-b", "ev-c"))

    def test_raw_score_is_not_misrepresented_as_confidence(self):
        result = adapt_composed_candidate(
            self.composed, self.nodes, scope="world/test", grammar_version="srok-v1"
        )
        self.assertEqual(result.raw_score, self.composed.score)
        self.assertEqual(result.score_semantics, "uncalibrated_ranking_score")
        self.assertEqual(result.native_candidate.uncertainty, 1.0)

    def test_lifecycle_ledger_remains_authoritative(self):
        result = adapt_composed_candidate(
            self.composed, self.nodes, scope="world/test", grammar_version="srok-v1"
        )
        ledger = LifecycleLedger()
        ledger.add_candidate(result.native_candidate)
        ledger.apply(Action(
            action_id="propose-1",
            action_type=ActionType.PROPOSE,
            candidate_id=result.native_candidate.candidate_id,
            candidate_version=result.native_candidate.version,
            from_state=CandidateState.OBSERVED,
            to_state=CandidateState.PROPOSED,
        ))
        current = ledger.candidates[
            (result.native_candidate.candidate_id, result.native_candidate.version)
        ]
        self.assertIs(current.state, CandidateState.PROPOSED)

    def test_score_does_not_change_semantic_candidate_identity(self):
        first = adapt_composed_candidate(
            self.composed, self.nodes, scope="world/test", grammar_version="srok-v1"
        )
        second = adapt_composed_candidate(
            replace(self.composed, score=self.composed.score + 100.0),
            self.nodes, scope="world/test", grammar_version="srok-v1"
        )
        self.assertEqual(first.native_candidate.candidate_id,
                         second.native_candidate.candidate_id)
        self.assertNotEqual(first.raw_score, second.raw_score)

    def test_single_role_candidate_is_rejected(self):
        bad = ComposedCandidate("supports", (("source", "a"),), 0.5, ())
        with self.assertRaisesRegex(ValueError, "at least two"):
            adapt_composed_candidate(
                bad, self.nodes, scope="world/test", grammar_version="srok-v1"
            )

    def test_missing_member_is_rejected(self):
        bad = ComposedCandidate(
            "supports", (("source", "missing"), ("target", "b")), 0.5, ()
        )
        with self.assertRaisesRegex(ValueError, "missing"):
            adapt_composed_candidate(
                bad, self.nodes, scope="world/test", grammar_version="srok-v1"
            )

    def test_duplicate_role_or_evidence_is_rejected(self):
        duplicate_role = ComposedCandidate(
            "supports", (("same", "a"), ("same", "b")), 0.5, ()
        )
        with self.assertRaisesRegex(ValueError, "role names"):
            adapt_composed_candidate(
                duplicate_role, self.nodes, scope="world/test", grammar_version="srok-v1"
            )
        duplicate_evidence = ComposedCandidate(
            "supports", (("source", "a"), ("target", "b")), 0.5, ("ev-a", "ev-a")
        )
        with self.assertRaisesRegex(ValueError, "evidence IDs"):
            adapt_composed_candidate(
                duplicate_evidence, self.nodes, scope="world/test", grammar_version="srok-v1"
            )


if __name__ == "__main__":
    unittest.main()
