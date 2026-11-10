import unittest

from prototype.e02_rule_ood import (
    RULES, Episode, consistent_rules, infer, make_episodes, run, target_c,
)


class E02RuleOODTests(unittest.TestCase):
    def test_rule_space_and_targets(self):
        self.assertEqual(len(RULES), 27)
        for rule in RULES:
            for a in range(3):
                for b in range(3):
                    c = target_c(rule, a, b)
                    self.assertEqual((rule[0] * a + rule[1] * b + c + rule[2]) % 3, 0)

    def test_support_identifies_rule_when_sufficient(self):
        episode = Episode((1, 2, 1), ((0, 0, 2), (1, 0, 1),
                                      (0, 1, 0), (1, 1, 2),
                                      (2, 0, 0), (0, 2, 1)),
                          (2, 2))
        hypotheses = consistent_rules(episode.support)
        self.assertIn(episode.rule, hypotheses)
        result = infer(episode)
        self.assertTrue(result["identifiable"])
        self.assertTrue(result["correct"])

    def test_episodes_are_reproducible(self):
        self.assertEqual(make_episodes(9), make_episodes(9))
        self.assertNotEqual(make_episodes(9), make_episodes(10))

    def test_invalid_support_size(self):
        for n in (0, 9):
            with self.assertRaises(ValueError):
                make_episodes(1, n)

    def test_run_reports_coverage_and_accuracy(self):
        result = run(seed=17, support_size=6)
        self.assertEqual(result["episodes"], 27)
        self.assertGreaterEqual(result["identification_coverage"], 0.0)
        self.assertLessEqual(result["identification_coverage"], 1.0)
        self.assertGreaterEqual(result["accuracy_on_all_episodes"], 0.0)
        self.assertLessEqual(result["accuracy_on_all_episodes"], 1.0)


if __name__ == "__main__":
    unittest.main()
