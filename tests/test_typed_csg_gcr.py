import unittest

from prototype.csg_gcr_coordinator import CandidateProposal, CoordinationError, GlobalConstraints
from prototype.csg_branch_delta import (
    BranchDelta, BranchMergeAuthorization, VerifiedBranchMergeAuthorization, BranchSnapshot, DeltaOperation,
    MergeStatus, canonical_hash,
)
from prototype.typed_csg_gcr import (
    TypedCandidateCoordinator, TypedCandidateProposal, _partial_typed_feasible,
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
        self.assertGreater(report.rejected_typed_sets + report.pruned_partial_sets, 0)
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
        self.assertGreater(report.rejected_typed_sets + report.pruned_partial_sets, 0)

    def test_partial_pruning_is_monotonic_for_small_exhaustive_subsets(self):
        x, y, z = (VariableRef("wl", name) for name in ("x", "y", "z"))
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                      [VariableSpec(x, "Entity")], start=0, end=5),
            self.make("e2", "r2", [RoleBinding("b", y, "m2", "Entity")],
                      [VariableSpec(y, "Entity")], start=5, end=10),
            self.make("e3", "r3", [RoleBinding("c", x, "m1", "Entity")],
                      [VariableSpec(x, "Event")]),
            self.make("e4", "r4", [RoleBinding("d", z, "m4", "Entity")],
                      [VariableSpec(z, "Entity")]),
        ]
        from itertools import combinations
        subsets = []
        for size in range(len(rows) + 1):
            subsets.extend(combinations(rows, size))
        for subset in subsets:
            if _partial_typed_feasible(tuple(subset)):
                continue
            subset_ids = {row.proposal.proposal_id for row in subset}
            for superset in subsets:
                superset_ids = {row.proposal.proposal_id for row in superset}
                if subset_ids.issubset(superset_ids):
                    self.assertFalse(
                        _partial_typed_feasible(tuple(superset)),
                        msg=f"pruned subset became feasible: {sorted(subset_ids)}",
                    )

    def test_pruned_and_unpruned_oracle_results_are_identical(self):
        x, y, z = (VariableRef("wl", name) for name in ("x", "y", "z"))
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                      [VariableSpec(x, "Entity")], start=0, end=5, score=4),
            self.make("e2", "r2", [RoleBinding("b", y, "m2", "Entity")],
                      [VariableSpec(y, "Entity")], start=5, end=10, score=3),
            self.make("e3", "r3", [RoleBinding("c", z, "m3", "Entity")],
                      [VariableSpec(z, "Entity")], score=2),
        ]
        limits = GlobalConstraints(max_states=500, result_limit=20)
        optimized = TypedCandidateCoordinator(enable_partial_pruning=True).coordinate(rows, limits)
        oracle = TypedCandidateCoordinator(enable_partial_pruning=False).coordinate(rows, limits)
        self.assertEqual(optimized.candidates, oracle.candidates)
        self.assertEqual(optimized.status, oracle.status)
        self.assertGreater(optimized.pruned_partial_sets, 0)
        self.assertLess(optimized.expanded_states, oracle.expanded_states)

    def branch_snapshot(self, branch, base, target, before, after):
        event = BranchDelta(
            f"{branch}-delta-1", DeltaOperation.UPDATE_ATTRIBUTE, target,
            canonical_hash(before), after, (f"derivation:{branch}",), None, 1,
        )
        return BranchSnapshot(
            "s0", canonical_hash(base), branch, 0, (event,), (),
            (target,), (f"derivation:{branch}",), ("root", branch),
        )

    def test_verified_authorization_capability_cannot_be_constructed_directly(self):
        with self.assertRaisesRegex(TypeError, "must come from the E09 verifier"):
            VerifiedBranchMergeAuthorization(
                "fake", "s0", ("left", "right"), ("fake-evidence",),
                "issuer", "a" * 64, "fake-keyring",
            )

    def test_unverified_scope_receipt_is_rejected(self):
        base = {"node:a": {"value": 0}, "node:b": {"value": 0}}
        x, y = VariableRef("wl", "x"), VariableRef("wl", "y")
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                      [VariableSpec(x, "Entity")], branch="left"),
            self.make("e2", "r2", [RoleBinding("b", y, "m2", "Entity")],
                      [VariableSpec(y, "Entity")], branch="right"),
        ]
        snapshots = (
            self.branch_snapshot("left", base, "node:a", base["node:a"], {"value": 1}),
            self.branch_snapshot("right", base, "node:b", base["node:b"], {"value": 2}),
        )
        unverified = BranchMergeAuthorization(
            "forged-ref", "s0", ("left", "right"), ("e09:fake-evidence",),
        )
        with self.assertRaisesRegex(CoordinationError, "signature-verified"):
            TypedCandidateCoordinator().coordinate(
                rows, base_state=base, branch_snapshots=snapshots,
                branch_merge_authorization=unverified,
            )

    def test_cross_branch_merge_requires_explicit_authorization(self):
        base = {"node:a": {"value": 0}, "node:b": {"value": 0}}
        x, y = VariableRef("wl", "x"), VariableRef("wl", "y")
        rows = [
            self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                      [VariableSpec(x, "Entity")], branch="left"),
            self.make("e2", "r2", [RoleBinding("b", y, "m2", "Entity")],
                      [VariableSpec(y, "Entity")], branch="right"),
        ]
        snapshots = (
            self.branch_snapshot("left", base, "node:a", base["node:a"], {"value": 1}),
            self.branch_snapshot("right", base, "node:b", base["node:b"], {"value": 2}),
        )
        with self.assertRaises(CoordinationError):
            TypedCandidateCoordinator().coordinate(
                rows, base_state=base, branch_snapshots=snapshots,
            )

    def test_branch_snapshot_parent_digest_must_match_base(self):
        base = {"node:a": {"value": 0}}
        x = VariableRef("wl", "x")
        row = self.make("e1", "r1", [RoleBinding("a", x, "m1", "Entity")],
                        [VariableSpec(x, "Entity")], branch="left")
        wrong = {"node:a": {"value": 99}}
        snapshot = self.branch_snapshot(
            "left", wrong, "node:a", wrong["node:a"], {"value": 1},
        )
        with self.assertRaises(CoordinationError):
            TypedCandidateCoordinator().coordinate(
                [row], base_state=base, branch_snapshots=(snapshot,),
            )

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
