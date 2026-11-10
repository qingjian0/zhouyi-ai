# E02-I2-C-E Follow-up Audit — 2026-11-10

**Branch:** `research/e02i2c-followup-audit-2026-11-10`  
**Base:** PR #26 head `7f62a0d4fc19aea1a5ed6d92b7ef8c512fce8819`  
**Scope:** independent audit note only; no edits to PR #26, PR #29, or other AI branches.

## 1. Evidence inspected

- GitHub Actions run: `42847416372`
- Metadata attack job: `129938547640`
- Artifact: `e02i2c-metadata-attack-report` (artifact ID `13778987229`)
- Artifact SHA-256: `2bd03919dcc3e20891957240cd5ff71deb7b4efefac492ac1974989efcadc669`
- Executed command: `python -m prototype.e02i2c_metadata_attack --seeds 30 --train-start-seed 1000 --gate-start-seed 10000 --bootstrap-samples 1000`
- The artifact was downloaded and its JSON parsed, not inferred from the PR summary.

## 2. Formal result versus post-hoc ablation

The formal run uses Train seeds 1000–1239 and Gate seeds 10000–10239 (240 episodes each). The additional M0 ablation is a separate exploratory diagnostic using the same Train range and fresh Gate seeds 20000–20239. The latter is explicitly labelled `exploratory_post_hoc_diagnostic`; it is not a replacement for the preregistered result.

Formal Gate aggregate results:

| Tier | Attacker | Accuracy | Macro-F1 | Lift over majority | 95% seed-block CI for lift |
|---|---|---:|---:|---:|---:|
| M0 | Categorical NB | 0.2500 | 0.1278 | 0.1001 | [0.0953, 0.1056] |
| M0 | Depth-3 tree | 0.2500 | 0.1278 | 0.1001 | [0.0953, 0.1056] |
| M1 | Categorical NB | 0.3958 | 0.2950 | 0.2672 | [0.2387, 0.2941] |
| M1 | Depth-3 tree | 0.4542 | 0.3692 | 0.3415 | [0.3171, 0.3636] |
| M2 | Categorical NB | 0.8083 | 0.7589 | 0.7311 | [0.7013, 0.7613] |
| M2 | Depth-3 tree | 0.7292 | 0.6457 | 0.6179 | [0.6005, 0.6347] |

Majority baseline: accuracy 0.1250, Macro-F1 0.0278. The evidence-aware adjudicator reference is 1.0/1.0, but it is not a metadata attacker and must not be interpreted as an autonomous discovery result.

## 3. Confirmed implementation issue: alarm semantics are tier-hardcoded

In `prototype/e02i2c_metadata_attack.py`, the formal result currently computes:

```python
metrics["leakage_alarm"] = (
    tier == "M0"
    and lift >= 0.05
    and interval["macro_f1_lift_ci_95"][0] > 0.0
)
```

Consequences:

- M0 can trigger the alarm.
- M1 and M2 cannot trigger it, regardless of their measured lift or confidence interval.
- Therefore M1/M2 `leakage_alarm: false` is not evidence that those feature sets are non-predictive or safe.
- Their predictive results are real benchmark observations, but whether they represent unacceptable leakage depends on the threat model and which fields an attacker is allowed to observe.

This is a reporting/semantic defect if downstream readers interpret the boolean as a general leakage verdict. Keep the narrow M0 identifier-surface alarm, but name it explicitly (for example, `identifier_leakage_alarm`). Report a separate, consistently calculated `metadata_predictability` metric for M0/M1/M2. Do not automatically label all predictability as privacy leakage.

## 4. M0 ablation: what is and is not isolated

The post-hoc ablation uses fresh Gate seeds 20000–20239 and reports:

| Feature subset | Attacker | Macro-F1 | Lift over majority | 95% CI for lift | Alarm |
|---|---|---:|---:|---:|---|
| Format-only | NB / depth-3 tree | 0.0278 | 0.0000 | [0.0000, 0.0000] | No |
| Cardinality-only | NB / depth-3 tree | 0.1345 | 0.1068 | [0.1011, 0.1134] | Yes |

The result supports: no predictive lift was detected from the current format-only feature bundle; the combined cardinality bundle is predictive in this finite benchmark.

It does **not** yet isolate pure count leakage. `_M0_CARDINALITY_KEYS` groups these together:

- `id.evidence_count`
- `id.evidence_duplicates`
- `id.sample_duplicates`
- `id.raw_duplicates`
- `id.same_value_cross_field`

The last feature is cross-field namespace equality, not a count. It should be tested separately. Recommended four-way decomposition:

1. `M0-Count`: evidence-record count only.
2. `M0-Duplicate`: within-field duplicate counts only.
3. `M0-CrossField`: evidence/sample/raw identifier equality across fields only.
4. `M0-Combined`: historical cardinality bundle.

Keep `M0-Format` as a separate control. Pre-register a new confirmatory Gate range before looking at its results; do not reuse the post-hoc Gate as a confirmatory test.

## 5. Additional interpretation from the confusion matrices

- M0 does not recover the full lifecycle label set; its predictions are concentrated on CREATE and KEEP. This is consistent with a coarse cardinality side channel rather than recovery of opaque token contents.
- M1 has substantial predictive lift, but collapses several distinct lifecycle events into the same prediction. This is evidence of partial template/operational correlation, not full semantic inference.
- M2 has the strongest predictive lift. In this finite template family, context shape is highly informative. The RETIRE/REACTIVATE confusion shows that the allowed context-shape fields still do not encode all lifecycle semantics.
- Train-label permutation substantially reduces predictive performance. This is a useful negative control, but it does not prove the absence of all other side channels.

## 6. Required follow-up work

### P0 — correct report semantics

- Split `identifier_leakage_alarm` from `metadata_predictability`.
- Remove the tier-hardcoded alarm semantics from generic report fields.
- Make the threat model explicit for each tier: attacker-visible, permitted-but-sensitive, and evaluator-only fields.
- Add tests proving that a deliberately predictive M1/M2 feature set can be reported as predictable without mislabelling it as identifier leakage.

### P1 — isolate M0 sources

- Implement Count / Duplicate / CrossField / Combined ablations.
- Add feature-level invariance tests under independent random bijections for evidence IDs, sample IDs, and raw-reference IDs.
- Ensure the three token namespaces are generated independently; a shared token source can create cross-field equality artifacts.
- Run a new preregistered Gate with a new seed range and report seed-block bootstrap intervals.

### P2 — test robustness beyond the current template family

- Add multiple environments with changed evidence cardinality and observation cadence.
- Randomize nuisance variables independently of event labels.
- Include adversarial cases where event identity is constant but evidence counts vary, and where event identity changes while counts remain fixed.
- Evaluate whether M1/M2 prediction persists under those interventions.
- Add at least one generator/mechanism family not used to design the feature extractor.

## 7. Acceptance criteria

This audit should not be considered closed until:

1. M0 Count, Duplicate, and CrossField effects are separately measured.
2. Generic report fields no longer imply M1/M2 are safe merely because the M0-only alarm is false.
3. Feature namespace randomization preserves semantic decisions and removes unintended equality channels.
4. New Gate results are preregistered, reproducible, and accompanied by per-seed-block outputs.
5. Conclusions remain limited to the tested synthetic mechanisms until independent mechanism families and environment shifts are evaluated.

**Current conclusion:** the formal CI succeeded and the M0 alarm is supported in the tested finite benchmark. The exploratory ablation narrows the signal to the combined cardinality/cross-field bundle, not pure record count. The current M1/M2 alarm booleans are structurally incapable of reporting a positive alarm; their measured predictability must be discussed separately. No claim of open-world security or autonomous discovery is justified.
