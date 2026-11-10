import unittest

from prototype.e02i_relation_evolution import (
    RelationEvolution, Snapshot, run_episode,
)


class E02IRelationEvolutionTests(unittest.TestCase):
    def test_requires_repeated_confirmation_before_reconfiguration(self):
        state = RelationEvolution(confirm_windows=2)
        a = Snapshot((0, 1, 2), 173, 0.98, 0.70)
        b = Snapshot((0, 1, 3), 173, 0.97, 0.68)
        self.assertEqual(state.observe(a, window=0), "CREATE")
        self.assertEqual(state.observe(b, window=1), "HOLD_PENDING")
        self.assertEqual(state.current.signature, a.signature)
        self.assertEqual(state.observe(b, window=2), "RECONFIGURE")
        self.assertEqual(state.current.signature, b.signature)

    def test_one_bad_window_degrades_but_does_not_delete(self):
        state = RelationEvolution(retire_windows=2)
        good = Snapshot((0, 1, 2), 173, 0.98, 0.70)
        bad = Snapshot((0, 1, 2), 173, 0.52, 0.50)
        self.assertEqual(state.observe(good, window=0), "CREATE")
        self.assertEqual(state.observe(bad, window=1), "DEGRADE")
        self.assertIsNotNone(state.current)
        self.assertEqual(state.observe(bad, window=2), "RETIRE")
        self.assertIsNone(state.current)

    def test_stable_relation_is_not_reconfigured(self):
        result = run_episode(seed=31, scenario="stable")
        self.assertEqual(result["windows"][0]["action"], "CREATE")
        self.assertTrue(all(w["action"] == "KEEP" for w in result["windows"][1:]))

    def test_member_and_rule_changes_require_confirmed_reconfiguration(self):
        for scenario in ("member_add", "member_remove", "rule_change"):
            with self.subTest(scenario=scenario):
                result = run_episode(seed=47, scenario=scenario)
                actions = [w["action"] for w in result["windows"]]
                self.assertEqual(actions[0], "CREATE")
                self.assertIn("HOLD_PENDING", actions)
                self.assertIn("RECONFIGURE", actions)

    def test_single_window_rule_shock_does_not_reconfigure(self):
        result = run_episode(seed=61, scenario="transient_rule_change")
        actions = [w["action"] for w in result["windows"]]
        self.assertEqual(actions[0:2], ["CREATE", "KEEP"])
        self.assertIn("HOLD_PENDING", actions)
        self.assertNotIn("RECONFIGURE", actions)
        self.assertEqual(actions[-1], "KEEP")


    def test_gate_controls_decisions_but_independent_test_split_is_audit_only(self):
        result = run_episode(seed=83, scenario="stable")
        self.assertTrue(all(w["split_ids_disjoint"] for w in result["windows"]))
        self.assertTrue(all("candidate_test_accuracy" in w for w in result["windows"]))
        self.assertTrue(all("persistent_test_accuracy" in w for w in result["windows"]))
        self.assertTrue(all("pairwise_test_accuracy" in w for w in result["windows"]))
        self.assertTrue(all(w["action"] == "KEEP" for w in result["windows"][1:]))
        self.assertTrue(all(w["persistent_test_accuracy"] is not None
                            for w in result["windows"]))


    def test_pending_candidate_is_not_scored_as_persistent_relation(self):
        result = run_episode(seed=47, scenario="member_add")
        pending = next(w for w in result["windows"] if w["action"] == "HOLD_PENDING")
        self.assertNotEqual(pending["candidate_members"], pending["persistent_members"])
        self.assertIsNotNone(pending["persistent_test_accuracy"])
        changed = next(w for w in result["windows"] if w["action"] == "RECONFIGURE")
        self.assertEqual(changed["candidate_members"], changed["persistent_members"])

    def test_disappearing_relation_is_retired_after_two_failed_windows(self):
        result = run_episode(seed=53, scenario="disappear")
        actions = [w["action"] for w in result["windows"]]
        self.assertEqual(actions[:2], ["CREATE", "KEEP"])
        self.assertIn("RETIRE", actions)


if __name__ == "__main__":
    unittest.main()
