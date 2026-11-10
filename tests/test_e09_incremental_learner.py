import unittest

from prototype.e09_counterexample_learner import Example
from prototype.e09_incremental_learner import (
    IncrementalConjunctionLearner, IncrementalLearningError,
)


class IncrementalConjunctionLearnerTests(unittest.TestCase):
    def make_learner(self):
        learner = IncrementalConjunctionLearner(
            ((0, 1), (0, 1), (0, 1, 2)), min_support=2
        )
        for row in (
            Example((0, 0, 0), "yes"),
            Example((0, 1, 0), "yes"),
            Example((1, 0, 0), "no"),
            Example((1, 1, 0), "no"),
        ):
            learner.observe(row.inputs, row.label)
        return learner

    def test_incremental_update_invalidates_only_matching_generalizations(self):
        learner = self.make_learner()
        self.assertEqual(learner.predict((0, 0, 2)), "yes")
        before = learner.report["incremental_pattern_updates"]
        self.assertEqual(learner.observe((0, 0, 2), "no"), "ADDED")
        self.assertIsNone(learner.predict((0, 0, 2)))
        self.assertEqual(
            learner.report["incremental_pattern_updates"] - before, 8
        )

    def test_duplicate_evidence_is_idempotent(self):
        learner = self.make_learner()
        before = learner.report["incremental_pattern_updates"]
        self.assertEqual(learner.observe((0, 0, 0), "yes"), "DUPLICATE")
        self.assertEqual(learner.report["incremental_pattern_updates"], before)

    def test_conflict_retracts_prior_contribution_and_quarantines_input(self):
        learner = self.make_learner()
        self.assertEqual(learner.predict((0, 0, 2)), "yes")
        self.assertEqual(learner.observe((0, 0, 0), "no"), "CONTESTED")
        self.assertEqual(learner.report["retracted_contributions"], 1)
        self.assertEqual(learner.report["contested_inputs"], 1)
        self.assertIsNone(learner.predict((0, 0, 2)))

    def test_conflict_does_not_reintroduce_either_label(self):
        learner = self.make_learner()
        learner.observe((0, 0, 0), "no")
        self.assertEqual(learner.observe((0, 0, 0), "yes"), "DUPLICATE")
        self.assertEqual(learner.observe((0, 0, 0), "maybe"), "CONTESTED")
        self.assertEqual(learner.report["retracted_contributions"], 1)
        self.assertIsNone(learner.predict((0, 0, 0)))

    def test_rejects_invalid_domain_and_arity(self):
        learner = self.make_learner()
        with self.assertRaises(IncrementalLearningError):
            learner.observe((9, 0, 0), "no")
        with self.assertRaises(IncrementalLearningError):
            learner.predict((0, 0))

    def test_snapshot_is_deterministic(self):
        a = self.make_learner().snapshot()
        b = self.make_learner().snapshot()
        self.assertEqual(a, b)

    def test_incremental_matches_full_recompute_reference_after_every_update(self):
        from itertools import product

        domains = ((0, 1), (0, 1), (0, 1))
        learner = IncrementalConjunctionLearner(domains, min_support=2)
        stream = [
            ((0, 0, 0), "A"), ((0, 1, 0), "A"),
            ((1, 0, 0), "B"), ((1, 1, 0), "B"),
            ((0, 0, 1), "A"), ((0, 0, 1), "B"),
            ((1, 1, 1), "B"), ((1, 1, 1), "B"),
            ((0, 1, 1), "A"), ((1, 0, 1), "A"),
        ]
        seen = {}

        def reference_predict(query):
            clean = {
                inputs: next(iter(labels))
                for inputs, labels in seen.items() if len(labels) == 1
            }
            inferred = set()
            for pattern in product(*((None, *domain) for domain in domains)):
                matched = [
                    label for inputs, label in clean.items()
                    if all(want is None or want == got
                           for want, got in zip(pattern, inputs))
                ]
                if len(matched) >= 2 and len(set(matched)) == 1:
                    if all(want is None or want == got
                           for want, got in zip(pattern, query)):
                        inferred.add(matched[0])
            return next(iter(inferred)) if len(inferred) == 1 else None

        all_queries = tuple(product(*domains))
        for inputs, label in stream:
            learner.observe(inputs, label)
            seen.setdefault(inputs, set()).add(label)
            for query in all_queries:
                self.assertEqual(
                    learner.predict(query), reference_predict(query),
                    msg=f"mismatch after observing {inputs!r} -> {label!r}, query={query!r}",
                )

    def test_reversing_input_order_preserves_final_predictions(self):
        rows = [
            ((0, 0, 0), "A"), ((0, 1, 0), "A"),
            ((1, 0, 0), "B"), ((1, 1, 0), "B"),
            ((0, 0, 1), "A"),
        ]
        forward = IncrementalConjunctionLearner(((0, 1),) * 3, min_support=2)
        reverse = IncrementalConjunctionLearner(((0, 1),) * 3, min_support=2)
        for inputs, label in rows:
            forward.observe(inputs, label)
        for inputs, label in reversed(rows):
            reverse.observe(inputs, label)
        for query in __import__("itertools").product(range(2), repeat=3):
            self.assertEqual(forward.predict(query), reverse.predict(query))


if __name__ == "__main__":
    unittest.main()
