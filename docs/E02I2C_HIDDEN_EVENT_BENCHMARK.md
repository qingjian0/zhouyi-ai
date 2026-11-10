# E02-I2-C Hidden Event Benchmark — Development Protocol

## Purpose

Test whether the evidence-gated event adjudicator distinguishes temporal identity events from superficially similar observations. This is a controlled synthetic development benchmark, not an open-world discovery claim.

## Information boundary

The generator/evaluator owns each episode's hidden `truth`. The adjudicator receives only:
- the observable `IdentitySnapshot` (or no prior identity),
- `ObservationOpportunity` records,
- observable `EvidencePacket` records,
- the observable candidate signature.

The `EvidencePacket` schema has no hidden identity, true event, latent state, or generator-transition field. The benchmark adapter calls `adjudicate_event` without passing `Episode.truth`. The evaluator compares the returned event with truth only after the decision is made.

Held-out Gate observations are valid inputs. Gate labels remain evaluator-side. No threshold fitting is performed in this first benchmark.

## Event coverage

Each seed generates one episode for each event class:
- KEEP
- MODIFY
- CREATE
- ABSTAIN — three distinct causes, rotated by seed: single-window unlinked rule change, insufficient sampling opportunity, and simultaneous support/contradiction
- SUSPEND
- REACTIVATE
- REACTIVATE_MODIFY
- RETIRE

REPLACE, SPLIT and MERGE are deliberately out of scope for this first benchmark: they require multi-identity graph evidence and transactional lineage evaluation, not a one-identity episode.

## Compared policies

1. `similarity_only`: intentionally weak forced decision from identity/signature similarity.
2. `single_window`: intentionally weak latest-window-only decision.
3. `evidence_gated`: current I2-C temporal adjudicator.

These are diagnostic baselines, not a comprehensive comparison against all possible algorithms.

## Split discipline

The development runner accepts only `train` and `gate`. CI uses disjoint seed ranges:
- Train: 20 seeds beginning at 1000.
- Gate: 20 seeds beginning at 2000.

Every sample ID includes its seed and event, so the generated Train and Gate sample namespaces are disjoint. The runner intentionally rejects `split=test`; there is no locked-Test command in this development artifact. A separate locked-Test runner must be created only after the protocol, code and thresholds are frozen, and must be executed once.

## Metrics

- Event macro-F1 and accuracy.
- Decision coverage (non-ABSTAIN rate).
- Selective risk (error rate among non-abstained decisions).
- False CREATE, MODIFY, SUSPEND and RETIRE counts.
- Per-class precision, recall, F1 and support.

The evaluator reports all metrics separately for Train and Gate. No Gate result is used to tune the current deterministic rules.

## Execution

```bash
python -m unittest tests.test_e02i2c_hidden_event_benchmark -v
python -m prototype.e02i2c_hidden_event_benchmark --seeds 20 --start-seed 1000 --split train
python -m prototype.e02i2c_hidden_event_benchmark --seeds 20 --start-seed 2000 --split gate
```

## Interpretation limits

- Synthetic episodes are generated from known event templates.
- The event family is finite and the candidate observation stream is supplied by the generator; this does not test autonomous candidate generation.
- The same adjudication rules are evaluated on both splits; no learned threshold is selected.
- A high score demonstrates only that the adjudicator follows this protocol on these controlled cases.
- It does not demonstrate open-ended relation discovery, robust environmental transfer, causal identification, or autonomous creation of a new representational language.

## Pass/fail policy

Do not declare I2-C complete from this development benchmark alone. Before a locked test, add:
1. multi-identity REPLACE/SPLIT/MERGE episodes and lineage-edge scoring;
2. environment shifts, noisy labels and correlated samples;
3. adversarial counterexamples for identity continuity and evidence leakage;
4. confidence intervals across independent episodes;
5. a frozen, separately generated locked-Test dataset and one-time evaluator run.
