import unittest

from orchestrator.research.active_design import design_next_experiment


def candidate(candidate_id, covers, cost=10, discrimination=0.5, **overrides):
    value = {
        "candidate_id": candidate_id,
        "hypothesis_id": "H-001",
        "covers": covers,
        "estimated_compute": cost,
        "expected_discrimination": discrimination,
        "preregistration_ref": "protocol://H-001/v1",
        "preregistered": True,
        "design": {"candidate": candidate_id},
    }
    value.update(overrides)
    return value


class ActiveDesignTests(unittest.TestCase):
    def test_prefers_more_required_gate_coverage(self):
        result = design_next_experiment(
            hypothesis_id="H-001", required_gates=["ood", "control"],
            candidates=[candidate("one", ["ood"], discrimination=1.0),
                        candidate("both", ["ood", "control"], discrimination=0.2)],
            compute_budget=100,
        )
        self.assertEqual(result["selected"]["candidate_id"], "both")

    def test_ranks_discrimination_then_cost_then_id(self):
        result = design_next_experiment(
            hypothesis_id="H-001", required_gates=["ood"],
            candidates=[candidate("z", ["ood"], cost=8, discrimination=0.8),
                        candidate("b", ["ood"], cost=5, discrimination=0.8),
                        candidate("a", ["ood"], cost=5, discrimination=0.8)],
            compute_budget=20,
        )
        self.assertEqual(result["selected"]["candidate_id"], "a")

    def test_excludes_over_budget_and_unregistered(self):
        result = design_next_experiment(
            hypothesis_id="H-001", required_gates=["ood"],
            candidates=[candidate("expensive", ["ood"], cost=101),
                        candidate("unregistered", ["ood"], preregistered=False)],
            compute_budget=100,
        )
        self.assertIsNone(result["selected"])
        self.assertEqual({x["reason"] for x in result["excluded"]},
                         {"over_compute_budget", "not_preregistered"})

    def test_excludes_other_hypothesis_and_irrelevant_gate(self):
        result = design_next_experiment(
            hypothesis_id="H-001", required_gates=["ood"],
            candidates=[candidate("other", ["ood"], hypothesis_id="H-002"),
                        candidate("iid", ["replication"])],
            compute_budget=100,
        )
        self.assertIsNone(result["selected"])
        self.assertEqual({x["reason"] for x in result["excluded"]},
                         {"hypothesis_mismatch", "covers_no_required_gate"})

    def test_duplicate_candidate_id_rejected(self):
        item = candidate("same", ["ood"])
        with self.assertRaisesRegex(ValueError, "duplicate candidate_id"):
            design_next_experiment(hypothesis_id="H-001", required_gates=["ood"],
                                   candidates=[item, item], compute_budget=100)

    def test_invalid_discrimination_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid cost"):
            design_next_experiment(hypothesis_id="H-001", required_gates=["ood"],
                                   candidates=[candidate("bad", ["ood"], discrimination=2)],
                                   compute_budget=100)

    def test_input_digest_is_deterministic(self):
        item = candidate("a", ["ood"])
        one = design_next_experiment(hypothesis_id="H-001", required_gates=["ood"],
                                     candidates=[item], compute_budget=100)
        two = design_next_experiment(hypothesis_id="H-001", required_gates=["ood"],
                                     candidates=[item], compute_budget=100)
        self.assertEqual(one["input_digest"], two["input_digest"])


if __name__ == "__main__":
    unittest.main()
