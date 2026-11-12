import unittest

from prototype.csg_gcr_coordinator import (
    CandidateCoordinator,
    CandidateProposal,
    CoordinationError,
    GlobalConstraints,
)


class CandidateCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = CandidateCoordinator()

    def proposal(self, proposal_id, *, parent="state-1", branch="b1",
                 bindings=(), evidence=(), score=1.0, cost=1,
                 requires=(), excludes=()):
        return CandidateProposal(
            proposal_id=proposal_id,
            parent_state_ref=parent,
            branch_id=branch,
            bindings=tuple(bindings),
            evidence_refs=tuple(evidence),
            score=score,
            cost=cost,
            requires=tuple(requires),
            excludes=tuple(excludes),
        )

    def test_combines_compatible_proposals_across_branches(self):
        report = self.coordinator.coordinate([
            self.proposal("p1", branch="left", bindings=(("cause", "rain"),),
                          evidence=("ev-1",), score=2),
            self.proposal("p2", branch="right", bindings=(("effect", "wet"),),
                          evidence=("ev-2",), score=3),
        ])
        self.assertEqual(report.status, "COMPLETE")
        best = report.candidates[0]
        self.assertEqual(best.proposal_ids, ("p1", "p2"))
        self.assertEqual(best.branch_ids, ("left", "right"))
        self.assertEqual(best.bindings, (("cause", "rain"), ("effect", "wet")))
        self.assertEqual(best.evidence_refs, ("ev-1", "ev-2"))
        self.assertEqual(best.score, 5)

    def test_conflicting_bindings_cannot_be_combined(self):
        report = self.coordinator.coordinate([
            self.proposal("p1", bindings=(("state", "open"),), score=5),
            self.proposal("p2", branch="b2", bindings=(("state", "closed"),), score=4),
        ])
        self.assertTrue(all(len(item.proposal_ids) == 1 for item in report.candidates))
        self.assertGreater(report.rejected_conflicts, 0)

    def test_different_parent_states_are_not_mixed(self):
        report = self.coordinator.coordinate([
            self.proposal("p1", parent="state-A", bindings=(("x", "1"),)),
            self.proposal("p2", parent="state-B", bindings=(("y", "2"),)),
        ])
        self.assertTrue(all(len(item.proposal_ids) == 1 for item in report.candidates))

    def test_explicit_exclusion_is_symmetric(self):
        report = self.coordinator.coordinate([
            self.proposal("p1", excludes=("p2",), score=4),
            self.proposal("p2", score=3),
        ])
        self.assertFalse(any(set(item.proposal_ids) == {"p1", "p2"}
                             for item in report.candidates))

    def test_required_binding_filters_candidate_sets(self):
        report = self.coordinator.coordinate(
            [self.proposal("p1", bindings=(("x", "1"),)),
             self.proposal("p2", bindings=(("y", "2"),))],
            GlobalConstraints(required_bindings=(("x", "1"),)),
        )
        self.assertTrue(report.candidates)
        self.assertTrue(all(("x", "1") in item.bindings
                            for item in report.candidates))

    def test_forbidden_binding_rejects_candidate_set(self):
        report = self.coordinator.coordinate(
            [self.proposal("p1", bindings=(("status", "unsafe"),)),
             self.proposal("p2", bindings=(("status", "safe"),), score=2)],
            GlobalConstraints(forbidden_bindings=(("status", "unsafe"),)),
        )
        self.assertTrue(report.candidates)
        self.assertTrue(all(("status", "unsafe") not in item.bindings
                            for item in report.candidates))

    def test_dependency_must_be_selected(self):
        report = self.coordinator.coordinate([
            self.proposal("dependent", requires=("base",), score=10),
            self.proposal("base", bindings=(("base", "yes"),), score=1),
        ])
        self.assertTrue(report.candidates)
        self.assertTrue(all(
            ("dependent" not in item.proposal_ids) or
            ("base" in item.proposal_ids)
            for item in report.candidates
        ))

    def test_cost_and_cardinality_are_hard_limits(self):
        report = self.coordinator.coordinate(
            [self.proposal("p1", score=5, cost=4),
             self.proposal("p2", score=4, cost=4),
             self.proposal("p3", score=3, cost=1)],
            GlobalConstraints(max_selected=2, max_cost=5),
        )
        self.assertTrue(report.candidates)
        self.assertTrue(all(len(item.proposal_ids) <= 2 and item.cost <= 5
                            for item in report.candidates))

    def test_budget_exhaustion_is_explicit(self):
        report = self.coordinator.coordinate(
            [self.proposal(f"p{i}", score=float(10 - i)) for i in range(8)],
            GlobalConstraints(max_states=2),
        )
        self.assertEqual(report.status, "BUDGET_EXHAUSTED")
        self.assertEqual(report.expanded_states, 2)

    def test_input_order_does_not_change_ranking(self):
        rows = [
            self.proposal("p1", bindings=(("x", "1"),), score=2),
            self.proposal("p2", bindings=(("y", "2"),), score=3),
            self.proposal("p3", bindings=(("x", "3"),), score=2),
        ]
        first = self.coordinator.coordinate(rows)
        second = self.coordinator.coordinate(reversed(rows))
        self.assertEqual(first.candidates, second.candidates)

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaises(CoordinationError):
            self.coordinator.coordinate([
                self.proposal("p1", requires=("missing",))
            ])

    def test_invalid_score_and_cost_are_rejected(self):
        with self.assertRaises(CoordinationError):
            self.coordinator.coordinate([
                self.proposal("p1", score=float("nan"))
            ])
        with self.assertRaises(CoordinationError):
            self.coordinator.coordinate([
                self.proposal("p1", cost=True)
            ])

    def test_monotonic_partial_feasibility_prunes_prefixes(self):
        rows = [
            self.proposal("p1", bindings=(("x", "2"),), score=4),
            self.proposal("p2", bindings=(("y", "3"),), score=3),
            self.proposal("p3", bindings=(("x", "1"),), score=2),
        ]
        limits = GlobalConstraints(required_bindings=(("x", "1"),),
                                   max_states=100, result_limit=100)
        baseline = self.coordinator.coordinate(rows, limits)
        pruned = self.coordinator.coordinate(
            rows, limits,
            partial_feasibility=lambda selected: all(
                dict(item.bindings).get("x", "1") == "1" for item in selected
            ),
        )
        self.assertGreater(pruned.pruned_partial_sets, 0)
        self.assertEqual(pruned.candidates, baseline.candidates)
        self.assertEqual(pruned.status, baseline.status)
        self.assertLess(pruned.expanded_states, baseline.expanded_states)

    def test_partial_feasibility_must_return_bool(self):
        with self.assertRaises(CoordinationError):
            self.coordinator.coordinate(
                [self.proposal("p1")],
                partial_feasibility=lambda selected: "yes",
            )

    def test_empty_input_returns_no_feasible_set(self):
        report = self.coordinator.coordinate([])
        self.assertEqual(report.status, "NO_FEASIBLE_SET")
        self.assertEqual(report.candidates, ())

    def test_combined_score_overflow_is_rejected(self):
        with self.assertRaises(CoordinationError):
            self.coordinator.coordinate([
                self.proposal("p1", score=1e308),
                self.proposal("p2", score=1e308),
            ])


if __name__ == "__main__":
    unittest.main()
