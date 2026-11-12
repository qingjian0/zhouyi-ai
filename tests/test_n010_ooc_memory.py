"""Subprocess RSS scaling check for the disk-indexed N0.10 reader."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from prototype.n09_learnable_srok import RoleSpec


def _write_dataset(path: Path, count: int) -> None:
    with path.open("w", encoding="utf-8") as output:
        for index in range(count):
            nodes = []
            targets = []
            for role in ("r0", "r1"):
                target = f"{index}-{role}"
                targets.append(target)
                nodes.append({
                    "node_id": target,
                    "node_type": role,
                    "features": [1.0],
                    "tags": ["eligible"],
                    "evidence_ids": [],
                })
            output.write(json.dumps({
                "id": f"row-{index}",
                "split": "train",
                "rule_family": "family-A",
                "group_id": f"source-{index // 2}",
                "nodes": nodes,
                "target_ids": targets,
            }, separators=(",", ":")) + "\n")


def _measure_in_child(path: Path) -> dict:
    program = r"""
import json, resource, sys
from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_ooc import N010StreamingDataset
roles = tuple(RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
              for name in ("r0", "r1"))
with N010StreamingDataset(sys.argv[1], roles, 1, expected_splits=("train",)) as data:
    count = sum(1 for _ in data.iter_training_examples())
    print(json.dumps({
        "count": count,
        "peak_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "index_bytes": data._db_path.stat().st_size,
    }))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program, str(path)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


class N010OutOfCoreMemoryTests(unittest.TestCase):
    def test_peak_rss_does_not_scale_with_materialized_example_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            small = root / "small.jsonl"
            large = root / "large.jsonl"
            _write_dataset(small, 1_000)
            _write_dataset(large, 20_000)
            small_result = _measure_in_child(small)
            large_result = _measure_in_child(large)

        self.assertEqual(small_result["count"], 1_000)
        self.assertEqual(large_result["count"], 20_000)
        # 20x the examples should not add a history-sized Python object graph.
        # Allow 12 MiB for interpreter/SQLite allocator and CI runner variance.
        growth_kib = large_result["peak_rss_kib"] - small_result["peak_rss_kib"]
        self.assertLessEqual(growth_kib, 12 * 1024, {
            "small": small_result,
            "large": large_result,
            "growth_kib": growth_kib,
        })


if __name__ == "__main__":
    unittest.main()
