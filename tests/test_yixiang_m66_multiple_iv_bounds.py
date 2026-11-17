import itertools
import unittest

from prototype.yixiang_m66_multiple_iv_bounds import bounded_multiple_iv_effect_set


def make_case(confounded_second=False):
    observed = ["Z1", "Z2", "X", "Y"]
    joint = {}
    for z1, z2, x, y in itertools.product((0, 1), repeat=4):
        pz = 0.25
        px = 0.2 + 0.2 * z1 + 0.2 * z2
        py = 0.1 + 0.3 * x + 0.1 * z1 + 0.05 * z2
        joint[f"{z1},{z2},{x},{y}"] = (
            pz * (px if x else 1-px) * (py if y else 1-py)
        )
    edges = [
        ["Z1", "X"], ["Z2", "X"], ["X", "Y"],
        ["Z1", "Y"], ["Z2", "Y"],
    ]
    nodes = ["Z1", "Z2", "X", "Y"]
    if confounded_second:
        nodes.append("U")
        edges.extend([["U", "Z2"], ["U", "Y"]])
        # This fixture's observed law is retained only as a gate test: the
        # graph screen must exclude Z2 despite its observed first-stage link.
    return {
        "dag": {"nodes": nodes, "edges": edges},
        "observed_variables": observed,
        "instrument_candidates": ["Z1", "Z2"],
        "query": {"exposure": "X", "outcome": "Y"},
        "observational_joint": joint,
    }


class M66MultipleIVBoundsTests(unittest.TestCase):
    def test_multiple_instruments_intersect_bounded_violation_intervals(self):
        result = bounded_multiple_iv_effect_set(make_case(), 0.1)
        self.assertEqual(
            result["status"],
            "bounded_multiple_iv_effect_set_under_linear_moment_assumptions",
        )
        self.assertAlmostEqual(result["identified_set"][0], 0.3, places=8)
        self.assertAlmostEqual(result["identified_set"][1], 1.05, places=8)
        self.assertEqual(result["instruments"], ["Z1", "Z2"])

    def test_zero_violation_bound_requires_common_exact_ratio(self):
        result = bounded_multiple_iv_effect_set(make_case(), 0.0)
        self.assertEqual(
            result["status"], "incompatible_with_declared_violation_bounds"
        )

    def test_graph_confounded_candidate_is_excluded(self):
        result = bounded_multiple_iv_effect_set(make_case(True), 0.1)
        self.assertEqual(result["instruments"], ["Z1"])
        self.assertEqual(
            result["instrument_screen"][1]["status"], "excluded_by_graph_screen"
        )

    def test_negative_nonfinite_and_missing_bounds_are_rejected(self):
        case = make_case()
        for bound in (-0.1, float("inf"), float("nan"), {"Z1": 0.1}):
            with self.subTest(bound=bound):
                with self.assertRaises(ValueError):
                    bounded_multiple_iv_effect_set(case, bound)

    def test_singular_instrument_covariance_is_rejected(self):
        case = make_case()
        # Make Z2 an exact duplicate of Z1 in the observational support.
        joint = {}
        for z1, x, y in itertools.product((0, 1), repeat=3):
            pz = 0.5
            px = 0.2 + 0.4 * z1
            py = 0.1 + 0.3 * x + 0.15 * z1
            joint[f"{z1},{z1},{x},{y}"] = pz * (px if x else 1-px) * (py if y else 1-py)
        case["observational_joint"] = joint
        result = bounded_multiple_iv_effect_set(case, 0.1)
        self.assertEqual(result["status"], "singular_instrument_covariance_matrix")

    def test_weak_conditional_first_stage_abstains(self):
        case = make_case()
        # Set X independent of both instruments in the joint distribution.
        joint = {}
        for z1, z2, x, y in itertools.product((0, 1), repeat=4):
            px, py = 0.5, 0.1 + 0.3*x + 0.1*z1 + 0.05*z2
            joint[f"{z1},{z2},{x},{y}"] = 0.25 * 0.5 * (py if y else 1-py)
        case["observational_joint"] = joint
        result = bounded_multiple_iv_effect_set(case, 0.1)
        self.assertEqual(
            result["status"], "weak_or_irrelevant_conditional_first_stage"
        )


if __name__ == "__main__":
    unittest.main()
