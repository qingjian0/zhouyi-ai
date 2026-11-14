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
- Witness records require edition, publisher, publication date, digitization source, access date, locator, witness-period class, and a variants list.
- Core pre-Qing records require a pre-Qing primary witness; critical editions must register their underlying witness basis.
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

## Source-discovery triage (not yet admitted as gold records)

- The Wikisource entry for 《周易傳義大全》(四庫全書本) identifies the work as compiled by 明胡廣等 and the displayed witness as 欽定四庫全書. This is a useful example of why work date and surviving/digitized witness date must be stored separately: the work belongs to a pre-Qing lineage, while this displayed witness is a Qing imperial collection copy. Until the underlying textual witness lineage is documented, it should be used for collation, not as a standalone pre-Qing witness.
- The same text page contains the 說卦傳 passage and layers comments from 程子、朱子 and later compilers. These must be segmented into distinct claims and attributed to their own source layers, not merged into one undifferentiated "classical" statement.
- 《周易玩辭集解》 (四庫全書本), 《周易闡象》 and 《易箋》 are Qing-era commentary witnesses and therefore belong in secondary/commentarial or collation roles, not the pre-Qing core.

Discovery links:
- https://zh.wikisource.org/zh/周易傳義大全_(四庫全書本)/卷二十四
- https://zh.wikisource.org/zh-hans/周易玩辞集解_(四库全书本)/卷05
- https://www.shidianguji.com/book/CADAL02040139/chapter/1l7nrwte3ml9q
- https://www.shidianguji.com/book/SK0145/chapter/1jzobna8suecy

These are candidate discovery references only. No record is promoted into the dataset until exact edition metadata, witness lineage, quotation offsets, and annotation review are complete.

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
