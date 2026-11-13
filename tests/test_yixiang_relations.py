import unittest
from prototype.yixiang_relations import HyperRelation, HypergraphAnalogy, assess_hypergraph_analogy

class HypergraphAnalogyTests(unittest.TestCase):
    def candidate(self, **overrides):
        values = dict(
            candidate_id="nary-001",
            source_entities=("s1","s2","s3","s4"), target_entities=("t1","t2","t3","t4"),
            mapping={"s1":"t1","s2":"t2","s3":"t3","s4":"t4"},
            source_relations=(
                HyperRelation("sr1","transfers",(("agent","s1"),("source","s2"),("recipient","s3"))),
                HyperRelation("sr2","regulates",(("regulator","s4"),("process","s3")))),
            target_relations=(
                HyperRelation("tr1","transfers",(("agent","t1"),("source","t2"),("recipient","t3"))),
                HyperRelation("tr2","regulates",(("regulator","t4"),("process","t3")))),
            evidence_refs=("fixture:nary-1",), conditions=("same declared role semantics",),
            validity_scope="only the supplied finite hypergraphs")
        values.update(overrides)
        return HypergraphAnalogy(**values)

    def test_accepts_role_preserving_nary_mapping(self):
        result=assess_hypergraph_analogy(self.candidate())
        self.assertTrue(result.accepted); self.assertEqual(result.f1,1.0); self.assertEqual(len(result.preserved),2)

    def test_rejects_role_swap_even_when_entity_set_is_same(self):
        c=self.candidate(target_relations=(
            HyperRelation("tr1","transfers",(("agent","t1"),("source","t3"),("recipient","t2"))),
            HyperRelation("tr2","regulates",(("regulator","t4"),("process","t3")))))
        result=assess_hypergraph_analogy(c)
        self.assertFalse(result.accepted); self.assertIn("NARY_ROLE_STRUCTURE_NOT_PRESERVED",result.reason_codes)
        self.assertEqual(result.f1,0.5)

    def test_reports_unmapped_source_hyperedge_as_missing(self):
        result=assess_hypergraph_analogy(self.candidate(mapping={"s1":"t1","s2":"t2","s3":"t3"}))
        self.assertFalse(result.accepted); self.assertEqual(len(result.missing),1)

    def test_rejects_duplicate_role_names(self):
        c=self.candidate(source_relations=(HyperRelation("sr1","bad",(("same","s1"),("same","s2"))),))
        with self.assertRaisesRegex(ValueError,"unique"): assess_hypergraph_analogy(c)

    def test_requires_evidence_conditions_and_scope(self):
        result=assess_hypergraph_analogy(self.candidate(evidence_refs=(),conditions=(),validity_scope=""))
        self.assertFalse(result.accepted)
        self.assertEqual(set(result.reason_codes),{"MISSING_EVIDENCE","MISSING_CONDITIONS","MISSING_VALIDITY_SCOPE"})

if __name__=="__main__": unittest.main()
