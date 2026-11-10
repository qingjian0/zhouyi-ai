import unittest

from prototype.e12a4_counterexample_operator_expansion import (
    FeatureSpec, LearnerView, Observation, infer, propose_operators,
)


def obs(eid, x, y, label):
    return Observation(eid, (("x", x), ("y", y)), label)


class CounterexampleOperatorExpansionTests(unittest.TestCase):
    def view(self):
        return LearnerView(
            (FeatureSpec("x"), FeatureSpec("y")),
            (obs("tr-1", 0, 1, 0), obs("tr-2", 0, 4, 1),
             obs("tr-3", 2, 3, 0), obs("tr-4", 1, 6, 1),
             obs("tr-5", 5, 7, 0)),
            (obs("ga-1", 0, 5, 1), obs("ga-2", 3, 4, 0)),
            (("x", "y"),),
        )

    def test_creates_parameterized_operator_outside_a3_grammar(self):
        result = infer(self.view())
        self.assertEqual(result["status"], "IDENTIFIABLE_WITHIN_A4_OPERATOR_FAMILY")
        selected = result["selected"]
        self.assertEqual(selected.family, "ABS_DIFF_GT")
        self.assertAlmostEqual(selected.threshold, 3.0)
        self.assertEqual(selected.evaluate(0, 4), 1)
        self.assertEqual(selected.evaluate(2, 3), 0)

    def test_candidate_generation_depends_on_train_not_gate(self):
        original = self.view()
        changed_gate = LearnerView(
            original.schema, original.train,
            (obs("ga-1b", 0, 5, 0), obs("ga-2b", 3, 4, 1)),
            original.counterexample_pairs,
        )
        self.assertEqual(propose_operators(original), propose_operators(changed_gate))

    def test_only_a3_flagged_pairs_can_expand(self):
        original = self.view()
        schema = original.schema + (FeatureSpec("z"),)
        train = tuple(Observation(item.evidence_id,
                                  item.values + (("z", item.value("x") + 100),),
                                  item.label) for item in original.train)
        gate = tuple(Observation(item.evidence_id,
                                 item.values + (("z", item.value("x") + 100),),
                                 item.label) for item in original.gate)
        view = LearnerView(schema, train, gate, (("x", "y"),))
        self.assertTrue(propose_operators(view))
        self.assertTrue(all((item.left, item.right) == ("x", "y")
                            for item in propose_operators(view)))

    def test_gate_rejects_train_fit_candidate(self):
        original = self.view()
        bad_gate = LearnerView(
            original.schema, original.train,
            (obs("ga-bad-1", 0, 5, 0), obs("ga-bad-2", 3, 4, 1)),
            original.counterexample_pairs,
        )
        self.assertEqual(infer(bad_gate)["status"], "INCONSISTENT")

    def test_multiple_flagged_pairs_remain_ambiguous(self):
        schema = (FeatureSpec("x"), FeatureSpec("y"), FeatureSpec("z"))
        train = (
            Observation("t1", (("x", 0), ("y", 1), ("z", 10)), 0),
            Observation("t2", (("x", 0), ("y", 5), ("z", 14)), 1),
            Observation("t3", (("x", 2), ("y", 3), ("z", 12)), 0),
            Observation("t4", (("x", 1), ("y", 7), ("z", 16)), 1),
        )
        gate = (
            Observation("g1", (("x", 0), ("y", 5), ("z", 15)), 1),
            Observation("g2", (("x", 3), ("y", 4), ("z", 11)), 0),
        )
        result = infer(LearnerView(schema, train, gate, (("x", "y"), ("x", "z"))))
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertIsNone(result["selected"])

    def test_candidate_budget_abstains(self):
        result = infer(self.view(), candidate_budget=1)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertIsNone(result["selected"])

    def test_provenance_records_parent_and_boundary_evidence(self):
        result = infer(self.view())
        provenance = result["provenance"]
        self.assertEqual(provenance["operator_id"], result["selected"].operator_id)
        self.assertEqual(provenance["parent_primitives"],
                         ("A3:numeric:pair", "META:threshold-separation"))
        self.assertEqual(provenance["source_evidence_ids"], ("tr-2", "tr-5"))
        self.assertEqual(provenance["validation_evidence_ids"], ("ga-1", "ga-2"))
        self.assertEqual(provenance["counterexample_pairs"], (("x", "y"),))
        self.assertEqual(provenance["revision"], "E12-A4-r0")

    def test_no_separating_train_gap_means_no_operator(self):
        view = LearnerView(
            (FeatureSpec("x"), FeatureSpec("y")),
            (obs("t1", 0, 1, 0), obs("t2", 2, 3, 1)),
            (obs("g1", 4, 5, 0),),
            (("x", "y"),),
        )
        self.assertEqual(propose_operators(view), ())
        self.assertEqual(infer(view)["status"], "INCONSISTENT")

    def test_train_gate_evidence_overlap_is_rejected(self):
        view = self.view()
        overlapping = LearnerView(view.schema, view.train,
                                   (view.train[0], obs("ga-2", 3, 4, 0)),
                                   view.counterexample_pairs)
        with self.assertRaises(ValueError):
            infer(overlapping)

    def test_missing_counterexample_pair_and_bad_values_fail_closed(self):
        view = self.view()
        with self.assertRaises(ValueError):
            infer(LearnerView(view.schema, view.train, view.gate, ()))
        bad = LearnerView(
            (FeatureSpec("x"), FeatureSpec("y")),
            (Observation("t1", (("x", True), ("y", 1)), 0),),
            (obs("g1", 0, 1, 0),),
            (("x", "y"),),
        )
        with self.assertRaises(TypeError):
            propose_operators(bad)
        with self.assertRaises(TypeError):
            infer(view, candidate_budget=True)


if __name__ == "__main__":
    unittest.main()
