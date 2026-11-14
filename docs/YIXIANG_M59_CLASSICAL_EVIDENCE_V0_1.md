# M59 — Classical yixiang evidence provenance schema v0.1

Status: executable provenance validator and synthetic fixtures; no curated gold corpus is claimed.

## Research purpose

M57/M58 test relational mapping on generated graphs. They do not establish that any relation extracted from the Zhouyi or other classical texts is historically grounded. M59 creates a strict intake gate for future classical-text evidence so that source attribution, textual witnesses, variant readings, annotation disagreement, and leakage are visible.

## Evidence hierarchy

- Pre-Qing works are the primary research target.
- Qing-and-later works may support collation, variant tracking, or secondary commentary, but cannot be promoted to core pre-Qing evidence.
- Modern commentary is secondary-only.
- Uncertain dating remains uncertain; it is not silently assigned to the pre-Qing group.
- A quoted span must exactly match a specified witness text and Unicode code-point offsets.
- Every claim must point to one or more exact evidence spans.
- At least two distinct annotators must label every claim independently. Adjudication is a separate field and may remain pending.
- Work-lineage and text-dependence groups must not cross train/validation/test splits.

## Implemented

- Schema version m59-classical-evidence-v0.1.
- Exact span-offset validation against a named textual witness.
- Work-period, source-kind, and evidence-policy gates.
- Claim-to-span referential integrity.
- Two independent annotations and explicit adjudication state.
- Split leakage checks over work lineage and text dependence.
- Corpus audit counts for period, evidence policy, split, and annotation minimum.

## Important limitations

The test fixture uses a short synthetic transcription only to test the validator. It is not a verified quotation, edition, witness, or gold label. No ancient corpus has been ingested or adjudicated yet. The validator cannot authenticate a witness; human bibliographic review and edition-level collation remain mandatory.

## Next evidence-collection protocol

1. Identify each work and its composition-date uncertainty separately from the surviving witness date.
2. Register each witness with edition, publisher/editor, publication date, locator, digitization source, and access date.
3. Transcribe the exact passage and record variants rather than normalizing them away.
4. Annotate explicit textual claims separately from analogy, metaphor, commentarial interpretation, and modern research hypotheses.
5. Require independent annotation before adjudication.
6. Split by work lineage and textual dependence, not by randomly sampled sentences.
7. Publish the source manifest and unresolved disagreements with the dataset.

## Schema fields

Each record contains source, witnesses, evidence_spans, claims, independent_annotations, adjudication, and split. The validator enforces structural integrity but does not infer the semantic correctness of a claim.
