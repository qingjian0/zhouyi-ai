import unittest

from orchestrator.core.experiment_matrix import ExperimentMatrix
from orchestrator.core.scheduler import TaskGraph


class ExperimentMatrixTests(unittest.TestCase):
    def make_matrix(self, **overrides):
        values = {
            "experiment": "primitive-induction-v1",
            "handler": "run_trial",
            "seeds": (11, 23),
            "conditions": ("baseline", "yijing_prior"),
            "tracks": ("binary", "ternary"),
            "payload": {"dataset": "toy-v1", "budget": 100},
        }
        values.update(overrides)
        return ExperimentMatrix(**values)

    def test_cartesian_expansion_count_and_order(self):
        matrix = self.make_matrix()
        tasks = matrix.to_tasks()
        self.assertEqual(matrix.task_count, 8)
        self.assertEqual(len(tasks), 8)
        self.assertEqual(
            [(t.payload["track"], t.payload["condition"], t.payload["seed"]) for t in tasks[:4]],
            [
                ("binary", "baseline", 11),
                ("binary", "baseline", 23),
                ("binary", "yijing_prior", 11),
                ("binary", "yijing_prior", 23),
            ],
        )
        TaskGraph(tasks)  # Expanded tasks must be accepted by the scheduler graph.

    def test_digest_is_stable_and_sensitive_to_manifest_changes(self):
        first = self.make_matrix()
        second = self.make_matrix()
        changed = self.make_matrix(seeds=(11, 23, 47))
        self.assertEqual(first.digest, second.digest)
        self.assertNotEqual(first.digest, changed.digest)

    def test_input_order_is_part_of_manifest_identity(self):
        first = self.make_matrix(seeds=(11, 23))
        reordered = self.make_matrix(seeds=(23, 11))
        self.assertNotEqual(first.digest, reordered.digest)

    def test_invalid_seeds_rejected(self):
        for seeds in ((), (True,), (-1,), (1, 1), ("1",)):
            with self.subTest(seeds=seeds):
                with self.assertRaises(ValueError):
                    self.make_matrix(seeds=seeds)

    def test_duplicate_or_empty_dimensions_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            self.make_matrix(tracks=("binary", "binary"))
        with self.assertRaisesRegex(ValueError, "non-empty"):
            self.make_matrix(conditions=())

    def test_payload_must_be_finite_json(self):
        with self.assertRaisesRegex(ValueError, "finite JSON"):
            self.make_matrix(payload={"bad": float("nan")})

    def test_each_task_receives_an_independent_payload_copy(self):
        tasks = self.make_matrix().to_tasks()
        tasks[0].payload["payload"]["budget"] = 1
        self.assertEqual(tasks[1].payload["payload"]["budget"], 100)


if __name__ == "__main__":
    unittest.main()
