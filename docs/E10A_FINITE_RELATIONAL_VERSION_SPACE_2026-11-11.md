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

The ten-seed sweep, subprocess learner backend, hidden-truth input canary, and full repository workflow all passed on latest E10-A head `e47a97d528d27f90a4c7c44dd80cc919899a41d6` in Run #42944371831. That run includes unit tests, E10-A experiment, subprocess backend, ten-seed sweep, and E01/E02 experiment gates. The next security gate is an OS-level sandbox/privilege profile, IPC timeouts, and adversarial framing tests. Then test E10-B transfer to renamed attributes, unseen objects, unseen contexts, support ablations, and hard negatives. Operator synthesis should wait until those transfer tests and matched baselines exist.


## E10-B first gate: explicit OOD abstention and renaming invariance

The learner now distinguishes three kinds of out-of-distribution input before voting. The first CI pass exposed two integration defects: the native ledger/shared protocol had a closed list of old decision statuses, and the rename-invariance test incorrectly required every query to be predictable even though the object-disjoint split intentionally creates unseen nuisance values. The ledger and shared protocol now accept the OOD statuses, and rename invariance compares both decision status and prediction, including valid abstentions. A subsequent CI run must verify these fixes.

The learner distinguishes:
- `ABSTAIN_OOD_RELATION`: an unseen relation symbol.
- `ABSTAIN_OOD_SCHEMA`: unseen attribute/context keys or participant records with no Support-known feature key.
- `ABSTAIN_OOD_VALUE`: unseen categorical attribute or context values.

This prevents a dangerous failure mode in which every known rule fails to match an unfamiliar input and the learner incorrectly turns that universal mismatch into a confident negative prediction.

`prototype/e10b_transfer_experiment.py` evaluates:
1. consistent global renaming of Support and Query feature/context keys (prediction invariance);
2. Query-only renamed attributes (must abstain as OOD schema);
3. Query-only unseen categorical values (must abstain as OOD value);
4. Query-only unseen context values (must abstain as OOD value);
5. Support-majority, deterministic-random, and evaluator-oracle upper-bound controls.
6. Post-hoc hard-negative slices by evaluator-only violation class.
7. Deterministic removal of 50% and 100% of positive Support evidence per relation, retaining negative Support examples.

The oracle is evaluator-only and is reported solely as an upper bound. OOD abstention is a safe rejection behavior, not successful extrapolation. The current stage does not yet establish semantic analogy, relation-family transfer, or open-world concept induction. Positive-support ablation tests whether evidence reduction increases ambiguity or failure; hard-negative slices expose which violation types remain difficult. These are diagnostic stress tests, not population estimates. CI runs this audit and its unit tests.


## E10-B.2: multi-seed positive-evidence ablation curve

`prototype/e10b_ablation_curve.py` retains a deterministic random subset of positive Support observations independently for each seed and relation, while retaining every negative Support row. The same object-disjoint Query split is scored at each retention fraction. The CI configuration uses seeds 200–204, six instances per template, and positive-evidence retention fractions 100%, 75%, 50%, 25%, and 0%.

Full repository workflow Run #42946954671 passed on commit `61bab220a92faef908a0a58dd638dd5c5ab3946e`. The five seeds produced identical aggregate values in this generator configuration:

| Positive Support retained | Mean coverage | Mean selective accuracy | Mean strict accuracy | Mean abstention | Mean version-space size | Mean prediction rule checks |
|---:|---:|---:|---:|---:|---:|---:|
| 100% (12 rows) | 0.4444 | 1.0000 | 0.4444 | 0.5556 | 2 | 54 |
| 75% (8 rows) | 0.4444 | 1.0000 | 0.4444 | 0.5556 | 2 | 54 |
| 50% (6 rows) | 0.4444 | 1.0000 | 0.4444 | 0.5556 | 2 | 54 |
| 25% (2 rows) | 0.4444 | 1.0000 | 0.4444 | 0.5556 | 2 | 54 |
| 0% (0 rows) | 0.2222 | 1.0000 | 0.2222 | 0.7778 | 49 | 1,272 |

The candidate-generation count remained 56 at every fraction. The standard deviation across the five seeds was zero for the listed aggregate metrics in this particular generator setup.

**Interpretation:** one retained positive example per relation (25% overall) was sufficient to preserve the same version-space size and prediction coverage as full positive evidence. Removing all positive Support examples expanded the aggregate version space from 2 to 49 and halved coverage, while the predictions that remained covered were still correct. This is evidence that the current synthetic task is highly identifiable from very little positive evidence—not evidence of robust learning under broad evidence scarcity. The flat curve from 100% through 25% also shows that this ablation schedule does not yet probe a gradual degradation regime. Future stress tests should vary the latent rule family, introduce correlated nuisance features, and control which *types* of positive evidence are removed, not only their count.

The strict metric counts abstentions as incorrect; selective accuracy is conditioned on coverage. These metrics must be read together. The reported 100% selective accuracy at 0% positive evidence does not mean the learner solves the task: coverage is only 22.22%.

## E10-B.3: opaque relation zero-shot identifiability boundary

`prototype/e10b_relation_ood_identifiability.py` constructs two evaluator worlds with byte-identical learner-visible Support and Query payloads but opposite hidden labels for an unseen relation symbol. The learner receives Support for one relation and Query for a second relation, with no shared examples or public relation-family descriptor.

Full repository workflow Run #42947215049 passed on commit `305b03e9c131d15013b60fe3124b63d2c0c5be73`. On seed 2701, the seen relation supplied 16 Support observations and the unseen relation had 20 Query observations. Both evaluator worlds had the same visible-payload SHA-256 digest; all 20 hidden labels were inverted between worlds. The current learner correctly returned `ABSTAIN_OOD_RELATION` for all 20 observations.

This is an identifiability boundary, not a model-performance benchmark: a forced binary predictor must have mean accuracy 50% across the two equally weighted, observationally indistinguishable worlds. Abstention avoids unsupported predictions but has zero coverage on this held-out relation. Zero-shot transfer for opaque relation symbols is impossible to justify from these inputs alone. A meaningful next experiment must expose a *public, non-label-bearing relation descriptor* or shared examples, then test whether that information actually supports transfer and whether descriptor collisions cause false transfer.

## E10-B findings and next research gate

1. The current finite DSL solves the matched object-disjoint task with very little positive evidence; increase structural diversity and adversarial nuisance variation before claiming evidence-efficient learning.
2. Unknown relation symbols are not a learnable zero-shot transfer problem without additional observable structure. The current fail-closed abstention is the correct behavior under the present input contract.
3. The next useful experiment is descriptor-conditioned relation-family transfer: provide an explicit public relation signature (e.g. arity and declared role/attribute schema), hold out an entire relation family, and compare descriptor-aware transfer against opaque-symbol abstention, majority, random, and evaluator-only oracle controls. Include descriptor collision and misleading-descriptor controls.
4. Keep symbolic structure discovery separate from its encoding. Only after a descriptor-based baseline exists should E10-C test whether multiple local relations can compose into higher-order structures, and E10-D test whether those structures can be revised under changing conditions and contradictory evidence.

All results remain limited to the synthetic generator and declared finite DSL. They do not establish semantic analogy, open-world operator invention, or superiority over neural or program-synthesis baselines.


## E10-C.1: contradictory evidence and version-space revision

`prototype/e10c_conflict_revision.py` selects a Query example that the Support-only learner predicts correctly, reveals its true label, then injects a second independent observation with identical relation symbol, participant objects, and context but the opposite label. The second observation has a distinct observation ID, so this is contradictory evidence rather than a duplicate retry.

Full repository workflow Run #42950720661 passed on code commit `339431c9a3236faf42bfd5f54539ef61ad246c27`. The default run (seed 2801) selected a ternary relation example and began with two total candidates (one for the selected relation). After the consistent reveal, one candidate remained. After the contradictory reveal:

| Update mode | Candidates after conflict | Update operations for conflict | Final decision |
|---|---:|---:|---|
| FROZEN | 1 | 0 | PREDICT (stale structure retained) |
| BATCH_REFIT | 0 | 176 | ABSTAIN_INCONSISTENT |
| INCREMENTAL_FILTER | 0 | 1 | ABSTAIN_INCONSISTENT |

The two adaptive update modes produced exactly the same empty final version space. In this one synthetic conflict, incremental filtering performed 1 candidate check versus 176 checks for batch refit; this is an operation-count result, not an end-to-end speedup claim. The frozen arm demonstrates the failure mode of refusing to revise: it retains a prediction despite the contradictory evidence.

**Interpretation:** exact finite version-space revision can detect incompatible evidence and fail closed. It cannot decide which source is trustworthy, recover the intended rule, or invent a replacement rule when the current candidate universe is inadequate. This experiment tests contradiction handling within a fixed DSL; it is not a concept-drift or open-world adaptation result.

## E10-C next gate: expansion versus contradiction

The next dynamic-learning experiment must distinguish two cases that currently collapse into abstention:

1. **True contradiction:** identical observable inputs receive incompatible labels. The current version space should become empty and remain explicitly inconsistent until evidence is adjudicated.
2. **Concept drift / new mechanism:** new observations are generated by a changed rule or a previously unseen condition. A fixed Support-derived candidate universe cannot recover a rule that was never enumerated.

A future expansion arm may regenerate a bounded candidate universe from authorized revealed evidence, but it must be separately versioned and audited. It must not silently erase old evidence or reinterpret contradictions as drift. Required controls: frozen universe, incremental filtering, bounded expansion, explicit drift declaration, and evaluator-only oracle. Measure candidate-universe growth, version-space changes, prediction coverage, selective/strict accuracy, abstention, and compute cost. Include a no-drift control to quantify false structure expansion.

The full repository workflow on the above code commit passed all unit tests and E10-A/E10-B/E10-C.1 and E01/E02 experiment gates. The documentation-only update that records these results triggers a fresh workflow run.


## E10-C.2: single-rule concept-drift representability boundary

`prototype/e10c_drift_representability.py` tests a limitation of the current one-rule-per-relation DSL. A controlled epoch-1 mechanism requires unordered role values `{A, B}` under context `red`; epoch 2 requires `{C, D}` under context `blue`. The same relation symbol is used across epochs.

The minimal audit has four gates: the combined stationary fit must have an empty version space; fitting each epoch separately must produce exactly one candidate each; and a no-drift control with the same `{A, B}`/`red` signature repeated across epochs must remain identifiable. These checks passed in the E10-C.2 CI step and its unit test on commit `9f5e224f4153f4cbc829dab4e03c04b05bd35882`.

**Interpretation:** this is a representability boundary, not a drift-detection result. A single static rule cannot represent the two sequentially different signatures when all evidence is forced into one version. An externally supplied epoch boundary restores identifiability in this minimal example. The learner does not autonomously detect the boundary, and this experiment does not modify production learner behavior.

## E10-C next gate: drift declaration and bounded expansion

Keep three operations distinct: (a) contradiction adjudication, where incompatible labels for identical inputs must remain explicitly inconsistent; (b) epoch segmentation, where evidence from different mechanisms is assigned to separate immutable versions; and (c) hypothesis expansion, where a declared epoch may enumerate a bounded new candidate universe from authorized evidence. Do not silently treat an empty version space as proof of drift. A future detector must be evaluated against stationary false-alarm controls, abrupt and gradual changes, noisy labels, detection delay, and the cost of unnecessary expansion.

Full repository Run #42951140784 is verifying the E10-C.2 addition and all E01/E02 gates; the E10-C.2 unit test and experiment step have passed so far. The final workflow conclusion remains pending at this documentation update.
