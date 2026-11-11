import unittest

from prototype.yijing_operator_induction import Node, Relation, RelationalState
from prototype.yijing_dynamic_role_evolution import (
    DynamicRoleEvolution, EpisodeSnapshot, RoleEventType, RoleEvolutionError,
)


def state(step=0, *, split=False, context="steady", prefix="e"):
    if split:
        nodes = (
            Node(prefix + "1", "agent", "ignored-a"),
            Node(prefix + "2", "agent", "ignored-b"),
            Node(prefix + "3", "resource", "ignored-c"),
        )
        edges = (
            Relation(prefix + "1", prefix + "3", "uses"),
            Relation(prefix + "2", prefix + "3", "avoids"),
        )
    else:
        nodes = (
            Node(prefix + "1", "agent", "ignored-a"),
            Node(prefix + "2", "agent", "ignored-b"),
            Node(prefix + "3", "resource", "ignored-c"),
        )
        edges = (
            Relation(prefix + "1", prefix + "3", "uses"),
            Relation(prefix + "2", prefix + "3", "uses"),
        )
    return RelationalState(tuple(nodes), tuple(sorted(edges)), (("phase", context),))


def snap(step, graph, *, complete=False, episode="ep", evidence=None):
    return EpisodeSnapshot(
        episode, step, graph, evidence or f"ev-{step}", "toy-domain",
        coverage_complete=complete,
    )


class DynamicRoleEvolutionTests(unittest.TestCase):
    def test_stable_roles_persist_across_snapshots(self):
        report = DynamicRoleEvolution().analyze([snap(0, state()), snap(1, state(1))])
        self.assertTrue(any(e.event_type == RoleEventType.PERSIST for e in report.events))

    def test_topology_change_produces_role_evolution_candidates(self):
        report = DynamicRoleEvolution().analyze([
            snap(0, state()), snap(1, state(1, split=True))
        ])
        self.assertTrue(report.events)

    def test_entity_renaming_preserves_event_types(self):
        a = DynamicRoleEvolution().analyze([snap(0, state(prefix="a")), snap(1, state(1, split=True, prefix="a"))])
        b = DynamicRoleEvolution().analyze([snap(0, state(prefix="z")), snap(1, state(1, split=True, prefix="z"))])
        self.assertEqual(
            sorted(e.event_type.value for e in a.events),
            sorted(e.event_type.value for e in b.events),
        )

    def test_incomplete_absence_never_claims_dissolution(self):
        before = state()
        after = RelationalState((), (), ())
        report = DynamicRoleEvolution().analyze([snap(0, before), snap(1, after)])
        self.assertFalse(any(e.event_type == RoleEventType.DISSOLVE for e in report.events))
        self.assertGreater(report.incomplete_absence_checks, 0)

    def test_complete_absence_can_propose_dissolution(self):
        report = DynamicRoleEvolution().analyze([
            snap(0, state()), snap(1, RelationalState((), (), ()), complete=True)
        ])
        self.assertTrue(any(e.event_type == RoleEventType.DISSOLVE for e in report.events))

    def test_context_change_is_annotation_not_forced_split(self):
        report = DynamicRoleEvolution().analyze([
            snap(0, state(context="growth")), snap(1, state(1, context="decline"))
        ])
        persists = [e for e in report.events if e.event_type == RoleEventType.PERSIST]
        self.assertTrue(persists)
        self.assertTrue(all(e.context_changed for e in persists))

    def test_low_overlap_does_not_force_dissolution(self):
        report = DynamicRoleEvolution(min_shared_entities=2).analyze([
            snap(0, state()), snap(1, state(1, prefix="new"))
        ])
        self.assertFalse(any(e.event_type == RoleEventType.DISSOLVE for e in report.events))

    def test_min_confidence_suppresses_weak_lineage(self):
        report = DynamicRoleEvolution(min_confidence=1.0).analyze([
            snap(0, state()), snap(1, state(1, split=True))
        ])
        self.assertTrue(all(e.confidence == 1.0 for e in report.events))

    def test_duplicate_evidence_is_rejected(self):
        with self.assertRaises(RoleEvolutionError):
            DynamicRoleEvolution().analyze([
                snap(0, state(), evidence="same"),
                snap(1, state(1), evidence="same"),
            ])

    def test_non_monotonic_steps_are_rejected(self):
        with self.assertRaises(RoleEvolutionError):
            DynamicRoleEvolution().analyze([snap(1, state()), snap(0, state(1))])

    def test_event_budget_is_reported(self):
        report = DynamicRoleEvolution(max_events=1).analyze([
            snap(0, state()), snap(1, state(1, split=True))
        ])
        if len(report.events) >= 1:
            self.assertLessEqual(len(report.events), 1)


if __name__ == "__main__":
    unittest.main()
