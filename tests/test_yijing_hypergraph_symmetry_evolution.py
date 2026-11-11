import unittest

from prototype.yijing_hypergraph_slot_group_induction import ExactSlotGroupObservation
from prototype.yijing_hypergraph_symmetry_evolution import (
    SymmetryEventStatus, SymmetryEventType, SymmetryEvolutionError,
    analyze_symmetry_evolution,
)


IDENTITY = ((0, 1, 2),)
C2 = ((0, 1, 2), (1, 0, 2))
S3 = (
    (0, 1, 2), (0, 2, 1), (1, 0, 2),
    (1, 2, 0), (2, 0, 1), (2, 1, 0),
)


def obs(evidence, step, group, *, context=(("phase", "steady"),), snapshot_context=(), domain="toy"):
    return ExactSlotGroupObservation(
        evidence, "joint", 3, ("a", "b", "c"), ("node", "node", "node"),
        context, (), None, None, "UNORDERED", group, step, domain, snapshot_context,
    )


class SymmetryEvolutionTests(unittest.TestCase):
    def test_persistent_symmetry_break_is_confirmed(self):
        report = analyze_symmetry_evolution([
            obs("s0", 0, S3), obs("s1", 1, C2), obs("s2", 2, C2),
        ])
        self.assertEqual(len(report.events), 1)
        event = report.events[0]
        self.assertEqual(event.event_type, SymmetryEventType.SYMMETRY_BREAK)
        self.assertEqual(event.status, SymmetryEventStatus.CONFIRMED)
        self.assertEqual(event.consecutive_target_snapshots, 2)

    def test_single_snapshot_change_remains_candidate(self):
        report = analyze_symmetry_evolution([
            obs("s0", 0, S3), obs("s1", 1, C2), obs("s2", 2, S3),
        ])
        self.assertEqual(report.events[0].status, SymmetryEventStatus.CANDIDATE)
        self.assertEqual(report.events[0].consecutive_target_snapshots, 1)

    def test_symmetry_expansion_is_detected(self):
        report = analyze_symmetry_evolution([
            obs("s0", 0, IDENTITY), obs("s1", 1, C2), obs("s2", 2, C2),
        ])
        self.assertEqual(report.events[0].event_type, SymmetryEventType.SYMMETRY_EXPAND)
        self.assertEqual(report.events[0].status, SymmetryEventStatus.CONFIRMED)

    def test_incomparable_groups_are_reconfigured(self):
        left = ((0, 1, 2), (1, 0, 2))
        right = ((0, 1, 2), (0, 2, 1))
        report = analyze_symmetry_evolution([
            obs("s0", 0, left), obs("s1", 1, right), obs("s2", 2, right),
        ])
        self.assertEqual(report.events[0].event_type, SymmetryEventType.RECONFIGURE)

    def test_context_shift_suppresses_structural_claim(self):
        report = analyze_symmetry_evolution([
            obs("s0", 0, S3),
            obs("s1", 1, IDENTITY, context=(("phase", "new"),)),
            obs("s2", 2, IDENTITY, context=(("phase", "new"),)),
        ])
        self.assertEqual(len(report.events), 1)
        self.assertEqual(report.events[0].event_type, SymmetryEventType.CONTEXT_SHIFT)
        self.assertEqual(report.events[0].status, SymmetryEventStatus.UNCERTAIN)
        self.assertTrue(report.events[0].context_changed)

    def test_global_snapshot_context_shift_suppresses_structural_claim(self):
        report = analyze_symmetry_evolution([
            obs("s0", 0, S3, snapshot_context=(("environment", "A"),)),
            obs("s1", 1, IDENTITY, snapshot_context=(("environment", "B"),)),
        ])
        self.assertEqual(report.events[0].event_type, SymmetryEventType.CONTEXT_SHIFT)
        self.assertTrue(report.events[0].context_changed)

    def test_domain_shift_is_not_misreported_as_symmetry_break(self):
        report = analyze_symmetry_evolution([
            obs("s0", 0, S3, domain="domain-a"),
            obs("s1", 1, IDENTITY, domain="domain-b"),
        ])
        self.assertEqual(report.events[0].event_type, SymmetryEventType.CONTEXT_SHIFT)
        self.assertTrue(report.events[0].domain_changed)

    def test_persistence_does_not_emit_change_event(self):
        report = analyze_symmetry_evolution([obs("s0", 0, C2), obs("s1", 1, C2)])
        self.assertEqual(report.events, ())
        self.assertEqual(report.transitions_seen, 1)

    def test_non_consecutive_step_numbers_are_allowed(self):
        report = analyze_symmetry_evolution([
            obs("s0", 2, S3), obs("s1", 7, C2), obs("s2", 12, C2),
        ])
        self.assertEqual(report.events[0].status, SymmetryEventStatus.CONFIRMED)

    def test_duplicate_steps_in_same_lineage_fail_closed(self):
        with self.assertRaises(SymmetryEvolutionError):
            analyze_symmetry_evolution([obs("s0", 1, S3), obs("s1", 1, C2)])

    def test_invalid_non_group_partition_is_rejected(self):
        invalid = ((0, 1, 2), (1, 0, 2), (0, 2, 1))
        with self.assertRaises(SymmetryEvolutionError):
            analyze_symmetry_evolution([obs("s0", 0, invalid)])

    def test_duplicate_evidence_id_is_rejected(self):
        with self.assertRaises(SymmetryEvolutionError):
            analyze_symmetry_evolution([obs("same", 0, S3), obs("same", 1, C2)])

    def test_group_validation_budget_fails_closed(self):
        with self.assertRaises(SymmetryEvolutionError):
            analyze_symmetry_evolution(
                [obs("s0", 0, S3)], max_group_validation_operations=35
            )

    def test_hysteresis_threshold_is_validated(self):
        with self.assertRaises(SymmetryEvolutionError):
            analyze_symmetry_evolution([obs("s0", 0, S3)], min_consecutive_target_snapshots=0)


if __name__ == "__main__":
    unittest.main()
