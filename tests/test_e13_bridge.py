import unittest

from prototype.e13_contract import (
    Entity, RelationInstance, RelationSchema, RelationalGraph, RoleSemantics
)
from prototype.e13_bridge import propose_bridge, validate_bridge


def make_graph(prefix, domain, source_side):
    if source_side:
        types = ("heat_source", "receiver")
        relation = "transfers_heat"
        roles = ("donor", "recipient")
        context = (("domain", domain),)
    else:
        types = ("bio_supplier", "consumer")
        relation = "transfers_energy"
        roles = ("provider", "recipient")
        context = (("field", domain),)
    schema = RelationSchema(
        relation, 2, types, RoleSemantics.ORDERED_NAMED, roles,
        symmetry="ASYMMETRIC", context_keys=tuple(k for k, _ in context)
    )
    graph = RelationalGraph(
        (Entity(prefix + "a", types[0]), Entity(prefix + "b", types[1])),
        (schema,),
        (RelationInstance(prefix + "r", relation, (prefix + "a", prefix + "b"), context),)
    )
    return graph


class CrossDomainBridgeTests(unittest.TestCase):
    def setUp(self):
        self.source = make_graph("s", "thermal", True)
        # The domain vocabulary changes, but this mapped context value must remain
        # equal unless a separate explicit value-level transform is introduced.
        self.target = make_graph("t", "thermal", False)

    def hypothesis(self, **overrides):
        args = dict(
            entity_types=(("heat_source", "bio_supplier"), ("receiver", "consumer")),
            relations=(("transfers_heat", "transfers_energy"),),
            roles=(("transfers_heat", "donor", "provider"),
                   ("transfers_heat", "recipient", "recipient")),
            contexts=(("domain", "field"),),
            provenance="human-authored mapping proposal v1",
            rationale="test whether a directed transfer pattern can be structurally aligned",
        )
        args.update(overrides)
        return propose_bridge("bridge-1", **args)

    def test_explicit_cross_domain_bridge_validates(self):
        result = validate_bridge(self.source, self.target, self.hypothesis())
        self.assertEqual(result.status, "VALID")
        self.assertEqual(result.matched_relation_pairs, (("sr", "tr"),))

    def test_no_implicit_relation_or_type_mapping(self):
        h = propose_bridge(
            "incomplete", entity_types=(), relations=(), roles=(),
            provenance="test", rationale="intentionally incomplete"
        )
        result = validate_bridge(self.source, self.target, h)
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UNMAPPED_OR_EXTRA_SOURCE_RELATION", result.reasons)

    def test_direction_or_role_swap_is_rejected(self):
        h = self.hypothesis(roles=(("transfers_heat", "donor", "recipient"),
                                  ("transfers_heat", "recipient", "provider")))
        result = validate_bridge(self.source, self.target, h)
        self.assertEqual(result.status, "REJECTED")
        self.assertTrue(any(
            marker in reason
            for marker in ("ROLE_MISMATCH", "ARGUMENT_TYPE_PATTERN_MISMATCH")
            for reason in result.reasons
        ))

    def test_relation_collision_rejected_by_default(self):
        with self.assertRaises(ValueError):
            self.hypothesis(relations=(("transfers_heat", "transfers_energy"),
                                       ("other", "transfers_energy")))

    def test_many_to_one_is_limited_to_entity_type_abstraction(self):
        with self.assertRaises(ValueError):
            self.hypothesis(
                relations=(("transfers_heat", "transfers_energy"),
                           ("other", "transfers_energy")),
                allow_many_to_one=True,
            )
        with self.assertRaises(ValueError):
            self.hypothesis(
                contexts=(("domain", "field"), ("other_domain", "field")),
                allow_many_to_one=True,
            )

    def test_context_mismatch_rejected(self):
        wrong_target = make_graph("t", "different", False)
        result = validate_bridge(self.source, wrong_target, self.hypothesis())
        self.assertEqual(result.status, "REJECTED")
        self.assertTrue(any("RELATION_INSTANCE_MATCH_COUNT" in x for x in result.reasons))

    def test_missing_provenance_rejected(self):
        with self.assertRaises(ValueError):
            self.hypothesis(provenance="")


    def test_explicit_role_mapping_can_realign_argument_positions(self):
        target_schema = RelationSchema(
            "transfers_energy", 2, ("consumer", "bio_supplier"),
            RoleSemantics.ORDERED_NAMED, ("recipient", "provider"),
            symmetry="ASYMMETRIC", context_keys=("field",)
        )
        reordered_target = RelationalGraph(
            (Entity("ta", "bio_supplier"), Entity("tb", "consumer")),
            (target_schema,),
            (RelationInstance("tr2", "transfers_energy", ("tb", "ta"),
                              (("field", "thermal"),)),)
        )
        result = validate_bridge(self.source, reordered_target, self.hypothesis())
        self.assertEqual(result.status, "VALID")
        self.assertEqual(result.matched_relation_pairs, (("sr", "tr2"),))


if __name__ == "__main__":
    unittest.main()
