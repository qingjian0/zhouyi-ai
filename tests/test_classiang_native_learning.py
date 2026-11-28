import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from prototype.classiang_native import EvidenceRef, Relation, Symbol, SymbolGraph
from prototype.classiang_native_learning import (
    CompositionLabel, NativeCompositionScorer, NativeRoleBindingModel, _features, graph_from_json, train_and_evaluate, train_and_evaluate_role_model,
)


def training_fixture():
    evidence = []
    symbols = [Symbol("hub", "domain", "node", (("role", "hub"),), ("e0-a",))]
    relations = []
    labels = []
    for i in range(4):
        family = f"family-{i}"
        e_left, e_right = f"e{i}-a", f"e{i}-b"
        evidence.extend((
            EvidenceRef(e_left, f"source-{i}", family, "p.1", "CC-BY-4.0", True),
            EvidenceRef(e_right, f"source-{i}", family, "p.2", "CC-BY-4.0", True),
        ))
        left_symbol, right_symbol = f"node-{i}-a", f"node-{i}-b"
        symbols.extend((
            Symbol(left_symbol, "domain", "node", (("index", str(i)),), (e_left,)),
            Symbol(right_symbol, "domain", "node", (("index", str(i + 1)),), (e_right,)),
        ))
        r_left, r_right = f"r{i}-a", f"r{i}-b"
        relations.extend((
            Relation(r_left, "connects", (("source", "hub"), ("target", left_symbol)), (e_left,)),
            Relation(r_right, "connects", (("source", "hub"), ("target", right_symbol)), (e_right,)),
        ))
        for label, suffix in ((1, "positive"), (0, "negative")):
            labels.append(CompositionLabel(
                example_id=f"{family}-{suffix}",
                group_id=family,
                source_family=family,
                relation_ids=(r_left, r_right),
                evidence_ids=(e_left, e_right),
                label=label,
                reviewed=True,
            ))
    return SymbolGraph(tuple(evidence), tuple(symbols), tuple(relations)), tuple(labels)


class NativeCompositionLearningTests(unittest.TestCase):
    def test_trains_and_keeps_source_families_disjoint(self):
        graph, labels = training_fixture()
        model, report = train_and_evaluate(graph, labels, seed=11, epochs=10)
        self.assertEqual(model.trained_examples, report["train_examples"])
        self.assertTrue(report["source_family_disjoint"])
        self.assertFalse(set(report["train_source_families"]) & set(report["validation_source_families"]))
        self.assertEqual(report["validation_examples"], 2)
        self.assertEqual(len(model.weights), 5)

    def test_checkpoint_round_trip(self):
        graph, labels = training_fixture()
        model, _ = train_and_evaluate(graph, labels, seed=5, epochs=5)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            digest = model.save(path)
            restored = NativeCompositionScorer.load(path)
            self.assertEqual(len(digest), 64)
            self.assertEqual(restored.to_dict(), model.to_dict())

    def test_graph_json_loader_round_trip(self):
        graph, _ = training_fixture()
        payload = {
            "schema_version": 1,
            "evidence": [asdict(item) for item in graph.evidence],
            "symbols": [asdict(item) for item in graph.symbols],
            "relations": [asdict(item) for item in graph.relations],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            restored = graph_from_json(path)
        self.assertEqual(restored, graph)

    def test_native_role_binding_model_trains_and_round_trips(self):
        graph, labels = training_fixture()
        model, report = train_and_evaluate_role_model(
            graph, labels, seed=11, dimension=8, epochs=20,
        )
        self.assertEqual(model.trained_examples, report["train_examples"])
        self.assertTrue(report["source_family_disjoint"])
        self.assertEqual(model.dimension, 8)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "role-model.json"
            digest = model.save(path)
            restored = NativeRoleBindingModel.load(path)
            self.assertEqual(len(digest), 64)
            self.assertEqual(restored.to_dict(), model.to_dict())

    def test_role_binding_rejects_unknown_relation_type(self):
        graph, labels = training_fixture()
        model = NativeRoleBindingModel.initialize(graph, labels[:2], dimension=8)
        with self.assertRaisesRegex(ValueError, "unknown relation ID"):
            model.predict_probability(graph, ("missing-relation",))

    def test_rejects_unreviewed_labels(self):
        graph, labels = training_fixture()
        bad = list(labels)
        bad[0] = CompositionLabel(
            example_id=bad[0].example_id, group_id=bad[0].group_id,
            source_family=bad[0].source_family, relation_ids=bad[0].relation_ids,
            evidence_ids=bad[0].evidence_ids, label=bad[0].label, reviewed=False,
        )
        with self.assertRaisesRegex(ValueError, "reviewed"):
            train_and_evaluate(graph, tuple(bad))

    def test_rejects_source_family_leakage(self):
        graph, labels = training_fixture()
        first = labels[0]
        leaked = CompositionLabel(
            example_id="cross-family-copy", group_id="family-1",
            source_family="family-1", relation_ids=first.relation_ids,
            evidence_ids=first.evidence_ids, label=0, reviewed=True,
        )
        with self.assertRaisesRegex(ValueError, "source_family"):
            train_and_evaluate(graph, labels + (leaked,))

    def test_rejects_single_class_training_partition(self):
        scorer = NativeCompositionScorer.initialize()
        with self.assertRaisesRegex(ValueError, "both positive and negative"):
            scorer.fit([((1.0, 0.0, 1.0, 0.0, 0.5), 1)] * 3)

    def test_feature_vector_is_finite_and_structural(self):
        graph, labels = training_fixture()
        values = _features(graph, labels[0].relation_ids)
        self.assertEqual(len(values), 5)
        self.assertTrue(all(isinstance(value, float) for value in values))
        self.assertEqual(values[1], 1.0)


if __name__ == "__main__":
    unittest.main()
