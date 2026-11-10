import unittest

from prototype.tx02_multistate_benchmark import (
    episode_to_dict,
    make_benchmark,
    make_episode,
)


class TX02EpisodeGeneratorTests(unittest.TestCase):
    def test_cardinalities_and_episode_counts(self):
        result = make_benchmark(episodes_per_cardinality=3, seed=41)
        self.assertEqual(result["cardinalities"], [2, 3, 4, 5])
        self.assertEqual(result["episode_count"], 12)
        self.assertEqual(len(result["episodes"]), 12)

    def test_deterministic_for_same_seed(self):
        first = make_episode(3, seed=9, support_size=3, query_count=2)
        second = make_episode(3, seed=9, support_size=3, query_count=2)
        self.assertEqual(first, second)

    def test_support_and_query_pairs_are_disjoint(self):
        for k in (2, 3, 4, 5):
            episode = make_episode(k, seed=100 + k, support_size=3, query_count=2)
            support_pairs = {(row.a, row.b) for row in episode.support}
            query_pairs = set(episode.queries)
            self.assertEqual(len(query_pairs), 2)
            self.assertTrue(support_pairs.isdisjoint(query_pairs))

    def test_hidden_rule_generates_support_and_query_targets(self):
        for k in (2, 3, 4, 5):
            episode = make_episode(k, seed=500 + k,
                                   support_size=min(5, k*k - 2), query_count=2)
            alpha, beta, delta = episode.hidden_rule
            visible = episode.visible_symbols
            inverse = {symbol: canonical for canonical, symbol in enumerate(visible)}

            for row in episode.support:
                expected = visible[(alpha * inverse[row.a] +
                                   beta * inverse[row.b] + delta) % k]
                self.assertEqual(row.c, expected)

            for (a, b), candidates, target in zip(
                episode.queries, episode.candidates, episode.targets
            ):
                expected = visible[(alpha * inverse[a] +
                                    beta * inverse[b] + delta) % k]
                self.assertEqual(len(candidates), k)
                self.assertEqual(set(candidates), set(range(k)))
                self.assertEqual(candidates[target], expected)

    def test_serialized_payload_does_not_leak_hidden_rule(self):
        episode = make_episode(3, seed=77, support_size=3, query_count=2)
        payload = episode_to_dict(episode)
        self.assertNotIn("hidden_rule", payload)
        self.assertNotIn("visible_symbols", payload)

    def test_rejects_invalid_sizes(self):
        with self.assertRaises(ValueError):
            make_episode(1, seed=1, support_size=1)
        with self.assertRaises(ValueError):
            make_episode(3, seed=1, support_size=0)
        with self.assertRaises(ValueError):
            make_episode(3, seed=1, support_size=8, query_count=2)


if __name__ == "__main__":
    unittest.main()
