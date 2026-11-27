# Classiang Gold Dataset Admission Contract v1

## Purpose

This contract is the mandatory pre-training admission gate for source-grounded Classiang corpora. It prevents accidental acceptance of untracked sources, unverified training-use permissions, unreviewed Gold labels, and source-family leakage across train/dev/locked-test.

The validator checks declared metadata and the dataset digest. It does **not** independently establish copyright ownership, interpret a license, verify the truth of an annotation, or prove semantic generalization. Those remain human/legal review responsibilities.

## Manifest format

A UTF-8 JSON manifest contains exactly:

- `schema_version: 1`
- `dataset: { path, sha256 }` — dataset path is relative to the manifest directory and may not escape it.
- `split_policy: "source_family_disjoint_v1"`
- `sources[]` — each source declares `source_id`, `source_family_id`, `source_uri`, `license_id`, `license_verified: true`, and `training_use_allowed: true`.
- `groups[]` — each document/near-duplicate group declares `group_id`, `source_id`, `split` (`train`, `dev`, or `locked_test`), and `annotation_status: "human_reviewed"`.

Every dataset record must explicitly carry `group_id`; the prototype loader's legacy subject-ID fallback is not accepted at the Gold admission boundary. Group-to-source identity must be consistent. A source family may occur in only one split. Every declared source and group must be used, and all three split roles must be present.

## Run

```bash
python -m prototype.classiang_dataset_manifest path/to/manifest.json
python -m unittest tests.test_classiang_dataset_manifest -v
```

The report binds the dataset SHA-256 and counts records, sources, source families, and groups by split. The report's `locked_test_role` is evaluation-only: a training orchestrator must not load locked-test labels into the learner process, and must only pass predictions to an isolated evaluator after prediction sealing.

## Admission policy

1. No dataset digest match, no run.
2. No verified source license and explicit training-use approval, no run.
3. No human-reviewed annotation group, no Gold admission.
4. No explicit group IDs or source-family split isolation, no run.
5. Any unknown/missing/unused source or group metadata, no run.
6. Synthetic data remains a pipeline smoke-test tier and must never be promoted to Gold by this validator.

## Current status

This is an executable contract and validator, not a claim that the repository already contains a qualifying real-world Gold corpus. Existing synthetic training fixtures do not satisfy the purpose of a real Gold evaluation set.

## Integration boundary

This PR ships the standalone validator and its contract. The existing legacy training entrypoints do **not** invoke it automatically yet. Therefore, a real Gold training run is not considered admitted merely because a manifest exists: the orchestration layer must call this validator successfully **before** the learner loads the dataset, and an integration test must prove that invalid manifests stop the run before model construction. Synthetic smoke-training paths remain separate and must be labeled synthetic.

