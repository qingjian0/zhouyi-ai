import unittest
from prototype.analogy import AnalogyCandidate, Evidence, Relation, assess_analogy

class AnalogyAssessmentTests(unittest.TestCase):
    def candidate(self, **overrides):
        values = dict(
            candidate_id="analogy-001", source_domain="ecology", target_domain="software",
            source_entities=("s1", "s2", "s3"), target_entities=("t1", "t2", "t3"),
            mapping={"s1": "t1", "s2": "t2", "s3": "t3"},
            dimensions=("function", "relation", "process"),
            source_relations=(Relation("s1", "s2", "regulates"), Relation("s2", "s3", "feeds")),
            target_relations=(Relation("t1", "t2", "regulates"), Relation("t2", "t3", "feeds")),
            conditions=("same operating regime",), evidence=(Evidence("study:1", True),),
            validity_scope="only under stable operating conditions",
        )
        values.update(overrides)
        return AnalogyCandidate(**values)

    def test_accepts_relation_preserving_candidate(self):
        result = assess_analogy(self.candidate())
        self.assertTrue(result.accepted)
        self.assertEqual(result.relation_f1, 1.0)
        self.assertEqual(result.mapped_entity_coverage, 1.0)

    def test_rejects_relation_direction_mismatch(self):
        candidate = self.candidate(target_relations=(
            Relation("t2", "t1", "regulates"), Relation("t2", "t3", "feeds")))
        result = assess_analogy(candidate)
        self.assertFalse(result.accepted)
        self.assertIn("RELATION_STRUCTURE_NOT_PRESERVED", result.reason_codes)

    def test_requires_evidence_and_scope(self):
        result = assess_analogy(self.candidate(evidence=(), validity_scope=""))
        self.assertIn("INSUFFICIENT_SUPPORTING_EVIDENCE", result.reason_codes)
        self.assertIn("MISSING_VALIDITY_SCOPE", result.reason_codes)

    def test_counterexample_policy_is_explicit(self):
        candidate = self.candidate(counterexamples=(Evidence("case:counterexample-1", False),))
        self.assertTrue(assess_analogy(candidate).accepted)
        strict = assess_analogy(candidate, reject_on_counterexample=True)
        self.assertFalse(strict.accepted)
        self.assertIn("UNRESOLVED_COUNTEREXAMPLE", strict.reason_codes)

    def test_rejects_non_bijective_mapping(self):
        candidate = self.candidate(mapping={"s1": "t1", "s2": "t1", "s3": "t3"})
        with self.assertRaises(ValueError):
            assess_analogy(candidate)

    def test_rejects_vacuous_empty_relation_graph(self):
        candidate = self.candidate(source_relations=(), target_relations=())
        result = assess_analogy(candidate)
        self.assertFalse(result.accepted)
        self.assertIn("INSUFFICIENT_RELATION_DATA", result.reason_codes)

    def test_rejects_unknown_dimension(self):
        with self.assertRaises(ValueError):
            assess_analogy(self.candidate(dimensions=("morphology", "vibes")))

if __name__ == "__main__":
    unittest.main()
