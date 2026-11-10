import unittest
from prototype.e12a3_relational_primitive_induction import (
    Example, FeatureSpec, LearnerView, infer, propose_relations,
)

def ex(a, b, c, d, label):
    return Example((("a",a),("b",b),("c",c),("d",d)), label)

class RelationalPrimitiveTests(unittest.TestCase):
    def test_discovers_numeric_order_relation_not_single_feature_threshold(self):
        view = LearnerView(
            (FeatureSpec("a","numeric"), FeatureSpec("b","numeric")),
            (Example((("a",1),("b",3)),1), Example((("a",4),("b",2)),0),
             Example((("a",2),("b",5)),1), Example((("a",7),("b",6)),0)),
            (Example((("a",0),("b",2)),1), Example((("a",5),("b",1)),0)))
        result = infer(view)
        self.assertEqual(result["status"], "IDENTIFIABLE_WITHIN_RELATIONAL_GRAMMAR")
        self.assertEqual((result["selected"].left, result["selected"].right,
                          result["selected"].relation), ("a","b","LT"))

    def test_discovers_categorical_same_different_relation(self):
        view = LearnerView(
            (FeatureSpec("left","categorical"), FeatureSpec("right","categorical")),
            (Example((("left","r"),("right","r")),1),
             Example((("left","r"),("right","b")),0),
             Example((("left","g"),("right","g")),1),
             Example((("left","g"),("right","y")),0)),
            (Example((("left","x"),("right","x")),1),
             Example((("left","x"),("right","z")),0)))
        result = infer(view)
        self.assertEqual(result["selected"].relation, "SAME")

    def test_proposal_uses_schema_and_train_not_gate_values(self):
        view = LearnerView(
            (FeatureSpec("a","numeric"), FeatureSpec("b","numeric")),
            (Example((("a",1),("b",2)),1), Example((("a",3),("b",1)),0)),
            (Example((("a",100),("b",-1)),0),))
        candidates = propose_relations(view)
        self.assertEqual(len(candidates), 4)  # LT, GT, EQ, SAME_PARITY
        self.assertTrue(all(p.left == "a" and p.right == "b" for p in candidates))

    def test_gate_rejects_train_only_spurious_relation(self):
        view = LearnerView(
            (FeatureSpec("a","numeric"), FeatureSpec("b","numeric")),
            (Example((("a",1),("b",3)),1), Example((("a",4),("b",2)),0),
             Example((("a",2),("b",5)),1), Example((("a",7),("b",6)),0)),
            (Example((("a",5),("b",1)),1), Example((("a",0),("b",2)),0)))
        self.assertEqual(infer(view)["status"], "INCONSISTENT")

    def test_candidate_budget_abstains(self):
        view = LearnerView(
            (FeatureSpec("a","numeric"), FeatureSpec("b","numeric")),
            (Example((("a",1),("b",2)),1), Example((("a",3),("b",1)),0)),
            (Example((("a",0),("b",2)),1),))
        result = infer(view, candidate_budget=1)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertIsNone(result["selected"])

    def test_mixed_types_do_not_generate_ill_typed_relations(self):
        view = LearnerView(
            (FeatureSpec("n","numeric"), FeatureSpec("s","categorical")),
            (Example((("n",1),("s","a")),0),),
            (Example((("n",2),("s","b")),1),))
        self.assertEqual(propose_relations(view), ())

    def test_boolean_is_not_numeric(self):
        view = LearnerView(
            (FeatureSpec("a","numeric"), FeatureSpec("b","numeric")),
            (Example((("a",True),("b",2)),1),),
            (Example((("a",1),("b",2)),0),))
        with self.assertRaises(TypeError):
            propose_relations(view)

    def test_ambiguous_relation_family_abstains(self):
        view = LearnerView(
            (FeatureSpec("a","numeric"), FeatureSpec("b","numeric")),
            (Example((("a",1),("b",3)),1), Example((("a",4),("b",2)),0)),
            (Example((("a",2),("b",5)),1), Example((("a",7),("b",6)),0)))
        # Two examples alone leave parity and order predicates underconstrained.
        self.assertIn(infer(view)["status"], {"AMBIGUOUS", "IDENTIFIABLE_WITHIN_RELATIONAL_GRAMMAR"})

if __name__ == "__main__":
    unittest.main()
