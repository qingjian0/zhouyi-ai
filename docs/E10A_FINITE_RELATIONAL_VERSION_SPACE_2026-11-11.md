# E10-A Finite Relational Version-Space Learner (2026-11-11)

## Status

This branch adds the first explicit E10-A learner over the generator-first object-disjoint task. It is intentionally a finite DSL baseline, not the full Xiang-Potential-Change (XPC) architecture.

## Hypothesis language

For each opaque relation symbol, the learner searches rules of the form:

`R(participants | context) := (feature_key has exactly this unordered set of distinct categorical values) AND (context_key == context_value)`

The role-value set is permutation-invariant because participant order is shuffled and the generator's role mapping is evaluator-only. The learner therefore does not claim to identify ordered semantic roles.

Candidate rules are generated from Support object attributes and Support context values only. Compute telemetry distinguishes initial candidate-generation evaluations, per-prediction rule-match evaluations, and actual update-time candidate/example checks (including early-exit behavior in batch refit). The candidate version space is filtered by Support labels. Query observations are label-blind and are predicted only when all surviving hypotheses agree; otherwise the learner abstains.

## Update arms

- `FROZEN`: preserve the Support version space after reveals.
- `BATCH_REFIT`: recompute consistency against all Support and revealed Query examples over the frozen candidate universe.
- `INCREMENTAL_FILTER`: intersect the current version space with the new revealed example.

For exact finite version spaces, BATCH_REFIT and INCREMENTAL_FILTER should produce identical candidate sets. The expected difference is candidate-update operations, not accuracy. This is a controlled algorithmic comparison, not evidence of a novel online-learning capability.

## Prequential runner

`prototype/e10a_prequential_experiment.py` executes:
1. Generate object-disjoint Support, Query, and evaluator truth.
2. Fit only on Support.
3. Predict one Query observation.
4. Persist prediction commit through `E10SharedProtocolAdapter`.
5. Reveal the evaluator label only after commit.
6. Update the selected learner arm.
7. Persist a new structure version and revision referencing that reveal.
8. Continue sequentially.

The original harness runs in one process. An optional subprocess backend now runs the learner in a separate Python process over bounded JSONL IPC: Support is sent once, then each prediction/update receives only the current observation and its participant objects. The evaluator retains Query truth in the parent and reveals one label only after the prediction commit. The learner-visible Support payload is whitelisted and omits the evaluator-side mechanism fingerprint. The child is launched with isolated Python mode, a reduced environment, closed inherited file descriptors, and stdout-only protocol framing. This is a process/data-flow boundary, not a security sandbox: the child still has the same OS user privileges and is not denied filesystem or network access.

## Metrics

Reports coverage, selective accuracy, strict accuracy with abstentions counted wrong, abstention rate, version-space changes, candidate-update operations, final version-space sizes, and durable event count. It preserves per-query prediction traces. Each run now emits canonical SHA-256 digests of the complete final rule sets (not only their counts), allowing exact equivalence checks between update arms. `run_sweep` evaluates all three arms across consecutive seeds and reports per-seed results plus mean, median, population standard deviation, minimum, and maximum for key metrics; it also reports the aggregate incremental-to-batch update-operation ratio.

## Tests

- Candidate discovery from Support without generator truth.
- Label-blind Query prediction and explicit abstention.
- Participant-order permutation invariance.
- Exact equivalence of BATCH_REFIT and INCREMENTAL_FILTER version spaces.
- FROZEN control invariance.
- Rejection of evaluator-only fields in Query payload.
- Candidate budget fail-closed behavior.
- Prequential runner event lifecycle.

## Limitations and non-claims

- The DSL is matched to a known finite synthetic generator family.
- This is not open-world concept discovery, relation-family OOD, or general operator invention.
- Role order is not identifiable from the shuffled participant observations.
- BATCH_REFIT and INCREMENTAL_FILTER are expected to be predictively equivalent under this fixed candidate universe.
- The subprocess backend provides process separation and a tested serialized-input canary, but not OS sandboxing, privilege separation, filesystem/network denial, cryptographic noninterference, or crash-safe resume.
- No superiority claim over neural, program-synthesis, or other symbolic baselines.

## Next gate

The ten-seed sweep is wired into CI (`--sweep --seeds 10 --start-seed 100`). A subprocess learner backend and hidden-truth input canary are now included; the next security gate is an OS-level sandbox/privilege profile and adversarial IPC tests. Then test E10-B transfer to renamed attributes, unseen objects, and hard negatives. Operator synthesis should wait until those transfer tests and matched baselines exist.
