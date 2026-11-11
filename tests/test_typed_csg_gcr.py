import unittest

from prototype.csg_gcr_coordinator import CandidateProposal, GlobalConstraints
from prototype.typed_csg_gcr import (
    TypedCandidateCoordinator, TypedCandidateProposal,
)
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal, RoleBinding, UnificationConstraints,
    VariableRef, VariableSpec,
)


class TypedCSGBridgeTests(unittest.TestCase):
    def make(self, name, relation, role_rows, variables, *, branch="b1",
             evidence=(), start=None, end=None, score=1.0, constraints=None):
        edge = HyperedgeProposal(
            name, "s0", branch, relation, tuple(role_rows), tuple(evidence),
            start, end,
        )
        proposal = CandidateProposal(
            name, "s0", branch, (), tuple(evidence), score=score,
            candidate_kind=relation,
        )
        return TypedCandidateProposal(
            proposal, edge, tuple(variables),
            constraints or UnificationConstraints(),
        )

    def test_typed_bridge_composes_and_preserves_provenance(self):
        x, y, z = (VariableRef("wl-A", n) for n in ("x", "y", "z"))
        rows = [
            self.make("e1", "causes", [
                RoleBinding("source", x, "rain", "WeatherEvent"),
                RoleBinding("target", y, "flood", "Event"),
            ], [VariableSpec(x, "Entity"), VariableSpec(y, "Entity")],
                branch="forward", evidence=("ev-a",), score=2),
            self.make("e2", "amplifies", [
                RoleBinding("source", y, "flood", "Event"),
                RoleBinding("target", z, "damage", "Outcome"),
            ], [VariableSpec(y, "Entity"), VariableSpec(z, "Entity")],
                branch="analogy", evidence=("ev-b",), score=3,
                constraints=UnificationConstraints(subtype_of=(
                    ("WeatherEvent", "Event"), ("Event", "Entity"),
                    ("Outcome", "Entity"),
                ))),
        ]
        report = TypedCandidateCoordinator().coordinate(rows)
        best = report.candidates[0]
        self.assertEqual(best.coordinated.proposal_ids, ("e1", "e2"))
        self.assertEqual(best.unification.evidence_refs, ("ev-a", "ev-b"))
        self.assertEqual(best.unification.branch_ids, ("analogy", "forward"))
        self.assertEqual(best.unification.active_from, None)

    def test_type_conflict_rejects_combination(self):
        x = VariableRef("wl", "x")
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "same-member", "Animal")],
                      [VariableSpec(x, "Entity")], evidence=("a",),
                      constraints=UnificationConstraints(subtype_of=(("Animal", "Entity"),))),
            self.make("e2", "r2", [RoleBinding("b", x, "same-member", "Vehicle")],
                      [VariableSpec(x, "Entity")], evidence=("b",),
                      constraints=UnificationConstraints(subtype_of=(("Vehicle", "Entity"),))),
        ]
        report = TypedCandidateCoordinator().coordinate(rows)
        self.assertGreater(report.rejected_typed_sets, 0)
        self.assertFalse(any(len(x.coordinated.proposal_ids) == 2
                             for x in report.candidates))

    def test_temporal_conflict_rejects_combination(self):
        x, y = VariableRef("wl", "x"), VariableRef("wl", "y")
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                      [VariableSpec(x, "Entity")], start=0, end=10),
            self.make("e2", "r2", [RoleBinding("b", y, "m2", "Entity")],
                      [VariableSpec(y, "Entity")], start=10, end=20),
        ]
        report = TypedCandidateCoordinator().coordinate(rows)
        self.assertGreater(report.rejected_typed_sets, 0)
        self.assertFalse(any(len(x.coordinated.proposal_ids) == 2
                             for x in report.candidates))

    def test_conflicting_variable_declarations_reject_combination(self):
        x = VariableRef("wl", "x")
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "m", "Event")],
                      [VariableSpec(x, "Entity")],
                      constraints=UnificationConstraints(subtype_of=(("Event", "Entity"),))),
            self.make("e2", "r2", [RoleBinding("b", x, "m", "Event")],
                      [VariableSpec(x, "Event")]),
        ]
        report = TypedCandidateCoordinator().coordinate(rows)
        self.assertGreater(report.rejected_typed_sets, 0)

    def test_legacy_binding_mixing_is_rejected(self):
        x = VariableRef("wl", "x")
        row = self.make("e1", "r1", [RoleBinding("a", x, "m", "Entity")],
                        [VariableSpec(x, "Entity")])
        bad = TypedCandidateProposal(
            CandidateProposal("e1", "s0", "b1", (("x", "m"),)),
            row.hyperedge, row.variables,
        )
        with self.assertRaises(ValueError):
            TypedCandidateCoordinator().coordinate([bad])

    def test_parent_state_isolation_and_budget_status(self):
        x, y = VariableRef("wl", "x"), VariableRef("wl", "y")
        a = self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                      [VariableSpec(x, "Entity")])
        b = self.make("e2", "r2", [RoleBinding("b", y, "m2", "Entity")],
                      [VariableSpec(y, "Entity")])
        bad_edge = HyperedgeProposal("e2", "s1", "b1", "r2",
                                     b.hyperedge.roles, (), None, None)
        b = TypedCandidateProposal(
            CandidateProposal("e2", "s1", "b1", (), ()),
            bad_edge, b.variables,
        )
        report = TypedCandidateCoordinator().coordinate(
            [a, b], GlobalConstraints(max_states=1)
        )
        self.assertEqual(report.status, "BUDGET_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
