# E10 Shared Evidence Protocol Adapter (2026-11-11)

## Status

Research adapter slice layered on the E09 shared-protocol integration branch. It mirrors E10-A's native prequential ledger into SQLite protocol v0.2. This does not implement an E10 relation learner.

## Preserved E10 semantics

- Prediction commits, evidence reveals, and revision events remain represented by the native `PrequentialLedger`.
- Abstentions remain first-class committed decisions.
- E10's own model version, candidate-set hash, confidence, compute-cost, reveal reliability, operation vocabulary, and rationale code are retained.
- The shared protocol adds the explicit learner track `e10`, durable event sequence, structure-version lineage, and cross-event references.
- The E10-native relation representation is stored as an opaque E10-specific structure definition; it is not converted into E09 rules or AST nodes.

## Durable event sequence

`initial_structure -> observation -> prediction_commit -> evidence_reveal -> structure_version -> revision`

The observation payload itself is not copied into the event store; the adapter stores a canonical digest in `payload_ref`. The caller must ensure this is the learner-visible query payload, not hidden evaluator truth.

## Failure and security boundaries

The native E10 ledger and SQLite store are two independent state holders. The adapter fails closed after a partial operation; it does not claim a cross-store atomic transaction, outbox, crash recovery, or replay reconstruction.

The adapter is in-process. Evaluator labels and learner state are not protected by process isolation, OS permissions, or authenticated IPC. A production design must make the evaluator the only holder of hidden labels and release each label only after a durable prediction acknowledgement.

## Validation

Run:

```bash
python -m unittest tests.test_e10a_prequential_ledger tests.test_e10_shared_protocol_adapter -v
```

Tests cover prediction/reveal/revision ordering, E10 abstention persistence, E10-native ledger preservation, and structure lineage. A full CI result is pending until a workflow runs against the exact branch head.

## Non-claims

- No E10 relation/analogy induction learner is integrated.
- No continual-learning benefit or accuracy improvement is demonstrated.
- No secure evaluator/learner isolation.
- No crash-safe cross-store transaction or restart resume.
- No benchmark superiority claim.
