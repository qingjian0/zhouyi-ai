import itertools
import unittest
from prototype.e13_bridge import propose_bridge, validate_bridge
from prototype.e13_b3 import enumerate_bridge_candidates
from test_e13_bridge import make_graph

class IndependentEnumerationOracleTests(unittest.TestCase):
    def test_b3_matches_independent_tiny_space_oracle(self):
        source=make_graph("s","thermal",True)
        target=make_graph("t","thermal",False)
        result=enumerate_bridge_candidates(source,target,context_key_map=(("domain","field"),),max_candidates=100)
        self.assertEqual(result.status,"COMPLETE")
        st=sorted({e.entity_type for e in source.entities})
        tt=sorted({e.entity_type for e in target.entities})
        ss=source.schemas[0]; ts=target.schemas[0]
        oracle=set()
        serial=0
        for type_order in itertools.permutations(tt,len(st)):
            type_map=tuple(zip(st,type_order))
            for role_order in itertools.permutations(ts.role_names):
                serial+=1
                h=propose_bridge(f"oracle-{serial}",entity_types=type_map,
                    relations=((ss.relation_type,ts.relation_type),),
                    roles=tuple((ss.relation_type,ts.relation_type,a,b) for a,b in zip(ss.role_names,role_order)),
                    contexts=(("domain","field"),),provenance="independent test oracle",
                    rationale="exhaustive tiny permutation oracle")
                if validate_bridge(source,target,h).status=="VALID":
                    oracle.add((type_map,role_order))
        actual={(tuple((x.source,x.target) for x in h.entity_types),tuple(x.target_role for x in h.roles)) for h,_ in result.valid_candidates}
        self.assertEqual(actual,oracle)

if __name__ == "__main__":
    unittest.main()
