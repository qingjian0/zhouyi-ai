import unittest

from prototype.e02i2_hidden_identity import (
    SCENARIOS,
    evaluate,
    generate_episode,
)
from prototype.e02i2_matching import MatchingMethod, match_candidates


class HiddenIdentityBenchmarkTests(unittest.TestCase):
    def test_generator_keeps_truth_out_of_observed_candidate_objects(self):
        episode = generate_episode("stable", 7000)
        candidate = episode.candidates[0]
        self.assertFalse(hasattr(candidate, "identity_id"))
        self.assertFalse(hasattr(candidate, "hidden_truth"))
        self.assertEqual(set(episode.hidden_truth), {candidate.candidate_id})
        self.assertNotIn(episode.hidden_truth[candidate.candidate_id], candidate.__dict__.values())

    def test_role_permutation_preserves_latent_identity(self):
        episode = generate_episode("role_permutation", 7001)
        decisions = match_candidates(
            episode.candidates, dict(episode.history),
            method=MatchingMethod.ROLE_ALIGNED,
        )
        self.assertEqual(decisions[0].identity_id, episode.hidden_truth[decisions[0].candidate_id])

    def test_same_members_different_rule_is_a_new_identity(self):
        episode = generate_episode("same_members_new_semantics", 7002)
        exact = match_candidates(
            episode.candidates, dict(episode.history),
            method=MatchingMethod.EXACT,
        )[0]
        jaccard = match_candidates(
            episode.candidates, dict(episode.history),
            method=MatchingMethod.JACCARD, min_score=0.70, min_margin=0.05,
        )[0]
        self.assertTrue(exact.abstained)
        self.assertFalse(jaccard.abstained)
        self.assertEqual(jaccard.identity_id, "hist-A")

    def test_role_aligned_and_hungarian_abstain_on_new_semantics(self):
        episode = generate_episode("same_members_new_semantics", 7002)
        for method in (MatchingMethod.ROLE_ALIGNED, MatchingMethod.HUNGARIAN):
            decision = match_candidates(
                episode.candidates, dict(episode.history), method=method,
            )[0]
            self.assertTrue(decision.abstained, method.value)
        weak = match_candidates(
            episode.candidates, dict(episode.history),
            method=MatchingMethod.JACCARD,
        )[0]
        self.assertEqual(weak.identity_id, "hist-A")

    def test_indistinguishable_identities_require_abstention(self):
        episode = generate_episode("indistinguishable", 7003)
        for method in MatchingMethod:
            decision = match_candidates(
                episode.candidates, dict(episode.history), method=method,
            )[0]
            self.assertTrue(decision.abstained, method.value)

    def test_dropout_is_not_counted_as_retirement(self):
        episode = generate_episode("temporary_dropout", 7004)
        self.assertEqual(episode.candidates, ())
        self.assertEqual(episode.hidden_truth, {})
        self.assertEqual(len(episode.history), 1)

    def test_benchmark_is_deterministic_and_covers_all_scenarios(self):
        first = evaluate(MatchingMethod.ROLE_ALIGNED, seeds=3, start_seed=9000)
        second = evaluate(MatchingMethod.ROLE_ALIGNED, seeds=3, start_seed=9000)
        self.assertEqual(first, second)
        self.assertEqual(set(first["by_scenario"]), set(SCENARIOS))
        self.assertEqual(first["totals"]["dropout_episodes"], 3)


if __name__ == "__main__":
    unittest.main()
