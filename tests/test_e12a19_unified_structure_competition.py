import inspect
import unittest

from prototype.e12a19_unified_structure_competition import (
    Budget, Edge, Example, Node, SplitManifest, compete,
)


def make_example(prefix, i, outcome):
    if outcome == "yes":
        atoms = ("a", "b")
        nodes = (Node("c", "context"), Node("x", "signal"), Node("y", "resource"))
        edges = (Edge("c", "activates", "x", "cold->warm"),
                 Edge("c", "recruits", "y", "idle->active"),
                 Edge("x", "supports", "y"))
    else:
        atoms = ("c",)
        nodes = (Node("c", "context"), Node("x", "signal"), Node("y", "resource"))
        edges = (Edge("x", "blocks", "c"),)
    return Example(f"{prefix}-{i:02d}", atoms, nodes, edges, outcome)


def dataset():
    train = tuple(make_example("train", i, "yes" if i % 2 == 0 else "no")
                  for i in range(24))
    validation = tuple(make_example("validation", i, "yes" if i % 2 == 0 else "no")
                       for i in range(8))
    locked = tuple(f"locked-{i:02d}" for i in range(6))
    manifest = SplitManifest(
        tuple(sorted(x.observation_id for x in train)),
        tuple(sorted(x.observation_id for x in validation)),
        locked, ("no", "yes"))
    return train, validation, manifest


class UnifiedStructureCompetitionTests(unittest.TestCase):
    def test_all_families_use_shared_evaluator(self):
        train, validation, manifest = dataset()
        result = compete(train, validation, manifest,
                         budget=Budget(max_candidates_per_family=500))
        self.assertEqual([x.family for x in result.families],
                         ["SPARSE_CONJUNCTION", "TYPED_PATH", "FORK_JOIN"])
        self.assertTrue(all(x.best_candidate_key for x in result.families))
        self.assertTrue(all(x.validation is not None for x in result.families))
        self.assertLess(result.baseline.log_loss, 1.0)

    def test_split_manifest_is_shared_and_locked_test_is_only_metadata(self):
        train, validation, manifest = dataset()
        result = compete(train, validation, manifest)
        self.assertEqual(result.split_digest, manifest.digest)
        self.assertEqual(result.train_ids, manifest.train_ids)
        self.assertEqual(result.validation_ids, manifest.validation_ids)
        self.assertEqual(result.locked_test_ids, manifest.locked_test_ids)
        self.assertNotIn("locked_test_examples", inspect.signature(compete).parameters)

    def test_training_order_does_not_change_results(self):
        train, validation, manifest = dataset()
        a = compete(train, validation, manifest)
        b = compete(tuple(reversed(train)), tuple(reversed(validation)), manifest)
        self.assertEqual(a, b)

    def test_candidate_budget_is_enforced_per_family(self):
        train, validation, manifest = dataset()
        result = compete(train, validation, manifest,
                         budget=Budget(max_candidates_per_family=1))
        self.assertTrue(all(x.evaluated_candidate_count <= 1 for x in result.families))
        self.assertTrue(any(x.truncated for x in result.families))

    def test_predicate_evaluation_budget_is_enforced(self):
        train, validation, manifest = dataset()
        result = compete(train, validation, manifest,
                         budget=Budget(max_predicate_evaluations_per_family=1))
        self.assertTrue(all(x.truncated for x in result.families))
        self.assertTrue(all(x.evaluated_candidate_count == 0 for x in result.families))

    def test_validation_only_atom_does_not_enter_candidate_universe(self):
        train, validation, manifest = dataset()
        changed = list(validation)
        row = changed[0]
        changed[0] = Example(row.observation_id, ("validation_only",), row.nodes,
                            row.edges, row.outcome)
        result = compete(train, changed, manifest)
        sparse = next(x for x in result.families if x.family == "SPARSE_CONJUNCTION")
        # The training vocabulary is exactly {a,b,c}; no validation-only candidate is proposed.
        self.assertEqual(sparse.generated_candidate_count, 7)

    def test_manifest_mismatch_is_rejected(self):
        train, validation, manifest = dataset()
        bad = SplitManifest(manifest.train_ids[:-1], manifest.validation_ids,
                            manifest.locked_test_ids, manifest.outcome_vocabulary)
        with self.assertRaises(ValueError):
            compete(train, validation, bad)

    def test_split_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            SplitManifest(("a",), ("a",), ("z",), ("no", "yes"))

    def test_unknown_outcome_is_rejected(self):
        train, validation, manifest = dataset()
        bad = list(validation)
        row = bad[0]
        bad[0] = Example(row.observation_id, row.atoms, row.nodes, row.edges, "unknown")
        with self.assertRaises(ValueError):
            compete(train, bad, manifest)


if __name__ == "__main__":
    unittest.main()
