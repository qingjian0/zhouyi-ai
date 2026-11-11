import unittest
from dataclasses import replace

from prototype.csg_gcr_coordinator import CandidateProposal
from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation, canonical_hash
from prototype.csg_gcr_e12a6_adapter import adapt_typed_candidate
from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, CandidateState, LifecycleLedger,
)
from prototype.typed_csg_gcr import TypedCandidateCoordinator, TypedCandidateProposal
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal, RoleBinding, VariableRef, VariableSpec,
)


class CSGGCRE12A6AdapterTests(unittest.TestCase):
    def make_result(self, *, score=4.5, branch="b1"):
        ref = VariableRef("wl", "entity")
        edge = HyperedgeProposal(
            "edge-1", "parent-1", branch, "supports",
            (RoleBinding("subject", ref, "entity-1", "Entity"),),
            ("ev-1",),
        )
        proposal = CandidateProposal(
            "edge-1", "parent-1", branch, (), ("ev-1",),
            score=score, candidate_kind="supports",
        )
        typed = TypedCandidateProposal(
            proposal, edge, (VariableSpec(ref, "Entity"),),
        )
        report = TypedCandidateCoordinator().coordinate((typed,))
        self.assertTrue(report.candidates)
        return report.candidates[0]

    def test_projects_to_observed_e12_candidate_and_shared_dtos(self):
        result = adapt_typed_candidate(
            self.make_result(), scope="world/test", grammar_version="csg-gcr-v1",
        )
        native = result.native_candidate
        self.assertIs(native.state, CandidateState.OBSERVED)
        self.assertEqual(native.proposer_family, "csg-gcr")
        self.assertEqual(native.operator, "supports")
        self.assertEqual(native.input_types, ("Entity",))
        self.assertEqual(native.evidence_ids, ("ev-1",))
        self.assertEqual(result.interchange.proposal.track_id, "e12a6")
        self.assertEqual(result.interchange.proposal.candidate_ref,
                         result.interchange.structure.ref)
        self.assertEqual(result.interchange.proposal.definition_digest,
                         result.interchange.structure.definition_digest)

    def test_raw_score_is_not_confidence_or_uncertainty(self):
        result = adapt_typed_candidate(
            self.make_result(score=9.25), scope="world/test",
            grammar_version="csg-gcr-v1",
        )
        self.assertEqual(result.raw_score, 9.25)
        self.assertEqual(result.score_semantics, "uncalibrated_ranking_score")
        self.assertEqual(result.native_candidate.uncertainty, 1.0)

    def test_score_does_not_change_semantic_candidate_identity(self):
        first = self.make_result(score=1.0)
        second = self.make_result(score=100.0)
        a = adapt_typed_candidate(first, scope="world/test", grammar_version="v1")
        b = adapt_typed_candidate(second, scope="world/test", grammar_version="v1")
        self.assertEqual(a.native_candidate.candidate_id, b.native_candidate.candidate_id)
        self.assertNotEqual(a.raw_score, b.raw_score)

    def test_e12_lifecycle_ledger_remains_authoritative(self):
        projection = adapt_typed_candidate(
            self.make_result(), scope="world/test", grammar_version="v1",
        )
        ledger = LifecycleLedger()
        ledger.add_candidate(projection.native_candidate)
        ledger.apply(Action(
            action_id="propose-csg-1",
            action_type=ActionType.PROPOSE,
            candidate_id=projection.native_candidate.candidate_id,
            candidate_version=projection.native_candidate.version,
            from_state=CandidateState.OBSERVED,
            to_state=CandidateState.PROPOSED,
        ))
        current = ledger.candidates[
            (projection.native_candidate.candidate_id,
             projection.native_candidate.version)
        ]
        self.assertIs(current.state, CandidateState.PROPOSED)

    def test_branch_delta_provenance_is_projected_into_e12(self):
        base = {"node:a": {"value": 0}}
        ref = VariableRef("wl", "entity")
        edge = HyperedgeProposal(
            "edge-1", "parent-1", "b1", "supports",
            (RoleBinding("subject", ref, "entity-1", "Entity"),),
            ("ev-1",),
        )
        proposal = CandidateProposal(
            "edge-1", "parent-1", "b1", (), ("ev-1",),
            candidate_kind="supports",
        )
        typed = TypedCandidateProposal(proposal, edge, (VariableSpec(ref, "Entity"),))
        delta = BranchDelta(
            "d1", DeltaOperation.UPDATE_ATTRIBUTE, "node:a",
            canonical_hash(base["node:a"]), {"value": 1},
            ("derivation:d1",), None, 1,
        )
        snapshot = BranchSnapshot(
            "parent-1", canonical_hash(base), "b1", 0, (delta,), (),
            ("node:a",), ("derivation:d1",), ("root", "b1"),
        )
        report = TypedCandidateCoordinator().coordinate(
            (typed,), base_state=base, branch_snapshots=(snapshot,),
        )
        projection = adapt_typed_candidate(
            report.candidates[0], scope="world/test", grammar_version="v1",
        )
        self.assertEqual(
            projection.native_candidate.evidence_ids,
            ("derivation:d1", "ev-1"),
        )
        self.assertIn("state_digest", projection.native_candidate.canonical_expression)

    def test_inconsistent_parent_or_evidence_is_rejected(self):
        result = self.make_result()
        bad_unification = replace(result.unification, parent_state_ref="other-parent")
        with self.assertRaisesRegex(ValueError, "parent state"):
            adapt_typed_candidate(
                replace(result, unification=bad_unification),
                scope="world/test", grammar_version="v1",
            )

    def test_invalid_scope_and_version_are_rejected(self):
        result = self.make_result()
        with self.assertRaises(ValueError):
            adapt_typed_candidate(result, scope="", grammar_version="v1")
        with self.assertRaises(ValueError):
            adapt_typed_candidate(result, scope="world/test", grammar_version="v1", version=0)


if __name__ == "__main__":
    unittest.main()
