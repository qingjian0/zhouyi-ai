import unittest

from prototype.classiang_engine import (
    ClassExample, FeatureAtom, FeatureCandidate, Observation,
    induce_class, select_aspects,
)
from prototype.classiang_native import EvidenceRef
from prototype.classiang_native_adapter import observation_to_symbol_graph


def make_observation(name, atoms, *, contradictions=()):
    evidence = (f"evidence:{name}",)
    features = tuple(
        FeatureCandidate(
            feature_id=f"{name}:{index}",
            atom=atom,
            evidence_refs=evidence,
            purpose_scores=(("recognition", 0.9),),
        )
        for index, atom in enumerate(atoms)
    )
    return Observation(
        name, f"subject:{name}", "test-domain", evidence, features,
        explicit_contradictions=tuple(contradictions),
    )


def reviewed(evidence_id, family):
    return EvidenceRef(
        evidence_id, f"source:{family}", family, "section:1",
        "CC-BY-4.0", True,
    )


class NativeAdapterTests(unittest.TestCase):
    def test_observation_and_induced_class_keep_evidence_lineage(self):
        shared = FeatureAtom("function", "transfers-load")
        positives = tuple(
            ClassExample(
                item := make_observation(name, (shared, FeatureAtom("attribute", value))),
                "recognition",
                select_aspects(item, purpose="recognition").selected,
            )
            for name, value in (("positive-a", "metal"), ("positive-b", "wood"))
        )
        negative_item = make_observation("negative", (FeatureAtom("attribute", "plastic"),))
        negative = ClassExample(
            negative_item, "recognition",
            select_aspects(negative_item, purpose="recognition").selected,
        )
        hypothesis = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=positives, negative_examples=(negative,),
            validity_scope="fixture-only",
        ).hypothesis
        target = make_observation("target", (shared,))
        ids = (
            "evidence:positive-a", "evidence:positive-b",
            "evidence:negative", "evidence:target",
        )
        catalog = {
            evidence_id: reviewed(evidence_id, evidence_id)
            for evidence_id in ids
        }
        graph = observation_to_symbol_graph(
            target, catalog, hypothesis=hypothesis,
        )
        graph.validate()
        self.assertEqual(
            {item.evidence_id for item in graph.evidence}, set(ids),
        )
        self.assertIn("has_aspect", {item.relation_type for item in graph.relations})
        self.assertIn(
            "class_requires_aspect",
            {item.relation_type for item in graph.relations},
        )
        self.assertIn(
            "class_excludes_boundary",
            {item.relation_type for item in graph.relations},
        )

    def test_contradictions_require_explicit_provenance(self):
        contradiction = FeatureAtom("function", "does-not-transfer")
        item = make_observation("target", (), contradictions=(contradiction,))
        catalog = {
            "evidence:target": reviewed("evidence:target", "target-family"),
        }
        with self.assertRaisesRegex(ValueError, "contradiction_evidence"):
            observation_to_symbol_graph(item, catalog)
        graph = observation_to_symbol_graph(
            item, catalog,
            contradiction_evidence={contradiction: ("evidence:target",)},
        )
        self.assertIn(
            "contradicts_aspect",
            {relation.relation_type for relation in graph.relations},
        )

    def test_missing_or_unreviewed_evidence_is_rejected(self):
        item = make_observation("target", (FeatureAtom("attribute", "red"),))
        with self.assertRaisesRegex(ValueError, "missing IDs"):
            observation_to_symbol_graph(item, {})
        catalog = {
            "evidence:target": EvidenceRef(
                "evidence:target", "source", "family", "p.1", "CC-BY-4.0", False,
            ),
        }
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            observation_to_symbol_graph(item, catalog)


if __name__ == "__main__":
    unittest.main()
