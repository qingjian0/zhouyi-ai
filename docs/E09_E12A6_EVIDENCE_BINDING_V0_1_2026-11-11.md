# E09 → E12-A6 evidence binding v0.1

## Purpose

Resolve a candidate evidence reference to a durable E09 reveal event, verify its observation/commit/reveal chain, and project only the metadata needed by E12-A6 lifecycle validation.

## Verification

The resolver requires:
- Exact reveal event ID within the named E09 episode.
- Strict E09 protocol v0.3.
- Evaluator actor role on the reveal.
- Matching episode, scope, learner track, split, query, and prediction identity.
- Exactly one prediction commit and one observation for the referenced prediction.
- Observation sequence before prediction commit; prediction commit before reveal.
- Reveal semantic commit digest equal to the prediction's CPG-EI interop commit digest.
- Reveal event digest equal to the durable E09 prediction-commit envelope digest.
- Explicit reveal causation reference to the prediction event.

The world-family label is required as caller-supplied context. It is never guessed from scope.

## Split projection

| E09 split | E12-A6 role | Rationale |
|---|---|---|
| SUPPORT | TRAIN | E09 SUPPORT is the learner-visible support/training partition |
| GATE_DEV | GATE_DEV | Remains development-only |
| GATE_FINAL | GATE_FINAL | Remains final gate-only |
| LOCKED_TEST | LOCKED_TEST | Remains locked-test-only |

No caller-provided arbitrary role mapping is accepted. In particular, LOCKED_TEST cannot be relabeled as TRAIN.

## Data minimization

The E09 raw target_or_feedback remains in the authoritative E09 event store. The returned E12-A6 Evidence DTO contains an opaque evidence reference rather than the raw label. The PersistentLifecycleLedger further replaces outcome/provenance strings with opaque references when persisting lifecycle events. ZPCM therefore stores no raw revealed target through this bridge.

## Ownership and limitations

- E09 remains authority for evidence payloads, event ordering, and split visibility.
- E12-A6 remains authority for lifecycle transitions.
- ZPCM remains authority for durable lifecycle event history and replay.
- This bridge verifies the E09 event chain against the trusted SQLite store; it does not authenticate the store's operator or provide OS-level process isolation.
- It does not verify branch-merge authorization issuer credentials.
