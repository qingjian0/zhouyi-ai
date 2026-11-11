import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from orchestrator.agents.experiment_registry import (
    ExperimentRegistry, ExperimentResult, ExperimentSpec,
)


def make_spec(experiment_id="exp-001", **overrides):
    values = dict(
        experiment_id=experiment_id,
        hypothesis="Parallel composition improves OOD composition accuracy",
        method="parallel-composition-v1",
        model_id="cpg-ei-prototype",
        model_version="0.1.0",
        dataset_id="composition-ood",
        dataset_version="v3",
        dataset_digest="a" * 64,
        code_revision="abcdef0123456789",
        seed=17,
        environment={"python": "3.11", "platform": "linux", "device": "cpu"},
        budget={"steps": 1000, "wall_seconds": 300},
        created_at="2026-11-11T02:00:00+00:00",
        baseline_id="transformer-baseline",
        comparison_group="ood-composition-v1",
        config={"beam_width": 8, "skip_intermediate": True},
    )
    values.update(overrides)
    return ExperimentSpec(**values)


class ExperimentRegistryTests(unittest.TestCase):
    def test_register_and_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = ExperimentRegistry(Path(temp) / "experiments.sqlite3")
            spec = make_spec()
            digest = registry.register(spec)
            self.assertEqual(len(digest), 64)
            self.assertEqual(registry.get_spec(spec.experiment_id), spec)
            self.assertIsNone(registry.get_result(spec.experiment_id))
            self.assertEqual(registry.list_experiment_ids(), ("exp-001",))

    def test_duplicate_spec_is_rejected_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = ExperimentRegistry(Path(temp) / "db.sqlite3")
            registry.register(make_spec())
            with self.assertRaisesRegex(ValueError, "already registered"):
                registry.register(make_spec(hypothesis="different"))

    def test_result_is_append_only_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = ExperimentRegistry(Path(temp) / "db.sqlite3")
            registry.register(make_spec())
            result = ExperimentResult(
                experiment_id="exp-001", status="completed",
                metrics={"accuracy": 0.82, "latency_ms": 12.5},
                completed_at="2026-11-11T02:05:00+00:00",
            )
            digest = registry.record_result(result)
            self.assertEqual(len(digest), 64)
            self.assertEqual(registry.get_result("exp-001"), result)
            with self.assertRaisesRegex(ValueError, "already recorded"):
                registry.record_result(result)

    def test_result_requires_registered_spec(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = ExperimentRegistry(Path(temp) / "db.sqlite3")
            result = ExperimentResult(
                experiment_id="missing", status="failed", metrics={},
                completed_at="2026-11-11T02:05:00+00:00",
            )
            with self.assertRaisesRegex(KeyError, "not registered"):
                registry.record_result(result)

    def test_invalid_reproducibility_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "dataset_digest"):
            make_spec(dataset_digest="bad")
        with self.assertRaisesRegex(ValueError, "code_revision"):
            make_spec(code_revision="not-a-commit")
        with self.assertRaisesRegex(ValueError, "timezone"):
            make_spec(created_at="2026-11-11T02:00:00")
        with self.assertRaisesRegex(ValueError, "seed"):
            make_spec(seed=-1)
        with self.assertRaisesRegex(ValueError, "budget"):
            make_spec(budget={"steps": float("nan")})

    def test_non_finite_metrics_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite number"):
            ExperimentResult(
                experiment_id="exp", status="completed",
                metrics={"accuracy": float("nan")},
                completed_at="2026-11-11T02:05:00+00:00",
            )

    def test_spec_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "db.sqlite3"
            registry = ExperimentRegistry(path)
            registry.register(make_spec())
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute("UPDATE experiments SET spec_json = ? WHERE experiment_id = ?",
                               ('{"tampered":true}', "exp-001"))
            with self.assertRaisesRegex(ValueError, "integrity"):
                registry.get_spec("exp-001")

    def test_unknown_experiment_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = ExperimentRegistry(Path(temp) / "db.sqlite3")
            with self.assertRaisesRegex(KeyError, "not found"):
                registry.get_spec("missing")


if __name__ == "__main__":
    unittest.main()
