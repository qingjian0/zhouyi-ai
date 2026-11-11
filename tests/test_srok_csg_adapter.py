import unittest

from prototype.csg_gcr_coordinator import CandidateCoordinator, CoordinationError
from prototype.srok0_kernel import ComposedCandidate
from prototype.srok_csg_adapter import proposal_from_srok


class SROKToCSGAdapterTests(unittest.TestCase):
    def candidate(self, relation, bindings, score=1.0, evidence=()):
        return ComposedCandidate(
            relation_type=relation,
            role_bindings=tuple(bindings),
            score=score,
            evidence_ids=tuple(evidence),
        )

    def test_explicit_variable_mapping_connects_non_adjacent_relations(self):
        left = proposal_from_srok(
            self.candidate("causes", (("source", "rain"), ("target", "flood")), 2,
                           ("ev-left",)),
            proposal_id="left", parent_state_ref="s0", branch_id="forward",
            role_variables={"source": "x", "target": "y"},
        )
        right = proposal_from_srok(
            self.candidate("amplifies", (("source", "flood"), ("target", "damage")), 3,
                           ("ev-right",)),
            proposal_id="right", parent_state_ref="s0", branch_id="analogy",
            role_variables={"source": "y", "target": "z"},
        )
        report = CandidateCoordinator().coordinate([left, right])
        best = report.candidates[0]
        self.assertEqual(best.proposal_ids, ("left", "right"))
        self.assertEqual(best.candidate_kinds, ("amplifies", "causes"))
        self.assertEqual(best.bindings, (("x", "rain"), ("y", "flood"),
                                         ("z", "damage")))
        self.assertEqual(best.evidence_refs, ("ev-left", "ev-right"))

    def test_conflicting_roles_cannot_bind_same_variable(self):
        candidate = self.candidate(
            "pair", (("source", "a"), ("target", "b"))
        )
        with self.assertRaises(CoordinationError):
            proposal_from_srok(
                candidate, proposal_id="p", parent_state_ref="s0",
                branch_id="b0",
                role_variables={"source": "same", "target": "same"},
            )

    def test_every_role_requires_explicit_variable_mapping(self):
        candidate = self.candidate("pair", (("source", "a"), ("target", "b")))
        with self.assertRaises(CoordinationError):
            proposal_from_srok(
                candidate, proposal_id="p", parent_state_ref="s0",
                branch_id="b0", role_variables={"source": "x"},
            )


if __name__ == "__main__":
    unittest.main()
