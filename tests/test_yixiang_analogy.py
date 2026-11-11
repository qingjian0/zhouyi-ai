import unittest

from prototype.yixiang_analogy import (
    AnalogyBridge,
    BridgeStatus,
    MappingKind,
    Node,
    Relation,
    RelationalGraph,
    validate_bridge,
)


def graph_pair(reverse_target=False):
    source = RelationalGraph(
        "source",
        tuple(sorted((
            Node("a", "actor"), Node("b", "system"), Node("c", "state"),
        ))),
        tuple(sorted((
            Relation("acts_on", ("a", "b")),
            Relation("changes", ("b", "c")),
        ))),
    )
    target_relations = (
        Relation("controls", ("y", "x") if reverse_target else ("x", "y")),
        Relation("transitions", ("y", "z")),
    )
    target = RelationalGraph(
        "target",
        tuple(sorted((
            Node("x", "controller"), Node("y", "system"), Node("z", "state"),
        ))),
        tuple(sorted(target_relations)),
    )
    bridge = AnalogyBridge(
        bridge_id="bridge-1",
        source=source,
        target=target,
        mapping_kind=MappingKind.RELATION,
        node_mapping=(("a", "x"), ("b", "y"), ("c", "z")),
        node_type_mapping=(("actor", "controller"), ("state", "state"), ("system", "system")),
        relation_mapping=(("acts_on", "controls"), ("changes", "transitions")),
        scope_conditions=("same causal direction",),
        predicted_consequences=("controller action precedes state transition",),
        counterexamples=("reversed control direction",),
        evidence_refs=("source:1", "target:1"),
    )
    return bridge


class YixiangAnalogyTests(unittest.TestCase):
    def test_ordered_relations_are_preserved(self):
        result = validate_bridge(graph_pair())
        self.assertEqual(result.status, BridgeStatus.STRUCTURALLY_PRESERVED)
        self.assertEqual(result.mapping_coverage, 1.0)
        self.assertEqual(result.preservation_rate, 1.0)
        self.assertEqual(len(result.preserved_relations), 2)

    def test_role_reversal_is_a_counterexample(self):
        result = validate_bridge(graph_pair(reverse_target=True))
        self.assertEqual(result.status, BridgeStatus.COUNTEREXAMPLE)
        self.assertEqual(len(result.violated_relations), 1)
        self.assertEqual(result.preservation_rate, 0.5)

    def test_unmapped_relation_is_not_misreported_as_contradiction(self):
        bridge = graph_pair()
        bridge = AnalogyBridge(
            bridge_id=bridge.bridge_id,
            source=bridge.source,
            target=bridge.target,
            mapping_kind=bridge.mapping_kind,
            node_mapping=bridge.node_mapping,
            node_type_mapping=bridge.node_type_mapping,
            relation_mapping=(("acts_on", "controls"),),
        )
        result = validate_bridge(bridge)
        self.assertEqual(result.status, BridgeStatus.PARTIAL)
        self.assertEqual(len(result.unmapped_relations), 1)
        self.assertEqual(len(result.violated_relations), 0)
        self.assertEqual(result.mapping_coverage, 0.5)

    def test_type_alignment_must_be_explicit(self):
        bridge = graph_pair()
        with self.assertRaisesRegex(ValueError, "explicit compatible type mapping"):
            AnalogyBridge(
                bridge_id="bad",
                source=bridge.source,
                target=bridge.target,
                mapping_kind=bridge.mapping_kind,
                node_mapping=bridge.node_mapping,
                node_type_mapping=(("actor", "system"), ("state", "state"), ("system", "controller")),
                relation_mapping=bridge.relation_mapping,
            )

    def test_malformed_mapping_shape_is_rejected_as_value_error(self):
        bridge = graph_pair()
        with self.assertRaisesRegex(ValueError, "entries must be pairs"):
            AnalogyBridge(
                bridge_id="bad-shape",
                source=bridge.source,
                target=bridge.target,
                mapping_kind=bridge.mapping_kind,
                node_mapping=(["a", "x"],),
                node_type_mapping=bridge.node_type_mapping,
                relation_mapping=bridge.relation_mapping,
            )

    def test_digest_is_deterministic(self):
        first = validate_bridge(graph_pair()).bridge_digest
        second = validate_bridge(graph_pair()).bridge_digest
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_empty_mapping_is_untestable(self):
        bridge = graph_pair()
        unmapped = AnalogyBridge(
            bridge_id="empty",
            source=bridge.source,
            target=bridge.target,
            mapping_kind=bridge.mapping_kind,
            node_mapping=(),
            node_type_mapping=(),
            relation_mapping=(),
        )
        self.assertEqual(validate_bridge(unmapped).status, BridgeStatus.UNTESTABLE)


if __name__ == "__main__":
    unittest.main()
