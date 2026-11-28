import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from prototype.classiang_native import EvidenceRef, Relation, Symbol, SymbolGraph
from prototype.classiang_native_learning import (
    CompositionLabel, NativeCompositionScorer, NativeRoleBindingModel, _features, graph_from_json, rank_compositions, train_and_evaluate, train_and_evaluate_role_model,
)


def training_fixture():
    evidence = []
    symbols = []
    relations = []
    labels = []
    for i in range(4):
        family = f"family-{i}"
        evidence_ids = [f"e{i}-{suffix}" for suffix in ("a", "b", "c", "d")]
        evidence.extend(
            EvidenceRef(eid, f"source-{i}", family, f"p.{index + 1}", "CC-BY-4.0", True)
            for index, eid in enumerate(evidence_ids)
        )
        hub, a, b, c_symbol, d, e, f_symbol = (
            f"node-{i}-{suffix}" for suffix in ("hub", "a", "b", "c", "d", "e", "f")
        )
        symbols.extend((
            Symbol(hub, "domain", "node", (("role", "hub"),), tuple(evidence_ids[:2])),
            Symbol(a, "domain", "node", (("index", str(i)),), (evidence_ids[0],)),
            Symbol(b, "domain", "node", (("index", str(i + 1)),), (evidence_ids[1],)),
            Symbol(c_symbol, "domain", "node", (("index", "c"),), (evidence_ids[2],)),
            Symbol(d, "domain", "node", (("index", "d"),), (evidence_ids[2],)),
            Symbol(e, "domain", "node", (("index", "e"),), (evidence_ids[3],)),
            Symbol(f_symbol, "domain", "node", (("index", "f"),), (evidence_ids[3],)),
        ))
        relation_ids = [f"r{i}-{suffix}" for suffix in ("a", "b", "c", "d")]
        relations.extend((
            Relation(relation_ids[0], "connects", (("source", hub), ("target", a)), (evidence_ids[0],)),
            Relation(relation_ids[1], "connects", (("source", hub), ("target", b)), (evidence_ids[1],)),
            Relation(relation_ids[2], "connects", (("source", c_symbol), ("target", d)), (evidence_ids[2],)),
            Relation(relation_ids[3], "connects", (("source", e), ("target", f_symbol)), (evidence_ids[3],)),
        ))
        labels.extend((
            CompositionLabel(
                example_id=f"{family}-positive", group_id=family,
                source_family=family, relation_ids=tuple(relation_ids[:2]),
                evidence_ids=tuple(evidence_ids[:2]), label=1, reviewed=True, label_basis="human_reviewed_pair", reviewer_id="fixture-reviewer", adjudication_id=f"{family}-positive", scope="fixture-domain",
            ),
            CompositionLabel(
                example_id=f"{family}-negative", group_id=family,
                source_family=family, relation_ids=tuple(relation_ids[2:]),
                evidence_ids=tuple(evidence_ids[2:]), label=0, reviewed=True, label_basis="human_reviewed_pair", reviewer_id="fixture-reviewer", adjudication_id=f"{family}-negative", scope="fixture-domain",
            ),
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
            graph, labels, seed=11, dimension=8, epochs=200, learning_rate=0.1,
        )
        self.assertEqual(model.trained_examples, report["train_examples"])
        self.assertTrue(report["source_family_disjoint"])
        self.assertEqual(model.dimension, 8)
        self.assertNotEqual(model.shared_symbol_weight, 0.0)
        held_out = int(report["validation_source_families"][0].split("-")[-1])
        positive = model.predict_probability(graph, (f"r{held_out}-a", f"r{held_out}-b"))
        negative = model.predict_probability(graph, (f"r{held_out}-c", f"r{held_out}-d"))
        self.assertGreater(positive, 0.5)
        self.assertLess(negative, 0.5)
        self.assertGreater(positive, negative)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "role-model.json"
            digest = model.save(path)
            restored = NativeRoleBindingModel.load(path)
            self.assertEqual(len(digest), 64)
            self.assertEqual(restored.to_dict(), model.to_dict())

    def test_role_binding_scores_bounded_compositions(self):
        graph, labels = training_fixture()
        model, _ = train_and_evaluate_role_model(
            graph, labels, seed=11, dimension=8, epochs=20,
        )
        ranked = rank_compositions(graph, model, max_depth=2, max_candidates=100)
        self.assertTrue(ranked)
        self.assertTrue(all(0.0 <= score <= 1.0 for score, _ in ranked))
        self.assertEqual(
            list(ranked),
            sorted(ranked, key=lambda item: (-item[0], item[1].relation_ids)),
        )

    def test_role_binding_reports_partial_oov_vocabulary_coverage(self):
        graph, labels = training_fixture()
        model = NativeRoleBindingModel.initialize(graph, labels[:2], dimension=8)
        relation_map = {item.relation_id: item for item in graph.relations}
        selected_symbols = {
            symbol_id
            for relation_id in labels[0].relation_ids
            for _, symbol_id in relation_map[relation_id].roles
        }
        target_id = sorted(selected_symbols)[0]
        changed_symbols = []
        for symbol in graph.symbols:
            if symbol.symbol_id == target_id:
                changed_symbols.append(Symbol(
                    symbol.symbol_id, symbol.domain, symbol.symbol_type,
                    symbol.attributes + (("novel_attribute", "never_seen_value"),),
                    symbol.evidence_ids, symbol.context, symbol.version,
                ))
            else:
                changed_symbols.append(symbol)
        oov_graph = SymbolGraph(graph.evidence, tuple(changed_symbols), graph.relations)
        coverage = model.vocabulary_coverage(oov_graph, labels[0].relation_ids)
        self.assertGreater(coverage["unknown_fields"], 0)
        self.assertGreater(coverage["unknown"]["attribute_keys"], 0)
        self.assertGreater(coverage["unknown"]["attribute_values"], 0)
        self.assertLess(coverage["coverage"], 1.0)

    def test_role_binding_rejects_unknown_relation_type(self):
        graph, labels = training_fixture()
        model = NativeRoleBindingModel.initialize(graph, labels[:2], dimension=8)
        with self.assertRaisesRegex(ValueError, "unknown relation ID"):
            model.predict_probability(graph, ("missing-relation",))

    def test_unknown_gold_annotations_are_excluded_from_training(self):
        graph, labels = training_fixture()
        first = labels[0]
        unknown = CompositionLabel(
            example_id="family-0-unknown", group_id=first.group_id,
            source_family=first.source_family, relation_ids=first.relation_ids,
            evidence_ids=first.evidence_ids, label=2, reviewed=True,
            label_basis="human_reviewed_pair", reviewer_id="fixture-reviewer",
            adjudication_id="unknown-adjudication", scope="fixture-domain",
            conditions=("only-under-condition-x",),
        )
        model, report = train_and_evaluate(graph, labels + (unknown,), seed=11, epochs=5)
        self.assertGreater(model.trained_examples, 0)
        self.assertEqual(report["unknown_annotations_excluded"], 1)

    def test_gold_pair_requires_adjudication_metadata(self):
        graph, labels = training_fixture()
        first = labels[0]
        incomplete = CompositionLabel(
            example_id="missing-adjudication", group_id=first.group_id,
            source_family=first.source_family, relation_ids=first.relation_ids,
            evidence_ids=first.evidence_ids, label=1, reviewed=True,
            label_basis="human_reviewed_pair",
        )
        with self.assertRaisesRegex(ValueError, "reviewer_id"):
            incomplete.validate(graph)

    def test_rejects_unreviewed_labels(self):
        graph, labels = training_fixture()
        bad = list(labels)
        bad[0] = CompositionLabel(
            example_id=bad[0].example_id, group_id=bad[0].group_id,
            source_family=bad[0].source_family, relation_ids=bad[0].relation_ids,
            evidence_ids=bad[0].evidence_ids, label=bad[0].label, reviewed=False, reviewer_id="fixture-reviewer", adjudication_id="bad-review", scope="fixture-domain",
        )
        with self.assertRaisesRegex(ValueError, "reviewed"):
            train_and_evaluate(graph, tuple(bad))

    def test_rejects_source_family_leakage(self):
        graph, labels = training_fixture()
        first = labels[0]
        leaked = CompositionLabel(
            example_id="cross-family-copy", group_id="family-1",
            source_family="family-1", relation_ids=first.relation_ids,
            evidence_ids=first.evidence_ids, label=0, reviewed=True, label_basis="human_reviewed_pair", reviewer_id="fixture-reviewer", adjudication_id="leak-review", scope="fixture-domain",
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
        self.assertAlmostEqual(values[1], 1.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
