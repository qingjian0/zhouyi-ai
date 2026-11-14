import unittest
from dataclasses import replace

from prototype.dynamic_analogy import (
    ContextAtom,
    DynamicAnalogyCandidate,
    RelationAtom,
    StateSnapshot,
    StateTransition,
    TransitionSystem,
    assess_dynamic_analogy,
)


def systems(*, target_event="grow", extra_target_transition=False, unrelated_target_fact=False):
    source = TransitionSystem(
        "source", ("a", "b"),
        (
            StateSnapshot("s0", 0, (RelationAtom("a", "b", "supports"),)),
            StateSnapshot("s1", 1, (RelationAtom("a", "b", "supports"),)),
            StateSnapshot("s2", 2, (RelationAtom("a", "b", "supports"),)),
        ),
        (StateTransition("s0", "s1", "grow"), StateTransition("s1", "s2", "stabilize")),
    )
    target_edges = [
        StateTransition("t0", "t1", target_event),
        StateTransition("t1", "t2", "stabilize"),
    ]
    if extra_target_transition:
        target_edges.append(StateTransition("t0", "t2", "shortcut"))
    target_entities = ("x", "y", "z") if unrelated_target_fact else ("x", "y")
    extra = (RelationAtom("x", "z", "unrelated"),) if unrelated_target_fact else ()
    target = TransitionSystem(
        "target", target_entities,
        (
            StateSnapshot("t0", 0, (RelationAtom("x", "y", "supports"), *extra)),
            StateSnapshot("t1", 1, (RelationAtom("x", "y", "supports"), *extra)),
            StateSnapshot("t2", 2, (RelationAtom("x", "y", "supports"), *extra)),
        ), tuple(target_edges),
    )
    return DynamicAnalogyCandidate(
        "candidate-1", source, target, {"a": "x", "b": "y"},
        (("s0", "t0"), ("s1", "t1"), ("s2", "t2")),
        "three-step synthetic transition trace",
    )


class DynamicAnalogyTests(unittest.TestCase):
    def test_accepts_relation_and_transition_preserving_mapping(self):
        result = assess_dynamic_analogy(systems())
        self.assertTrue(result.accepted)
        self.assertEqual(result.state_f1, 1.0)
        self.assertEqual(result.transition_f1, 1.0)
        self.assertEqual(result.preserved_transitions, 2)


    def test_ignores_target_relations_outside_the_mapped_subgraph(self):
        result = assess_dynamic_analogy(systems(unrelated_target_fact=True))
        self.assertTrue(result.accepted)
        self.assertEqual(result.state_precision, 1.0)
        self.assertEqual(result.state_recall, 1.0)

    def test_rejects_static_match_when_event_transition_differs(self):
        result = assess_dynamic_analogy(systems(target_event="decay"))
        self.assertFalse(result.accepted)
        self.assertIn("DYNAMIC_TRANSITION_NOT_PRESERVED", result.reason_codes)
        self.assertEqual(result.state_f1, 1.0)
        self.assertLess(result.transition_recall, 1.0)

    def test_extra_target_transition_reduces_precision(self):
        result = assess_dynamic_analogy(systems(extra_target_transition=True))
        self.assertFalse(result.accepted)
        self.assertLess(result.transition_precision, 1.0)

    def test_rejects_temporally_reversed_alignment(self):
        candidate = systems()
        invalid = DynamicAnalogyCandidate(
            candidate.candidate_id, candidate.source, candidate.target,
            candidate.entity_mapping,
            (("s0", "t2"), ("s1", "t1"), ("s2", "t0")),
            candidate.validity_scope,
        )
        with self.assertRaisesRegex(ValueError, "temporal order"):
            assess_dynamic_analogy(invalid)

    def test_rejects_non_injective_entity_mapping(self):
        candidate = systems()
        invalid = DynamicAnalogyCandidate(
            candidate.candidate_id, candidate.source, candidate.target,
            {"a": "x", "b": "x"}, candidate.state_alignment, candidate.validity_scope,
        )
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            assess_dynamic_analogy(invalid)

    def test_requires_actual_transitions(self):
        candidate = systems()
        source = TransitionSystem(candidate.source.domain, candidate.source.entities,
                                  candidate.source.snapshots, ())
        invalid = DynamicAnalogyCandidate(
            candidate.candidate_id, source, candidate.target,
            candidate.entity_mapping, candidate.state_alignment, candidate.validity_scope,
        )
        result = assess_dynamic_analogy(invalid)
        self.assertFalse(result.accepted)
        self.assertIn("INSUFFICIENT_SOURCE_TRANSITIONS", result.reason_codes)

    def test_partial_entity_mapping_ignores_unmapped_target_subgraph(self):
        candidate = systems(unrelated_target_fact=True)
        source = TransitionSystem(
            "source", ("a", "b", "unmapped"),
            candidate.source.snapshots, candidate.source.transitions,
        )
        partial = DynamicAnalogyCandidate(
            candidate.candidate_id, source, candidate.target,
            candidate.entity_mapping, candidate.state_alignment, candidate.validity_scope,
        )
        result = assess_dynamic_analogy(partial, min_entity_coverage=2 / 3)
        self.assertTrue(result.accepted)
        self.assertAlmostEqual(result.mapped_entity_coverage, 2 / 3)
        self.assertEqual(result.observed_state_facts, 3)

    def test_preserves_explicit_time_position_and_potential_context(self):
        candidate = systems()
        source_states = tuple(
            replace(state, context=(
                ContextAtom("a", "position", "upper"),
                ContextAtom("a", "potential", "rising"),
                ContextAtom("", "time", "early"),
            ))
            for state in candidate.source.snapshots
        )
        target_states = tuple(
            replace(state, context=(
                ContextAtom("x", "position", "high"),
                ContextAtom("x", "potential", "increasing"),
                ContextAtom("", "time", "phase_1"),
            ))
            for state in candidate.target.snapshots
        )
        mapped = replace(
            candidate,
            source=replace(candidate.source, snapshots=source_states),
            target=replace(candidate.target, snapshots=target_states),
            context_value_mapping=(
                ("position", "upper", "high"),
                ("potential", "rising", "increasing"),
                ("time", "early", "phase_1"),
            ),
        )
        result = assess_dynamic_analogy(mapped)
        self.assertTrue(result.accepted)
        self.assertTrue(result.context_assessed)
        self.assertEqual(result.context_f1, 1.0)
        self.assertEqual(result.preserved_context_facts, 9)

    def test_rejects_context_mismatch_after_explicit_mapping(self):
        candidate = systems()
        source_states = tuple(
            replace(state, context=(ContextAtom("a", "potential", "rising"),))
            for state in candidate.source.snapshots
        )
        target_states = tuple(
            replace(state, context=(ContextAtom("x", "potential", "falling"),))
            for state in candidate.target.snapshots
        )
        mapped = replace(
            candidate,
            source=replace(candidate.source, snapshots=source_states),
            target=replace(candidate.target, snapshots=target_states),
        )
        result = assess_dynamic_analogy(mapped)
        self.assertFalse(result.accepted)
        self.assertIn("TIME_POSITION_POTENTIAL_CONTEXT_NOT_PRESERVED", result.reason_codes)
        self.assertEqual(result.context_f1, 0.0)

    def test_context_value_mapping_must_be_injective_per_dimension(self):
        candidate = systems()
        invalid = replace(
            candidate,
            context_value_mapping=(
                ("position", "upper", "high"),
                ("position", "lower", "high"),
            ),
        )
        with self.assertRaisesRegex(ValueError, "injective"):
            assess_dynamic_analogy(invalid)

    def test_rejects_non_finite_threshold(self):
        with self.assertRaises(ValueError):
            assess_dynamic_analogy(systems(), min_state_f1=float("nan"))

    def test_rejects_transition_that_moves_backward(self):
        candidate = systems()
        source = TransitionSystem(
            candidate.source.domain, candidate.source.entities,
            candidate.source.snapshots,
            (StateTransition("s1", "s0", "backward"),),
        )
        invalid = DynamicAnalogyCandidate(
            candidate.candidate_id, source, candidate.target,
            candidate.entity_mapping, candidate.state_alignment, candidate.validity_scope,
        )
        with self.assertRaisesRegex(ValueError, "strictly forward"):
            assess_dynamic_analogy(invalid)


if __name__ == "__main__":
    unittest.main()
