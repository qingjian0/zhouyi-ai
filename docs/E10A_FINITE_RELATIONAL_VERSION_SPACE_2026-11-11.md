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


## Ten-seed result (commit 7d20f0d, run #42943830809)

Configuration: seeds 100–109, six instances per template, 54 Support observations and 54 Query observations per seed.

| Metric | FROZEN | BATCH_REFIT | INCREMENTAL_FILTER |
|---|---:|---:|---:|
| Mean coverage | 1.000 | 1.000 | 1.000 |
| Mean selective accuracy | 1.000 | 1.000 | 1.000 |
| Mean strict accuracy | 1.000 | 1.000 | 1.000 |
| Mean abstention rate | 0.000 | 0.000 | 0.000 |
| Mean candidate-update checks | 0 | 9,232.2 | 54 |

Batch refit and incremental filtering produced exactly equal final rule sets in all ten seeds. Aggregate measured update checks were 92,322 for batch refit and 540 for incremental filtering; the incremental/batch ratio was 0.005849 (about 0.585%, or about 171x fewer checks in this synthetic workload).

**Critical interpretation:** FROZEN also achieved 100% strict accuracy with zero update operations. The current Support set already identifies the finite rules well enough to solve this Query distribution. Thus this task does not demonstrate a need for online learning, adaptation, or continual structure revision. The operation-count result is an algorithmic comparison inside this narrow finite DSL; it is not an end-to-end latency or general efficiency claim.

This finding changes the next experiment: E10-B must include genuinely informative held-out conditions—renamed attributes, unseen categorical values, unseen contexts, controlled support ablations, and hard negatives—and must compare against frozen, majority, random, and exact-oracle controls. If the task is not underdetermined for FROZEN, it cannot measure the value of updating.

## Tests

- Candidate discovery from Support without generator truth.
- Label-blind Query prediction and explicit abstention.
- Participant-order permutation invariance.
- Exact equivalence of BATCH_REFIT and INCREMENTAL_FILTER version spaces.
- FROZEN control invariance.
- Rejection of evaluator-only fields in Query payload.
- Candidate budget fail-closed behavior.
- Prequential runner event lifecycle.
- Multi-seed exact rule-set digest equivalence and distribution reporting.
- Subprocess learner lifecycle and evaluator-truth mutation canary.

## Limitations and non-claims

- The DSL is matched to a known finite synthetic generator family.
- This is not open-world concept discovery, relation-family OOD, or general operator invention.
- Role order is not identifiable from the shuffled participant observations.
- BATCH_REFIT and INCREMENTAL_FILTER are expected to be predictively equivalent under this fixed candidate universe.
- The subprocess backend provides process separation and a tested serialized-input canary, but not OS sandboxing, privilege separation, filesystem/network denial, cryptographic noninterference, or crash-safe resume.
- No superiority claim over neural, program-synthesis, or other symbolic baselines.

## Next gate

The ten-seed sweep passed as part of full workflow run #42943830809. The subprocess learner backend and hidden-truth input canary were added after that run; their validation is pending on the latest branch head. The next security gate is an OS-level sandbox/privilege profile, IPC timeouts, and adversarial framing tests. Then test E10-B transfer to renamed attributes, unseen objects, unseen contexts, support ablations, and hard negatives. Operator synthesis should wait until those transfer tests and matched baselines exist.
