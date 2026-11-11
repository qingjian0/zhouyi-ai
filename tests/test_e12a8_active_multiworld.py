import unittest

from prototype.e12a7_multiworld import MECHANISMS, SyntheticWorld
from prototype.e12a8_active_multiworld import (
    PrequentialExperimentLedger,
    _predicted_outcome,
    evaluate_policy,
    likelihoods,
    make_actions,
    run_episode,
    select_action,
)


class E12A8ActiveMultiworldTests(unittest.TestCase):
    def test_passive_observations_cannot_separate_direct_from_confounding(self):
        prior = {"direct": 0.5, "confounded": 0.5}
        actions = make_actions(include_interventions=False)
        for action in actions:
            self.assertEqual(
                _predicted_outcome("direct", action),
                _predicted_outcome("confounded", action),
            )
            table = likelihoods(prior, action)
            self.assertEqual(table["direct"], table["confounded"])

    def test_active_selector_prefers_intervention_for_direct_vs_confounding(self):
        prior = {"direct": 0.5, "confounded": 0.5}
        actions = make_actions(include_interventions=True)
        choice = select_action(prior, actions, remaining_budget=2.0)
        self.assertEqual(choice["status"], "SELECTED")
        selected = next(a for a in actions if a.action_id == choice["selected"])
        self.assertTrue(selected.intervention)

    def test_commit_precedes_reveal_and_updates_posterior(self):
        ledger = PrequentialExperimentLedger({"direct": 0.5, "inverse": 0.5})
        action = next(a for a in make_actions() if a.intervention and a.x == 1
                      and a.context == 0 and a.time == 0)
        ledger.commit(action)
        self.assertEqual(ledger.events[0]["phase"], "COMMIT")
        result = ledger.reveal(action.action_id, 1)
        self.assertEqual(result["status"], "UPDATED")
        self.assertGreater(ledger.posterior["direct"], ledger.posterior["inverse"])
        self.assertEqual(ledger.events[1]["phase"], "REVEAL")

    def test_reveal_without_commit_is_rejected(self):
        ledger = PrequentialExperimentLedger({"direct": 1.0})
        with self.assertRaises(ValueError):
            ledger.reveal("not-committed", 1)

    def test_duplicate_commit_and_duplicate_reveal_are_rejected(self):
        ledger = PrequentialExperimentLedger({"direct": 1.0})
        action = make_actions()[0]
        ledger.commit(action)
        with self.assertRaises(ValueError):
            ledger.commit(action)
        ledger.reveal(action.action_id, 0)
        with self.assertRaises(ValueError):
            ledger.reveal(action.action_id, 0)

    def test_missing_observation_does_not_change_posterior(self):
        ledger = PrequentialExperimentLedger({"direct": 0.5, "inverse": 0.5})
        action = make_actions()[0]
        ledger.commit(action)
        before = dict(ledger.posterior)
        result = ledger.reveal(action.action_id, None)
        self.assertEqual(result["status"], "MISSING")
        self.assertEqual(ledger.posterior, before)

    def test_budget_excludes_unaffordable_interventions(self):
        prior = {"direct": 0.5, "confounded": 0.5}
        actions = make_actions(include_interventions=True)
        choice = select_action(prior, actions, remaining_budget=1.0)
        self.assertEqual(choice["status"], "NO_DISCRIMINATING_ACTION")
        self.assertIsNone(choice["selected"])

    def test_policy_runner_never_exposes_truth_in_learner_result(self):
        world = SyntheticWorld("private-world-name", "direct")
        result = run_episode(world, policy="active", budget=4.0, max_steps=3)
        self.assertNotIn("truth", result)
        self.assertNotIn("mechanism", result)
        self.assertEqual(result["events"][0]["phase"], "COMMIT")
        self.assertEqual(result["events"][1]["phase"], "REVEAL")

    def test_evaluator_compares_active_random_and_fixed_on_same_worlds(self):
        worlds = [
            SyntheticWorld("w-direct", "direct"),
            SyntheticWorld("w-inverse", "inverse"),
            SyntheticWorld("w-confounded", "confounded"),
        ]
        result = evaluate_policy(worlds, seeds=(0, 1), budget=8.0)
        self.assertEqual(set(result["policies"]), {"active", "random", "fixed"})
        for metrics in result["policies"].values():
            self.assertEqual(len(metrics["episodes"]), 6)
            self.assertGreaterEqual(metrics["accuracy"], 0.0)
            self.assertLessEqual(metrics["accuracy"], 1.0)

    def test_prior_must_be_valid(self):
        with self.assertRaises(ValueError):
            select_action({"not-a-mechanism": 1.0}, make_actions(), 2.0)

    def test_invalid_action_cost_and_non_integer_outcome_are_rejected(self):
        from prototype.e12a8_active_multiworld import ExperimentAction
        ledger = PrequentialExperimentLedger({"direct": 1.0})
        invalid = ExperimentAction("bad", True, 0, 0, 0, float("nan"))
        with self.assertRaises(ValueError):
            ledger.commit(invalid)
        action = make_actions()[0]
        ledger.commit(action)
        with self.assertRaises(ValueError):
            ledger.reveal(action.action_id, 1.0)

    def test_invalid_episode_limits_are_rejected(self):
        world = SyntheticWorld("w", "direct")
        for kwargs in (
            {"budget": -1.0},
            {"max_steps": -1},
            {"confidence_threshold": 0.0},
            {"confidence_threshold": 1.1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    run_episode(world, **kwargs)


if __name__ == "__main__":
    unittest.main()
