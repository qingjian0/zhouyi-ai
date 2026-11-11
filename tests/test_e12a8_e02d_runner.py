import unittest
from prototype.e02_rule_ood import make_episodes
from prototype.e12a8_e02d_runner import run, run_episode

class E12A8E02DRunnerTests(unittest.TestCase):
    def test_runner_scores_all_episodes_without_gold_in_learner_commit(self):
        result = run(seed=17, support_size=6)
        self.assertEqual(result["episodes"], 27)
        self.assertGreater(result["prediction_coverage"], 0)
        for row in result["episodes_detail"]:
            self.assertNotIn("gold", {
                "prediction": row["prediction"],
                "prediction_identifiable": row["prediction_identifiable"],
                "consistent_hypotheses": row["consistent_hypotheses"],
                "commit_digest": row["commit_digest"],
            })
            self.assertEqual(len(row["commit_digest"]), 64)

    def test_ambiguous_episode_abstains_instead_of_scoring_guess(self):
        episodes = make_episodes(seed=100, support_size=1)
        rows = [run_episode(ep, i) for i, ep in enumerate(episodes)]
        ambiguous = [row for row in rows if not row["prediction_identifiable"]]
        self.assertTrue(ambiguous)
        self.assertTrue(all(row["scored"] is False and row["correct"] is None
                            for row in ambiguous))

if __name__ == "__main__":
    unittest.main()
