"""Independent exact-enumeration checks for the E12-A2-M selector.

The oracle below uses the joint-distribution definition of mutual information,
not the production implementation's posterior-entropy calculation.
"""
import itertools
import math
import unittest

from prototype.e12a2_active_measurement_selector import (
    expected_information_gain,
    select_measurement,
)


def exact_mutual_information(weights, likelihoods):
    """Compute I(H; O) directly from p(h, o), in bits."""
    total = float(sum(weights.values()))
    prior = {h: w / total for h, w in weights.items()}
    outcomes = tuple(next(iter(likelihoods.values())))
    p_outcome = {
        o: sum(prior[h] * likelihoods[h][o] for h in prior)
        for o in outcomes
    }
    result = 0.0
    for h in prior:
        for o in outcomes:
            joint = prior[h] * likelihoods[h][o]
            if joint > 0.0 and p_outcome[o] > 0.0:
                result += joint * math.log2(joint / (prior[h] * p_outcome[o]))
    return result


class ExactOracleTests(unittest.TestCase):
    def test_binary_likelihood_grid_matches_independent_joint_oracle(self):
        weights = {"h0": 0.2, "h1": 0.3, "h2": 0.5}
        grid = (0.0, 0.25, 0.5, 0.75, 1.0)
        checked = 0
        for probabilities in itertools.product(grid, repeat=3):
            likelihoods = {
                h: {"yes": p, "no": 1.0 - p}
                for h, p in zip(weights, probabilities)
            }
            actual = expected_information_gain(weights, likelihoods)
            expected = exact_mutual_information(weights, likelihoods)
            self.assertAlmostEqual(actual, expected, places=11)
            checked += 1
        self.assertEqual(checked, 125)

    def test_selector_matches_exact_best_cost_normalized_action(self):
        weights = {"h0": 0.15, "h1": 0.35, "h2": 0.5}
        actions = {
            "a": {
                "h0": {"y": 1.0, "n": 0.0},
                "h1": {"y": 0.5, "n": 0.5},
                "h2": {"y": 0.0, "n": 1.0},
            },
            "b": {
                "h0": {"y": 0.8, "n": 0.2},
                "h1": {"y": 0.2, "n": 0.8},
                "h2": {"y": 0.1, "n": 0.9},
            },
            "c": {
                "h0": {"y": 0.6, "n": 0.4},
                "h1": {"y": 0.6, "n": 0.4},
                "h2": {"y": 0.6, "n": 0.4},
            },
        }
        costs = {"a": 2.0, "b": 1.0, "c": 0.5}
        epsilon = 1e-9
        oracle_scores = {
            action: exact_mutual_information(weights, likelihoods)
            / (costs[action] + epsilon)
            for action, likelihoods in actions.items()
        }
        expected_action = min(
            oracle_scores,
            key=lambda action: (-oracle_scores[action], costs[action], action),
        )
        result = select_measurement(weights, actions, costs, 2.0)
        self.assertEqual(result["status"], "SELECTED")
        self.assertEqual(result["selected_action"], expected_action)

    def test_candidate_and_action_mapping_order_does_not_change_choice(self):
        weights = {"h0": 0.2, "h1": 0.3, "h2": 0.5}
        actions = {
            "z": {
                "h0": {"yes": 1.0, "no": 0.0},
                "h1": {"yes": 0.0, "no": 1.0},
                "h2": {"yes": 0.5, "no": 0.5},
            },
            "a": {
                "h0": {"yes": 0.8, "no": 0.2},
                "h1": {"yes": 0.2, "no": 0.8},
                "h2": {"yes": 0.4, "no": 0.6},
            },
        }
        costs = {"z": 1.0, "a": 1.0}
        baseline = select_measurement(weights, actions, costs, 1.0)
        reversed_weights = dict(reversed(list(weights.items())))
        reversed_actions = {
            action: dict(reversed(list(by_h.items())))
            for action, by_h in reversed(list(actions.items()))
        }
        reversed_costs = dict(reversed(list(costs.items())))
        permuted = select_measurement(
            reversed_weights, reversed_actions, reversed_costs, 1.0
        )
        self.assertEqual(permuted["status"], baseline["status"])
        self.assertEqual(permuted["selected_action"], baseline["selected_action"])
        self.assertAlmostEqual(
            permuted["expected_information_gain_bits"],
            baseline["expected_information_gain_bits"],
            places=12,
        )

    def test_observational_equivalence_has_exactly_zero_information(self):
        weights = {"h0": 0.1, "h1": 0.2, "h2": 0.7}
        same = {
            h: {"x": 0.25, "y": 0.75}
            for h in weights
        }
        self.assertAlmostEqual(exact_mutual_information(weights, same), 0.0)
        self.assertAlmostEqual(expected_information_gain(weights, same), 0.0)
        result = select_measurement(weights, {"same": same}, {"same": 1.0}, 1.0)
        self.assertEqual(result["status"], "NO_DISCRIMINATING_ACTION")


if __name__ == "__main__":
    unittest.main()
