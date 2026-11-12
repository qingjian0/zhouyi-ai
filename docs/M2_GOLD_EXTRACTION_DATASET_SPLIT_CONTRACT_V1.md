# M2 gold extraction dataset and split contract v1

Status: typed manifest and leakage validator; no labeled corpus is included.

## Dataset record

Every gold case is bound to:
- a stable case ID and domain;
- a split (train, validation, test, or held-out-domain OOD test);
- one or more source-lineage IDs;
- one or more immutable M1 EvidenceRefs;
- an annotation review status.

Validation, test, and OOD-test labels must be adjudicated. Training labels may be reviewed or adjudicated, but unreviewed labels are not accepted.

## Leakage prevention

The manifest rejects:
- duplicate case IDs;
- a source-lineage ID assigned to more than one split;
- a source document appearing in more than one split, even if its lineage IDs differ;
- an identical evidence reference crossing splits;
- an OOD domain appearing in train/validation/test as well as OOD-test.

Split assignment must happen at source-document/lineage level before chunking or candidate expansion. Randomly splitting chunks or extracted candidates is prohibited because near-duplicate content can leak across splits.

## OOD interpretation

`ood_test` means domain-held-out evaluation and therefore requires domain isolation. Compositional OOD within an already represented domain should use a separately declared evaluation protocol rather than being mislabeled as domain-held-out OOD.

## Reproducibility

The manifest has stable canonical JSON serialization and a SHA-256 digest. Keep the manifest, annotation schema version, and source lineage mapping under version control. Any annotation correction creates a new dataset version; do not silently mutate the meaning of an existing version.

## Limits

This contract validates split integrity and annotation review state. It does not verify that labels are semantically correct, that EvidenceRefs resolve to live M1 bytes, or that annotators are independent. Those checks belong to the annotation workflow and source resolver. The manifest is not a training dataset by itself until real adjudicated examples are supplied.
