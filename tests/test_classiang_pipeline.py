import unittest

from prototype.analogy import AnalogyCandidate, Evidence, Relation
from prototype.classiang_engine import (
    ClassExample, FeatureAtom, FeatureCandidate, Observation, select_aspects,
)
from prototype.classiang_pipeline import (
    ClassiangCycleRequest, RevisionRequest, run_classiang_cycle,
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
        self.positive = (
            make_example("p1", (self.feature,)),
            make_example("p2", (self.feature,)),
        )
        self.negative = (
            make_example("n1", (FeatureAtom("attribute", "blue"),)),
        )

    def request(self, **overrides):
        values = dict(
            class_id="load-transfer",
            purpose="recognition",
            validity_scope="fixture-only",
            query_observation=make_observation("query", (self.feature,)),
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

    def test_relation_mismatch_blocks_transfer(self):
        bad = valid_analogy()
        bad = AnalogyCandidate(
            **{**bad.__dict__, "target_relations": (Relation("x", "y", "contains"),)}
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
        self.assertEqual(initial.version, 1)


if __name__ == "__main__":
    unittest.main()
