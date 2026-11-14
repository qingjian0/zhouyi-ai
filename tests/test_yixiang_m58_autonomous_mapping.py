import unittest

from prototype.yixiang_m57_nonpath_benchmark import generate_dataset
from prototype.yixiang_m58_autonomous_mapping import enumerate_mappings, predict


class M58AutonomousMappingTests(unittest.TestCase):
    def test_full_solver_recovers_mapping_without_candidate_list(self):
        cases, truth = generate_dataset(count=90, seed=5801)
        for case in cases:
            public_case = dict(case)
            public_case.pop("candidate_mappings")
            result = enumerate_mappings(public_case, mode="full_constraints")
            self.assertEqual(result["status"], "unique", case["case_id"])
            expected_id = truth[case["case_id"]]["correct_candidate_id"]
            expected_index = int(expected_id.split("-")[1])
            self.assertEqual(
                result["solutions"][0],
                case["candidate_mappings"][expected_index],
                case["case_id"],
            )

    def test_path_only_cannot_resolve_hard_cases(self):
        cases, _ = generate_dataset(count=90, seed=5802)
        hard = [c for c in cases if c["difficulty"] in ("compositional", "nonpath")]
        for case in hard:
            public_case = dict(case)
            public_case.pop("candidate_mappings")
            result = enumerate_mappings(public_case, mode="path_only")
            self.assertEqual(result["status"], "ambiguous", case["case_id"])

    def test_solver_does_not_require_or_read_candidate_mappings(self):
        cases, _ = generate_dataset(count=30, seed=5803)
        case = dict(cases[-1])
        case.pop("candidate_mappings")
        prediction = predict(case)
        self.assertEqual(prediction["status"], "unique")
        self.assertIsInstance(prediction["mapping"], dict)

    def test_search_budget_is_explicit(self):
        cases, _ = generate_dataset(count=30, seed=5804)
        result = enumerate_mappings(cases[-1], max_states=1)
        self.assertEqual(result["status"], "budget_exhausted")


if __name__ == "__main__":
    unittest.main()
