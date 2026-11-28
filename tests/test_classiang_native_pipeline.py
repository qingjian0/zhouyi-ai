import unittest

from prototype.classiang_engine import (
    ClassExample, FeatureAtom, FeatureCandidate, Observation, select_aspects,
)
from prototype.classiang_native import EvidenceRef
from prototype.classiang_native_pipeline import run_native_classiang_cycle
from prototype.classiang_pipeline import ClassiangCycleRequest


def observation(name, atoms):
    evidence = (f"evidence:{name}",)
    features = tuple(
        FeatureCandidate(
            f"{name}:{index}", atom, evidence,
            (("recognition", 0.9),),
        )
        for index, atom in enumerate(atoms)
    )
    return Observation(name, f"subject:{name}", "mechanics", evidence, features)


def example(name, atoms):
    item = observation(name, atoms)
    return ClassExample(
        item, "recognition",
        select_aspects(item, purpose="recognition").selected,
    )


def catalog_for(*names):
    result = {}
    for name in names:
        evidence_id = f"evidence:{name}"
        result[evidence_id] = EvidenceRef(
            evidence_id, f"source:{name}", f"family:{name}",
            "section:1", "CC-BY-4.0", True,
        )
    return result


class NativeClassiangPipelineTests(unittest.TestCase):
    def test_cognition_cycle_projects_into_composable_native_graph(self):
        common = FeatureAtom("function", "transfers-load")
        extra_a = FeatureAtom("attribute", "metal")
        extra_b = FeatureAtom("attribute", "wood")
        query = observation("query", (common, extra_a))
        request = ClassiangCycleRequest(
            class_id="load-transfer",
            purpose="recognition",
            validity_scope="fixture-only",
            query_observation=query,
            positive_examples=(
                example("positive-a", (common, extra_a)),
                example("positive-b", (common, extra_b)),
            ),
            negative_examples=(example("negative", (extra_a,)),),
        )
        result = run_native_classiang_cycle(
            request,
            catalog_for("query", "positive-a", "positive-b", "negative"),
            max_depth=2,
            max_candidates=50,
        )
        self.assertIsNotNone(result.cognition.induction.hypothesis)
        self.assertEqual(result.cognition.membership.decision.value, "accept_provisional")
        self.assertGreaterEqual(len(result.graph.symbols), 4)
        self.assertTrue(result.compositions.candidates)
        self.assertEqual(result.ranked_compositions, ())
        self.assertTrue(all(
            candidate.evidence_ids
            for candidate in result.compositions.candidates
        ))

    def test_native_pipeline_fails_closed_on_missing_hypothesis_evidence(self):
        common = FeatureAtom("function", "transfers-load")
        query = observation("query", (common,))
        request = ClassiangCycleRequest(
            class_id="load-transfer",
            purpose="recognition",
            validity_scope="fixture-only",
            query_observation=query,
            positive_examples=(
                example("positive-a", (common,)),
                example("positive-b", (common,)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "missing IDs"):
            run_native_classiang_cycle(
                request, catalog_for("query"),
            )


if __name__ == "__main__":
    unittest.main()
