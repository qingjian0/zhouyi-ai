import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_dataset_manifest import validate_manifest


def _write_fixture(root: Path, *, leak_family: bool = False, reviewed: bool = True):
    rows = []
    groups = []
    sources = []
    for index, split in enumerate(("train", "dev", "locked_test")):
        source_id = f"source-{index}"
        group_id = f"group-{index}"
        family_id = "shared-family" if leak_family and index in (0, 1) else f"family-{index}"
        text = f"device {index} transfers water"
        start = text.index("transfers water")
        rows.append({
            "observation_id": f"obs-{index}",
            "subject_id": f"subject-{index}",
            "domain": "mechanical",
            "source_id": source_id,
            "group_id": group_id,
            "text": text,
            "annotations": [{
                "start_char": start,
                "end_char": start + len("transfers water"),
                "dimension": "function",
                "value": "transfers-water",
                "purposes": ["recognition"],
            }],
        })
        sources.append({
            "source_id": source_id,
            "source_family_id": family_id,
            "source_uri": f"https://example.test/source/{index}",
            "license_id": "CC-BY-4.0",
            "license_verified": True,
            "training_use_allowed": True,
        })
        groups.append({
            "group_id": group_id,
            "source_id": source_id,
            "split": split,
            "annotation_status": "pending" if not reviewed and split == "locked_test" else "human_reviewed",
        })
    dataset = {"schema_version": 1, "examples": rows}
    raw = json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode("utf-8")
    (root / "dataset.json").write_bytes(raw)
    manifest = {
        "schema_version": 1,
        "dataset": {"path": "dataset.json", "sha256": hashlib.sha256(raw).hexdigest()},
        "split_policy": "source_family_disjoint_v1",
        "sources": sources,
        "groups": groups,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root / "manifest.json"


class ClassiangDatasetManifestTests(unittest.TestCase):
    def test_valid_manifest_reports_disjoint_reviewed_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            report = validate_manifest(_write_fixture(Path(directory)))
        self.assertEqual(report["record_count"], 3)
        self.assertEqual(report["groups_by_split"], {"dev": 1, "locked_test": 1, "train": 1})
        self.assertTrue(report["source_family_disjoint"])
        self.assertTrue(report["all_groups_human_reviewed"])

    def test_rejects_source_family_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "source-family leakage"):
                validate_manifest(_write_fixture(Path(directory), leak_family=True))

    def test_rejects_unreviewed_locked_test_group(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "not human_reviewed"):
                validate_manifest(_write_fixture(Path(directory), reviewed=False))

    def test_rejects_dataset_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = _write_fixture(Path(directory))
            (Path(directory) / "dataset.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                validate_manifest(manifest_path)

    def test_rejects_implicit_group_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = _write_fixture(root)
            payload = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
            for row in payload["examples"]:
                row.pop("group_id")
            raw = json.dumps(payload, sort_keys=True).encode("utf-8")
            (root / "dataset.json").write_bytes(raw)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dataset"]["sha256"] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "group_id explicitly"):
                validate_manifest(manifest_path)

    def test_rejects_unknown_source_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = _write_fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["groups"][0]["source_id"] = "missing-source"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown source_id"):
                validate_manifest(manifest_path)


if __name__ == "__main__":
    unittest.main()
