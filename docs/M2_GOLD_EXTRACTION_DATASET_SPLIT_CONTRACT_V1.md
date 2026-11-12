# M2 gold extraction dataset and split contract v1.1

Status: typed manifest, source-span provenance, and leakage validator; no labeled corpus is included.

## Dataset record

Every gold case is bound to:
- a stable case ID and domain;
- a split (train, validation, test, or held-out-domain OOD test);
- one or more source-lineage IDs;
- one or more immutable M1 EvidenceRefs;
- an annotation review status;
- at least one byte-exact source evidence span for every positive gold semantic unit.

A gold span records the ordered gold-unit index, its EvidenceRef, absolute source byte offsets, and SHA-256 of the exact span bytes. Offsets must be a non-empty subrange of the EvidenceRef. A separate M1 source resolver must verify that the span digest matches the actual immutable source bytes; DTO validation alone cannot establish that fact. Negative/no-answer cases have no gold-unit spans but still retain their source evidence context.

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

The manifest has stable canonical JSON serialization and a SHA-256 digest. It reports case, gold-unit, and evidence-span counts. Keep the manifest, annotation schema version, and source lineage mapping under version control. Any annotation correction creates a new dataset version; do not silently mutate the meaning of an existing version.

## Limits

This contract validates split integrity, annotation review state, source-span shape, and EvidenceRef containment. It does not verify span bytes against M1, prove label correctness, or establish annotator independence. Those checks belong to the source resolver and annotation workflow. The manifest is not a training dataset by itself until real adjudicated examples are supplied.
