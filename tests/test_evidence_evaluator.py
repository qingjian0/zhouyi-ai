import unittest
from orchestrator.research.evidence import evaluate_evidence

def row(evidence_id, split, control, mean, lower, upper, seeds=12, valid=True, preregistered=True):
    return {"evidence_id": evidence_id, "split": split, "control": control, "effect_mean": mean, "ci_lower": lower, "ci_upper": upper, "seeds": seeds, "valid": valid, "preregistered": preregistered}

class EvidenceEvaluatorTests(unittest.TestCase):
    def test_requires_ood_and_control_support(self):
        result = evaluate_evidence(predicted_direction="positive", evidence=[row("ood", "ood", "none", .2, .1, .3), row("shuffle", "iid", "shuffled", .1, .02, .18)])
        self.assertEqual(result["verdict"], "supported")
    def test_one_row_cannot_satisfy_both_support_gates(self):
        result = evaluate_evidence(predicted_direction="positive", evidence=[
            row("ood-shuffled", "ood", "shuffled", .2, .1, .3)
        ])
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertFalse(result["gates"]["independent_support_rows"])

    def test_iid_only_is_inconclusive(self):
        result = evaluate_evidence(predicted_direction="positive", evidence=[row("iid", "iid", "none", .2, .1, .3), row("shuffle", "iid", "shuffled", .1, .02, .18)])
        self.assertEqual(result["verdict"], "inconclusive")
    def test_adverse_ood_rejects(self):
        result = evaluate_evidence(predicted_direction="positive", evidence=[row("ood", "ood", "none", -.2, -.3, -.1), row("shuffle", "iid", "random", .1, .02, .18)])
        self.assertEqual(result["verdict"], "rejected")
    def test_insufficient_seeds_excluded(self):
        result = evaluate_evidence(predicted_direction="positive", evidence=[row("ood", "ood", "none", .2, .1, .3, seeds=3), row("shuffle", "iid", "shuffled", .1, .02, .18)])
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertEqual(result["evidence"][0]["status"], "excluded")
    def test_negative_direction(self):
        result = evaluate_evidence(predicted_direction="negative", evidence=[row("ood", "ood", "none", -.2, -.3, -.1), row("shuffle", "iid", "shuffled", -.1, -.18, -.02)])
        self.assertEqual(result["verdict"], "supported")
    def test_duplicate_ids_and_bad_intervals_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_evidence(predicted_direction="positive", evidence=[row("same", "ood", "none", .2, .1, .3), row("same", "iid", "random", .1, .02, .18)])
        with self.assertRaises(ValueError):
            evaluate_evidence(predicted_direction="positive", evidence=[row("bad", "ood", "none", .2, .4, .3)])

if __name__ == "__main__":
    unittest.main()
