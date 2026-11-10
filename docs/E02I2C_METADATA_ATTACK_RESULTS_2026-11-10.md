# E02-I2-C-E: First Metadata-Only Attack Results

**Status:** first preregistered Train/Gate run completed successfully; M0 source-isolation ablation is a separate exploratory follow-up.  
**Run:** GitHub Actions `42845566350`  
**Code head:** `df68c4bfbbfb8a4f0ac8d56bb4639b191d752d25`  
**Artifact:** `e02i2c-metadata-attack-report`  
**Date:** 2026-11-10

## 1. Protocol execution

- 8 event classes.
- 30 seed blocks per event.
- Train: 240 episodes, seed range 1000–1239.
- Gate: 240 episodes, seed range 10000–10239.
- 1000 seed-block bootstrap resamples.
- Train/Gate sample namespaces: disjoint.
- Train/Gate evidence namespaces: disjoint.
- Evaluator split marker used as a predictive feature: no.
- Absolute window labels used: no.
- Evaluator truth passed to attacker: no.
- Negative control: fixed Train-label permutation.
- Evidence-aware adjudicator reported as a reference, not as a metadata attacker.

The workflow and report-generation step completed successfully. This is a development Gate result for the current finite synthetic template family, not a locked-Test result.

## 2. Aggregate results

Majority baseline: accuracy 0.1250, Macro-F1 0.0278.  
Evidence-aware adjudicator reference: accuracy 1.0000, Macro-F1 1.0000.

| Tier | Attacker | Accuracy | Macro-F1 | Macro-F1 lift over majority | 95% seed-block CI for lift |
|---|---|---:|---:|---:|---:|
| M0 | Categorical NB | 0.2500 | 0.1278 | 0.1001 | [0.0953, 0.1056] |
| M0 | Depth-3 tree | 0.2500 | 0.1278 | 0.1001 | [0.0953, 0.1056] |
| M1 | Categorical NB | 0.3958 | 0.2950 | 0.2672 | [0.2387, 0.2941] |
| M1 | Depth-3 tree | 0.4542 | 0.3692 | 0.3415 | [0.3171, 0.3636] |
| M2 | Categorical NB | 0.8083 | 0.7589 | 0.7311 | [0.7013, 0.7613] |
| M2 | Depth-3 tree | 0.7292 | 0.6457 | 0.6179 | [0.6005, 0.6347] |

The preregistered M0 alarm is triggered for both attackers: lift is at least 0.05 and the 95% seed-block interval excludes zero.

## 3. What the confusion matrices reveal

### M0 — identifier surface and cardinality

Both attackers predict:
- CREATE for every two-evidence episode;
- KEEP for every one-evidence episode, except the ABSTAIN class is split between those two predictions.

They do not recover MODIFY, REACTIVATE, REACTIVATE_MODIFY, RETIRE or SUSPEND. The M0 alarm is therefore not evidence that random token contents reveal event labels. It is driven by the number of evidence identifiers/records in an episode.

The fixed Train-label permutation control falls to accuracy 0.1250 and Macro-F1 0.0341 for both M0 attackers. This supports the interpretation that the original signal is learned from feature/label association rather than a hard-coded label mapping.

### M1 — operational/provenance structure

M1 perfectly recognizes CREATE, KEEP and MODIFY in this template family, but collapses REACTIVATE, REACTIVATE_MODIFY, RETIRE and SUSPEND into MODIFY. It therefore detects some event structure while failing to distinguish important lifecycle semantics.

### M2 — context shape

M2 adds identity presence/status and coarse candidate-signature shape. The categorical Naive Bayes attacker reaches 0.8083 accuracy and 0.7589 Macro-F1. It recognizes CREATE, KEEP, MODIFY, REACTIVATE, REACTIVATE_MODIFY and SUSPEND strongly, but maps all RETIRE examples to REACTIVATE.

That RETIRE/REACTIVATE confusion is informative: the permitted context-shape fields are insufficient to distinguish them. The missing discriminator is evidence polarity/meaning, which the metadata attacker is forbidden to inspect.

## 4. Negative controls

Train-label permutation reduces Macro-F1 as follows:

| Tier | Categorical NB | Depth-3 tree |
|---|---:|---:|
| M0 | 0.0341 | 0.0341 |
| M1 | 0.0405 | 0.0068 |
| M2 | 0.0600 | 0.0932 |

The control is consistent with the attackers learning correlations from the unpermuted training labels. It does not prove that every possible side channel has been eliminated.

## 5. Interpretation

1. **M0 alarm is a cardinality side channel.** The current M0 feature bundle includes counts of identifier-bearing records. The result does not show that opaque token values or token formats disclose event labels.
2. **M1 demonstrates template/operational leakage.** Window counts, sampling opportunity, record cardinality and provenance structure correlate with the event labels.
3. **M2 demonstrates context-shape leakage.** Identity status and coarse signature syntax make several event labels easy to infer in this benchmark.
4. **Evidence semantics remain necessary.** RETIRE versus REACTIVATE is not resolved by M2 context shape alone.
5. **The perfect evidence-aware score is not proof of autonomous discovery.** Candidate/event templates are predefined and the evaluator supplies the hidden event label only for scoring.

## 6. Limitations and next step

- Only a finite, hand-authored synthetic template family was tested.
- The current generator uses a single environment value; this does not test environment transfer.
- No locked Test, open-world scenario family, or independent mechanism family has been evaluated.
- M0's alarm combines token-format features with identifier cardinality.

A post-hoc diagnostic now separates M0 token-format features from cardinality features and uses a fresh Gate seed range (20000–20239). It is explicitly exploratory and must not replace the preregistered M0 result. Its result will be recorded separately after its own CI run.


## 7. Fresh-Gate M0 source ablation (completed)

**Run:** GitHub Actions `42846824166`  
**Code head:** `7f62a0d4fc19aea1a5ed6d92b7ef8c512fce8819`  
**Train:** 240 episodes, seeds 1000–1239  
**Fresh Gate:** 240 episodes, seeds 20000–20239  
**Bootstrap:** 1000 seed-block resamples

| M0 feature subset | Attacker | Accuracy | Macro-F1 | Lift over majority | 95% CI for lift |
|---|---|---:|---:|---:|---:|
| Format only | Categorical NB | 0.1250 | 0.0278 | 0.0000 | [0.0000, 0.0000] |
| Format only | Depth-3 tree | 0.1250 | 0.0278 | 0.0000 | [0.0000, 0.0000] |
| Cardinality only | Categorical NB | 0.2500 | 0.1345 | 0.1068 | [0.1011, 0.1134] |
| Cardinality only | Depth-3 tree | 0.2500 | 0.1345 | 0.1068 | [0.1011, 0.1134] |

The format-only attackers fall exactly to the majority baseline. The cardinality-only attackers reproduce and slightly strengthen the preregistered M0 alarm on an independent Gate range. This supports the diagnosis that the M0 signal is a record-count/cardinality side channel, not opaque-token formatting.

The cardinality-only feature set still contains several correlated count/duplicate indicators. It does not yet prove that `id.evidence_count` alone is the only causal feature. A follow-up micro-ablation now compares evidence-count-only against all remaining cardinality fields.

## 8. Additional feature-family ablation (pending CI)

The next diagnostic splits M1/M2 into identifier (`id.*`), operational/provenance (`op.*`), and context-shape (`ctx.*`) feature families. It also measures leave-one-family-out variants on a fresh Gate range (30000–30239). This is post-hoc diagnostic work; it does not alter the preregistered M0/M1/M2 results.

The same run further splits M0 cardinality into evidence-count-only and all-other-cardinality fields. The new diagnostic is exploratory and must be reported separately from the preregistered attack.


## 9. Exact M0 source and M1/M2 feature-family ablations

**Run:** GitHub Actions `42849403133`  
**Code head:** `c3c31078aa124d109c5700fc0a8e0c145eda379a`  
**Train:** 240 episodes, seeds 1000–1239  
**Fresh M0 Gate:** 20000–20239  
**Fresh family-ablation Gate:** 30000–30239  
**Bootstrap:** 1000 seed-block resamples  
**Workflow:** success (unit-tests and hidden-identity jobs both completed successfully)

### 9.1 M0: evidence count is the entire observed signal

| Feature subset | Attacker | Accuracy | Macro-F1 | Lift | 95% CI for lift |
|---|---|---:|---:|---:|---:|
| Evidence-count only | Categorical NB | 0.2500 | 0.1345 | 0.1068 | [0.1011, 0.1134] |
| Evidence-count only | Depth-3 tree | 0.2500 | 0.1345 | 0.1068 | [0.1011, 0.1134] |
| All other cardinality fields, excluding evidence count | Categorical NB | 0.1250 | 0.0278 | 0.0000 | [0.0000, 0.0000] |
| All other cardinality fields, excluding evidence count | Depth-3 tree | 0.1250 | 0.0278 | 0.0000 | [0.0000, 0.0000] |

On this generator and Gate range, the M0 alarm is entirely reproduced by the single feature `id.evidence_count`. Duplicate counts and cross-field equality indicators add no measurable predictive signal.

### 9.2 M1: operational metadata is more predictive than identifier metadata

| Feature family | Attacker | Accuracy | Macro-F1 | Lift | 95% CI for lift |
|---|---|---:|---:|---:|---:|
| Identifier only | Categorical NB | 0.2500 | 0.1333 | 0.1056 | [0.1001, 0.1120] |
| Operational only | Categorical NB | 0.3958 | 0.3002 | 0.2724 | [0.2437, 0.3013] |
| Operational only | Depth-3 tree | 0.4792 | 0.3957 | 0.3679 | [0.3505, 0.3847] |

The operational family alone is a much stronger event proxy than identifier format/cardinality. This shows that the current event templates also encode lifecycle labels in observation schedules, counts, sampling opportunities and related operational structure.

### 9.3 M2: context shape is independently predictive

| Feature family / ablation | Attacker | Accuracy | Macro-F1 | Lift | 95% CI for lift |
|---|---|---:|---:|---:|---:|
| Context only | Categorical NB | 0.6667 | 0.5729 | 0.5451 | [0.5128, 0.5722] |
| Context only | Depth-3 tree | 0.6667 | 0.5729 | 0.5451 | [0.5128, 0.5722] |
| M2 without identifier family | Categorical NB | 0.8125 | 0.7642 | 0.7364 | [0.7073, 0.7618] |
| M2 without operational family | Categorical NB | 0.8125 | 0.7667 | 0.7389 | [0.7118, 0.7627] |

Identity presence/status and coarse candidate syntax carry strong predictive information in this finite template family. Removing identifier metadata barely changes M2 performance. Removing operational metadata also leaves a strong context-only signal.

This is not automatically an invalid semantic shortcut: identity status and candidate structure may legitimately inform event adjudication. The result does establish that M2 performance cannot be described as evidence-semantic reasoning alone. The next diagnostic should split identity-state fields from candidate-shape fields and compare both against an evidence-aware policy.

## 10. Updated research conclusion

1. The M0 identifier-surface alarm is specifically an evidence-count side channel in this benchmark.
2. M1 operational/provenance metadata is a larger source of event-template leakage than opaque ID formatting.
3. M2 context shape is highly predictive even without operational or identifier features.
4. The current 8 event templates are not metadata-invariant and are not suitable as a locked generalization test.
5. The next valid step is scenario-family diversity with semantic feasibility constraints, not more random seeds on the same templates.

These results are finite-template diagnostics only. They do not demonstrate open-world generalization, autonomous relation discovery, or causal inference.
