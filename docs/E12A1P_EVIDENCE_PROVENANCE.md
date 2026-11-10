# E12-A1.1 — Evidence Provenance and Candidate Lineage

Status: implemented research extension; lineage semantics are explicit, but causal validity is not established.

## Research question

Can every proposed typed predicate be traced to the exact Train evidence that generated it, the generator version and schema under which it was proposed, and the independent Gate evidence used to evaluate it?

## Data model

- Each immutable `EvidenceRecord` has a caller-supplied, non-empty `evidence_id`, a split (`train` or `gate`), an example, and a schema version.
- Evidence IDs must be globally unique across Train and Gate.
- `schema_version` is explicit and must match the inference call.
- Each candidate has a deterministic canonical `candidate_id` derived from its typed predicate and generator version.
- Candidate rows record generator version, schema version, Train support evidence IDs, Train consistency, Gate consistency, and the Gate evidence IDs used for evaluation.
- The result records the complete Train/Gate evidence ID lists and the selected candidate ID, if one exists.

## Support semantics

- Numeric equality and categorical equality candidates cite the Train records whose feature value equals the candidate value.
- Threshold candidates cite Train records at the adjacent unique values that define the midpoint threshold.
- Parity candidates cite the Train records used to establish the integer-valued parity proposal.
- Gate IDs are recorded as evaluation lineage, not as proposal support. Gate data never generates candidates.

## Guarantees and limits

1. IDs are deterministic for the same typed predicate and generator version.
2. Evidence references are explicit and validated for uniqueness, split, and schema version.
3. Candidate generation remains Train-only; Gate evidence is used only for independent evaluation.
4. Budget exhaustion remains an abstention and retains lineage for evaluated candidates.
5. Provenance establishes derivation and evaluation traceability only. It does **not** establish causal validity, data quality, independence, representativeness, or truth.
6. The candidate ID is a canonical descriptive identifier, not a cryptographic integrity guarantee.
7. The underlying learner remains a finite, single-feature predicate grammar.

## Run

```bash
python -m unittest tests.test_e12a1p_evidence_provenance -v
python -m unittest discover -s tests -v
```
