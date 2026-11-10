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
