import itertools
import unittest

from prototype.e13_bridge import propose_bridge, validate_bridge
from prototype.e13_contract import (
    Entity, RelationInstance, RelationSchema, RelationalGraph, RoleSemantics
)
from prototype.e13_b3 import enumerate_bridge_candidates
from test_e13_bridge import make_graph


class IndependentEnumerationOracleTests(unittest.TestCase):
    def test_b3_matches_independent_tiny_space_oracle(self):
        source = make_graph("s", "thermal", True)
        target = make_graph("t", "thermal", False)
        result = enumerate_bridge_candidates(
            source, target, context_key_map=(("domain", "field"),), max_candidates=100
        )
        self.assertEqual(result.status, "COMPLETE")

        source_types = sorted({e.entity_type for e in source.entities})
        target_types = sorted({e.entity_type for e in target.entities})
        target_schema = target.schemas[0]
        source_schema = source.schemas[0]
        oracle_valid = set()
        serial = 0
        for target_type_order in itertools.permutations(target_types, len(source_types)):
            type_map = tuple(zip(source_types, target_type_order))
            for target_role_order in itertools.permutations(target_schema.role_names):
                serial += 1
                hypothesis = propose_bridge(
                    f"oracle-{serial}",
                    entity_types=type_map,
                    relations=((source_schema.relation_type, target_schema.relation_type),),
                    roles=tuple(
                        (source_schema.relation_type, target_schema.relation_type, sr, tr)
                        for sr, tr in zip(source_schema.role_names, target_role_order)
                    ),
                    contexts=(("domain", "field"),),
                    provenance="independent test oracle",
                    rationale="independent exhaustive permutation enumeration",
                )
                if validate_bridge(source, target, hypothesis).status == "VALID":
                    oracle_valid.add((type_map, target_role_order))
        actual_valid = {
            (tuple((x.source, x.target) for x in h.entity_types),
             tuple(x.target_role for x in h.roles))
            for h, _ in result.valid_candidates
        }
        self.assertEqual(actual_valid, oracle_valid)


if __name__ == "__main__":
    unittest.main()
