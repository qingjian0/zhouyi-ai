import unittest
from dataclasses import replace

from prototype.analogy import AnalogyCandidate, Evidence, Relation
from prototype.dynamic_analogy import (
    DynamicAnalogyCandidate, RelationAtom, StateSnapshot, StateTransition, TransitionSystem,
)
from prototype.classiang_engine import (
    ClassExample, FeatureAtom, FeatureCandidate, Observation, select_aspects,
)
from prototype.classiang_pipeline import (
    AnalogyDiscoveryRequest, ClassiangCycleRequest, RevisionRequest, run_classiang_cycle,
)


def make_observation(name, atoms):
    refs = (f"source:{name}",)
    features = tuple(
        FeatureCandidate(
            feature_id=f"{name}:{index}",
            atom=atom,
            evidence_refs=refs,
            purpose_scores=(("recognition", 0.9),),
        )
        for index, atom in enumerate(atoms)
    )
    return Observation(name, f"subject:{name}", "test-domain", refs, features)


def make_example(name, atoms):
    observation = make_observation(name, atoms)
    return ClassExample(
        observation, "recognition",
        select_aspects(observation, purpose="recognition").selected,
    )


def valid_analogy():
    return AnalogyCandidate(
        candidate_id="mapping-1",
        source_domain="mechanics",
        target_domain="biology",
        source_entities=("a", "b"),
        target_entities=("x", "y"),
        mapping={"a": "x", "b": "y"},
        dimensions=("relation", "function"),
        source_relations=(Relation("a", "b", "transfers-load"),),
        target_relations=(Relation("x", "y", "transfers-load"),),
        conditions=("same directed relation predicate",),
        evidence=(Evidence("source:analogy", True),),
        validity_scope="the two supplied finite graphs",
    )


class ClassiangPipelineTests(unittest.TestCase):
    def setUp(self):
        self.feature = FeatureAtom("function", "transfers-load")
        self.feature2 = FeatureAtom("process", "cyclic")
        self.positive = (
            make_example("p1", (self.feature, self.feature2)),
            make_example("p2", (self.feature, self.feature2)),
        )
        self.negative = (
            make_example("n1", (FeatureAtom("attribute", "blue"),)),
        )

    def request(self, **overrides):
        values = dict(
            class_id="load-transfer",
            purpose="recognition",
            validity_scope="fixture-only",
            query_observation=make_observation("query", (self.feature, self.feature2)),
            positive_examples=self.positive,
            negative_examples=self.negative,
            analogy_candidate=valid_analogy(),
        )
        values.update(overrides)
        return ClassiangCycleRequest(**values)

    def test_runs_discriminative_class_and_transfer_gates(self):
        result = run_classiang_cycle(self.request())
        self.assertEqual(result.induction.status.value, "discriminative")
        self.assertEqual(result.membership.decision.value, "accept_provisional")
        self.assertTrue(result.analogy_assessment.accepted)
        self.assertTrue(result.transfer_gate_passed)
        self.assertIn(
            "STRUCTURAL_TRANSFER_GATES_PASSED_NOT_SEMANTIC_PROOF",
            result.reason_codes,
        )

    def test_no_negative_boundary_fails_closed(self):
        result = run_classiang_cycle(self.request(negative_examples=()))
        self.assertFalse(result.transfer_gate_passed)
        self.assertIn("CLASS_BOUNDARY_NOT_DISCRIMINATIVE", result.reason_codes)

    def test_missing_transfer_candidate_fails_closed(self):
        result = run_classiang_cycle(self.request(analogy_candidate=None))
        self.assertFalse(result.transfer_gate_passed)
        self.assertIn("NO_TRANSFER_CANDIDATE_EVALUATED", result.reason_codes)

    def test_bounded_mapping_discovery_can_supply_transfer_candidate(self):
        search = AnalogyDiscoveryRequest(
            source_domain="mechanics",
            target_domain="biology",
            source_entities=("a", "b"),
            target_entities=("x", "y"),
            source_relations=(Relation("a", "b", "transfers-load"),),
            target_relations=(Relation("x", "y", "transfers-load"),),
            dimensions=("relation", "function"),
            conditions=("same directed relation predicate",),
            evidence=(Evidence("source:analogy", True),),
            validity_scope="two finite fixture graphs",
            max_evaluations=4,
            max_results=4,
        )
        result = run_classiang_cycle(
            self.request(analogy_candidate=None, analogy_discovery=search)
        )
        self.assertIsNotNone(result.analogy_discovery)
        self.assertTrue(any(item.assessment.accepted
                            for item in result.analogy_discovery.candidates))
        self.assertTrue(result.transfer_gate_passed)

    def test_dynamic_transition_mapping_is_integrated(self):
        source = TransitionSystem(
            domain="mechanics",
            entities=("a", "b"),
            snapshots=(
                StateSnapshot("s0", 0, (RelationAtom("a", "b", "supports"),)),
                StateSnapshot("s1", 1, (RelationAtom("a", "b", "supports"),)),
            ),
            transitions=(StateTransition("s0", "s1", "advance"),),
        )
        target = TransitionSystem(
            domain="biology",
            entities=("x", "y"),
            snapshots=(
                StateSnapshot("t0", 0, (RelationAtom("x", "y", "supports"),)),
                StateSnapshot("t1", 1, (RelationAtom("x", "y", "supports"),)),
            ),
            transitions=(StateTransition("t0", "t1", "advance"),),
        )
        dynamic = DynamicAnalogyCandidate(
            candidate_id="dynamic-1",
            source=source,
            target=target,
            entity_mapping={"a": "x", "b": "y"},
            state_alignment=(("s0", "t0"), ("s1", "t1")),
            validity_scope="two finite transition systems",
        )
        result = run_classiang_cycle(
            self.request(analogy_candidate=None, dynamic_analogy_candidate=dynamic)
        )
        self.assertTrue(result.dynamic_analogy_assessment.accepted)
        self.assertTrue(result.transfer_gate_passed)

    def test_relation_mismatch_blocks_transfer(self):
        bad = replace(
            valid_analogy(),
            target_relations=(Relation("x", "y", "contains"),),
        )
        result = run_classiang_cycle(self.request(analogy_candidate=bad))
        self.assertFalse(result.transfer_gate_passed)
        self.assertIn("TRANSFER_STRUCTURE_OR_EVIDENCE_GATE_FAILED", result.reason_codes)

    def test_optional_revision_is_composed_without_silent_installation(self):
        initial_request = self.request(analogy_candidate=None)
        initial = run_classiang_cycle(initial_request).induction.hypothesis
        counterexample = make_example(
            "ce-1", (self.feature, FeatureAtom("attribute", "metal"))
        )
        revision = RevisionRequest(
            hypothesis=initial,
            positive_examples=self.positive,
            negative_examples=self.negative,
            counterexample=counterexample,
        )
        result = run_classiang_cycle(self.request(revision=revision))
        self.assertIsNotNone(result.revision)
        self.assertEqual(result.revision.active_hypothesis.version, 2)
        self.assertEqual(result.revision.removed_required_features, (self.feature,))
        self.assertEqual(initial.version, 1)


if __name__ == "__main__":
    unittest.main()
