import unittest
from dataclasses import replace

from prototype.e11a_unlabeled_concepts import (
    Episode, ObjectView, evaluate, make_episode, predict, propose_concepts, run,
)


class E11AUnlabeledConceptTests(unittest.TestCase):
    def test_reproducible_and_identity_disjoint(self):
        first = make_episode(31)
        second = make_episode(31)
        self.assertEqual(first, second)
        learner_ids = {obj.object_id for obj in first.learner_objects}
        query_ids = {obj.object_id for obj in first.query_objects}
        self.assertTrue(learner_ids.isdisjoint(query_ids))

    def test_proposal_api_has_no_truth_argument(self):
        episode = make_episode(7)
        proposals = propose_concepts(episode.learner_objects)
        self.assertTrue(proposals)
        predictions = predict(episode.query_objects, proposals)
        self.assertEqual(set(predictions), {
            obj.object_id for obj in episode.query_objects
        })

    def test_renaming_symbols_preserves_structure_and_scores(self):
        episode = make_episode(19)
        proposals = propose_concepts(episode.learner_objects)
        mapping = {
            symbol: f"opaque-{index:03d}"
            for index, symbol in enumerate(sorted({
                attr for obj in episode.learner_objects
                for attr in obj.attributes
            }))
        }
        renamed_learner = tuple(
            replace(obj, attributes=frozenset(mapping[a] for a in obj.attributes))
            for obj in episode.learner_objects
        )
        renamed_query = tuple(
            replace(obj, attributes=frozenset(
                mapping.get(a, f"unseen-{a}") for a in obj.attributes
            ))
            for obj in episode.query_objects
        )
        renamed = replace(
            episode, learner_objects=renamed_learner, query_objects=renamed_query
        )
        renamed_proposals = propose_concepts(renamed.learner_objects)
        self.assertEqual(len(proposals), len(renamed_proposals))
        original_metrics = evaluate(episode, proposals)
        renamed_metrics = evaluate(renamed, renamed_proposals)
        self.assertAlmostEqual(
            original_metrics["mean_best_query_f1"],
            renamed_metrics["mean_best_query_f1"],
        )
        self.assertAlmostEqual(
            original_metrics["mean_one_to_one_query_f1"],
            renamed_metrics["mean_one_to_one_query_f1"],
        )

    def test_input_order_does_not_change_proposals(self):
        episode = make_episode(23)
        forward = propose_concepts(episode.learner_objects)
        reverse = propose_concepts(tuple(reversed(episode.learner_objects)))
        self.assertEqual(forward, reverse)

    def test_one_candidate_cannot_be_credited_to_two_concepts(self):
        query = (
            ObjectView("q1", frozenset({"shared"})),
            ObjectView("q2", frozenset({"shared"})),
        )
        episode = Episode(
            learner_objects=(),
            query_objects=query,
            truth={"q1": frozenset({"A"}), "q2": frozenset({"B"})},
            hidden_schemas={"A": frozenset({"a"}), "B": frozenset({"b"})},
        )
        result = evaluate(episode, (("shared",),))
        self.assertAlmostEqual(result["mean_best_query_f1"], 2.0 / 3.0)
        self.assertAlmostEqual(result["mean_one_to_one_query_f1"], 1.0 / 3.0)
        self.assertEqual(result["matched_candidate_count"], 1)
        self.assertEqual(result["one_to_one_concept_recall"], 0.5)

    def test_duplicate_candidate_extensions_do_not_inflate_concept_count(self):
        query = (
            ObjectView("q1", frozenset({"x", "z"})),
            ObjectView("q2", frozenset({"x", "z"})),
            ObjectView("q3", frozenset({"other"})),
        )
        episode = Episode(
            learner_objects=(),
            query_objects=query,
            truth={"q1": frozenset({"A"}), "q2": frozenset({"A"}),
                   "q3": frozenset({"B"})},
            hidden_schemas={"A": frozenset({"a"}), "B": frozenset({"b"})},
        )
        result = evaluate(episode, (("x",), ("x", "z")))
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["unique_candidate_extension_count"], 1)

    def test_invalid_parameters_fail_closed(self):
        episode = make_episode(3)
        for value in (0.0, 1.1):
            with self.assertRaises(ValueError):
                propose_concepts(episode.learner_objects, min_support=value)
        for value in (0, 5):
            with self.assertRaises(ValueError):
                propose_concepts(episode.learner_objects, max_order=value)

    def test_run_reports_scope_and_valid_metrics(self):
        result = run(seed=17, object_count=120)
        self.assertTrue(result["object_identity_disjoint"])
        self.assertGreater(result["candidate_count"], 0)
        self.assertGreaterEqual(result["mean_best_query_f1"], 0.0)
        self.assertLessEqual(result["mean_best_query_f1"], 1.0)
        self.assertGreaterEqual(result["mean_one_to_one_query_f1"], 0.0)
        self.assertLessEqual(result["mean_one_to_one_query_f1"], 1.0)
        self.assertEqual(len(result["per_concept"]), 3)


if __name__ == "__main__":
    unittest.main()
