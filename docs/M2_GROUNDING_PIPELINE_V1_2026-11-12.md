# M2 Entity Grounding Pipeline v1

Status: executable injected-resolver contract; not a general entity-linking model or truth adjudicator.

## Position in the pipeline

`Observation → SemanticUnitCandidate (UNRESOLVED) → Entity Grounding → TRLW`

The extraction stage may identify source expressions and typed attributes, but it cannot claim entity identity. The grounding stage resolves a candidate against a scope-authorized, versioned registry. Only candidates returned as `GROUNDED` are eligible for the default TRLW query policy.

## Contract

- Resolver input is one immutable SemanticUnitCandidate.
- Resolver output binds to the exact candidate record ID and exact M1 EvidenceRef tuple.
- A `GROUNDED` decision requires a canonical key and a matched surface form present in the candidate's source forms.
- `PARTIALLY_GROUNDED`, `CONFLICTED`, `REJECTED`, and `STALE` remain distinct statuses; they are not silently promoted to `GROUNDED`.
- An `UNRESOLVED` result does not append a no-op revision.
- Grounding creates a new immutable candidate revision with a deterministic ID and a derivation reference to the prior candidate event.
- Scope, source references, and truth status are preserved. Grounding never sets `SUPPORTED`, `REFUTED`, or a calibrated truth probability.
- The whole bounded decision batch is validated before the first append. Persistence failures can still leave an append-only prefix; deterministic IDs support idempotent retries.

## Trust boundary

The injected resolver is a trusted dependency and must enforce registry access, scope policy, canonical-key namespace and resolver versioning. The pipeline validates output shape and provenance, but it cannot prove that the resolver's entity database is correct. A future production resolver needs explicit registry snapshots, access policy, alias collision handling, multilingual normalization, and adjudication of ambiguous matches.

## Non-claims

This is not an NLP parser, open-world entity linker, knowledge graph truth engine, or E09 authority. It does not demonstrate semantic extraction quality, cross-domain analogy, or general natural-language understanding. Those require separate datasets, locked OOD tests, hard negatives, calibration, and human-audited labels.

## Validation

Focused contract test:

```bash
python -m unittest tests.test_m2_grounding_pipeline -v
```

Repository validation is provided by the `research-branch-validation` workflow on this `research/*` branch. CI success validates contract behavior only; it does not validate resolver quality or entity-linking accuracy.
