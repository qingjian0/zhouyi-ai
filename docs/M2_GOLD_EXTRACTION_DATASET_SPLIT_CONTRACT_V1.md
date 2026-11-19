# M2 gold extraction dataset and split contract v1

Status: typed manifest and leakage validator; no labeled corpus is included.

## Dataset record

Every gold case is bound to a stable case ID, domain, split (train, validation, test, or held-out-domain OOD test), source-lineage IDs, immutable M1 EvidenceRefs, and annotation review status. Validation, test, and OOD-test labels must be adjudicated.

## Leakage prevention

The manifest rejects duplicate case IDs, source lineage or document IDs assigned to multiple splits, identical evidence references crossing splits, and OOD domains that also occur in train/validation/test. Split assignment happens at source-document/lineage level before chunking or candidate expansion; random candidate-level splitting is prohibited.

## OOD interpretation

`ood_test` means domain-held-out evaluation and therefore requires domain isolation. Compositional OOD within a represented domain requires a separately declared protocol and must not be mislabeled as domain-held-out OOD.

## Reproducibility

The manifest has canonical JSON serialization and a SHA-256 digest. Keep the manifest, annotation schema version, and source-lineage mapping under version control. Annotation corrections create a new dataset version; do not silently mutate an existing version.

## Limits

This contract validates split integrity and annotation review state. It does not verify semantic label correctness, resolve EvidenceRefs to live M1 bytes, or prove annotator independence. The manifest is not a training corpus until real adjudicated examples are supplied.
