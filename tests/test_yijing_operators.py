import unittest

from prototype.yijing_operators import (
    BianState, Context, DualAxis, DualState, Evidence, InfluenceEdge,
    OPERATOR_REGISTRY, Relation, Status, XiangMapping, YaoLine,
    bian_bit_flip, shiwei_condition, wuxing_influence,
    xiang_partial_mapping, yao_bind_position, yin_yang_complement,
)


class YijingOperatorTests(unittest.TestCase):
    def setUp(self):
        self.ev = Evidence("ev-1", "synthetic:test-fixture")

    def test_registry_has_distinct_families(self):
        self.assertEqual(
            {c.family for c in OPERATOR_REGISTRY.values()},
            {"yin_yang", "wuxing", "yao_position", "bian_transition",
             "shiwei", "xiang_analogy"},
        )

    def test_yinyang_requires_declared_functional_constraint(self):
        axis = DualAxis("axis-1", "synthetic", "left", "right", "yy-v0")
        a = DualState("a", "axis-1", 0.8, (self.ev,))
        b = DualState("b", "axis-1", 0.2, (self.ev,))
        result = yin_yang_complement(axis, a, b, functional_constraint=None)
        self.assertEqual(result.status, Status.NEED_CONTEXT)

    def test_yinyang_does_not_claim_universal_semantics(self):
        axis = DualAxis("axis-1", "synthetic", "left", "right", "yy-v0")
        a = DualState("a", "axis-1", 0.8, (self.ev,))
        b = DualState("b", "axis-1", 0.2, (self.ev,))
        result = yin_yang_complement(
            axis, a, b, functional_constraint="jointly satisfy task constraint"
        )
        self.assertEqual(result.status, Status.APPLIED)
        self.assertEqual(result.value["interpretation"], "candidate_only")

    def test_wuxing_missing_context_is_unknown_to_execution(self):
        edge = InfluenceEdge("wood", "fire", "PROMOTE", 0.7,
                             {"phase": "spring"}, "textual-school-a-v1")
        result = wuxing_influence(edge, context=Context(), source_value=1.0,
                                  evidence=(self.ev,))
        self.assertEqual(result.status, Status.NEED_CONTEXT)

    def test_wuxing_is_directed_and_versioned(self):
        edge = InfluenceEdge("wood", "fire", "PROMOTE", 0.5,
                             {"phase": "spring"}, "school-a-v1")
        result = wuxing_influence(
            edge, context=Context(phase="spring"), source_value=2.0,
            evidence=(self.ev,),
        )
        self.assertEqual(result.status, Status.APPLIED)
        self.assertEqual(result.value["directed_effect"], 1.0)
        self.assertEqual(result.value["interpretation_version"], "school-a-v1")

    def test_wuxing_unknown_relation_is_not_silently_signed(self):
        edge = InfluenceEdge("a", "b", "MYSTERY", 1.0, {}, "v1")
        result = wuxing_influence(edge, context=Context(), source_value=1.0,
                                  evidence=(self.ev,))
        self.assertEqual(result.status, Status.UNKNOWN)

    def test_yao_position_preserves_role_and_position(self):
        line = YaoLine("line-1", "yang", 3, "lower-middle", "school-v1",
                       (self.ev,))
        result = yao_bind_position(line, expected_position=3)
        self.assertTrue(result.value["position_match"])
        self.assertEqual(result.value["role"], "lower-middle")

    def test_bian_flip_is_explicitly_limited(self):
        state = BianState((1, 0, 1, 0, 1, 0), "bitflip-v0", (self.ev,))
        result = bian_bit_flip(state, positions=(2, 6), trigger="synthetic event")
        self.assertEqual(result.value["after"], (1, 1, 1, 0, 1, 1))
        self.assertEqual(result.value["operator_scope"], "limited_bit_flip_baseline")

    def test_bian_requires_trigger(self):
        state = BianState((1, 0), "v1", (self.ev,))
        self.assertEqual(
            bian_bit_flip(state, positions=(1,), trigger=None).status,
            Status.NEED_CONTEXT,
        )

    def test_shiwei_requires_explicit_time_and_position_when_requested(self):
        result = shiwei_condition(
            context=Context(domain="synthetic", phase="spring"),
            required_fields=("domain", "valid_time", "position"),
            evidence=(self.ev,),
        )
        self.assertEqual(result.status, Status.NEED_CONTEXT)

    def test_xiang_requires_type_and_role_compatibility(self):
        mapping = XiangMapping({"s": "t"}, False, True, (self.ev,))
        result = xiang_partial_mapping(
            (Relation("s", "s", "supports"),), (), mapping
        )
        self.assertEqual(result.status, Status.NOT_APPLICABLE)

    def test_xiang_measures_structure_not_surface_similarity(self):
        mapping = XiangMapping({"s1": "t1", "s2": "t2"}, True, True,
                               (self.ev,))
        result = xiang_partial_mapping(
            (Relation("s1", "s2", "supports"),),
            (Relation("t1", "t2", "supports"),), mapping,
        )
        self.assertEqual(result.value["structure_preservation"], 1.0)
        self.assertEqual(result.status, Status.APPLIED)

    def test_xiang_records_conflicting_relation(self):
        mapping = XiangMapping({"s1": "t1", "s2": "t2"}, True, True,
                               (self.ev,))
        result = xiang_partial_mapping(
            (Relation("s1", "s2", "supports"),),
            (Relation("t1", "t2", "blocks"),), mapping,
        )
        self.assertEqual(len(result.value["conflicts"]), 1)
        self.assertEqual(result.value["structure_preservation"], 0.0)


if __name__ == "__main__":
    unittest.main()
