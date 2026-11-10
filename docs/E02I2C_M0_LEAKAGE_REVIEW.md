# E02-I2-C-E: M0 Leakage Finding and Follow-up Protocol

**Status:** independent research review; no changes to PR #26 or its running CI  
**Evidence run:** GitHub Actions run [42845267534](https://github.com/qingjian0/zhouyi-ai/actions/runs/42845267534), run 293  
**Evidence head:** `c9a66fa1f1addb6921260d00ff9235df55805ef0`  
**Follow-up branch base:** PR #26 head `df68c4bfbbfb8a4f0ac8d56bb4639b191d752d25`  
**Scope:** interpret the completed 30-seed-block metadata attack and define a fresh, non-contaminated next experiment.

## 1. Result: the preregistered M0 leakage alarm fired

The completed artifact reports 240 Train episodes and 240 Gate episodes: 30 examples for each of eight event classes, with disjoint seed ranges (Train 1000–1239; Gate 10000–10239).

| M0 attacker | Accuracy | Macro-F1 | Lift over majority | 95% seed-block CI for lift | Alarm |
|---|---:|---:|---:|---:|---|
| Categorical Naive Bayes | 0.2500 | 0.1278 | +0.1001 | [0.0953, 0.1056] | **Fired** |
| Depth-3 decision tree | 0.2500 | 0.1278 | +0.1001 | [0.0953, 0.1056] | **Fired** |
| Majority | 0.1250 | 0.0278 | — | — | Reference |

The preregistered threshold was a macro-F1 lift of at least 0.05 with a 95% seed-block bootstrap interval excluding zero. Both attackers exceed that threshold. The result therefore falsifies the claim that the current benchmark's M0 identifier surface is non-predictive under the registered attacker family.

The Train-label permutation negative control returned near-majority performance in this run (Naive Bayes accuracy 0.1250, macro-F1 0.0341; tree accuracy 0.1250, macro-F1 0.0341). This is useful, but it is only one fixed permutation and is not a calibrated permutation-null distribution.

## 2. Stop-rule consequence

The preregistration explicitly says that an M0 failure requires stopping and repairing the identifier/provenance surface before interpreting higher tiers.

Accordingly:

- M0 is a **positive leakage finding**, not a pass.
- M1 and M2 scores are descriptive diagnostics only in this run. They must not be presented as independent evidence of event understanding or as a validated tier progression.
- The evidence-aware adjudicator's 1.0 accuracy is a finite-template reference result. It does not demonstrate open-world discovery, because the generator uses hand-authored event templates and the evaluator's eight event classes are fixed.
- This result does not establish that the core relation adjudicator is wrong. It establishes that a separate attacker can recover some evaluator labels above the registered M0 baseline without polarity or literal candidate-signature semantics.

## 3. Feature-level audit: M0 currently mixes two questions

The M0 extractor includes identifier syntax features and `id.evidence_count`. The preregistration permits counts of identifiers, but this creates an interpretive ambiguity:

1. **Identifier-surface leakage:** prefixes, schemes, lengths, character classes, token structure, cross-field linkage, duplicate/equality patterns.
2. **Cardinality/template leakage:** number of evidence/sample/reference records.

These must be measured separately. A positive result for the combined M0 tier cannot yet be attributed specifically to opaque-ID formatting or token content.

The next audit must split the current M0 into:
- **M0-Syntax:** per-field prefixes, schemes, lengths, character shapes, and token-structure relations; no record counts.
- **M0-Cardinality:** evidence/sample/reference counts and duplicate counts only.
- **M0-Combined:** the original registered feature family, retained for comparability.

The existing Gate has already been inspected and must not be reused to tune this decomposition. Any revised feature set is exploratory on that Gate and requires a new untouched Gate.

## 4. Provenance independence issue to verify

The current hidden-event generator's `_packet` function creates one random token and reuses it in:
- `evidence_id`,
- `sample_id`,
- `raw_observation_ref`.

The field prefixes differ, but the opaque token payload is shared. Therefore these are not independently randomized provenance identifiers, despite the earlier hardening description referring to independent randomized IDs.

This does not by itself explain the M0 alarm: the present M0 extractor checks full-string equality and token-length relations, but does not explicitly compute shared-suffix/token-overlap relations. It is nevertheless a concrete mismatch between the intended provenance-independence property and the generator implementation.

Do not silently patch PR #17 or PR #26 from this review. Add an independent provenance audit that tests:
- independent random token generation per field;
- no shared suffix, substring, or reversible transform across fields;
- cross-episode uniqueness per namespace;
- invariance of adjudication under independent bijective renaming of each namespace.

## 5. E02-I2-C-F: scenario-diversity and nuisance-randomization protocol

The next experiment should test whether the M0 signal is a consequence of fixed event templates and correlated nuisance metadata.

### Data construction

- Preserve the eight evaluator labels and keep truth outside the attacker-visible observation.
- Generate multiple independently authored scenario templates per event, rather than one fixed construction path per label.
- Sample nuisance variables independently of event label: evidence count, number of observation opportunities, missingness pattern, window offsets/gaps, record order, source-version presence, environment labels, and identifier formatting.
- Where constraints are semantically necessary, define matched strata and sample the same nuisance distribution across every event class within each stratum.
- Generate evidence, sample, and raw-reference identifiers from independent namespaces with independent random tokens.
- Keep the semantic evidence sufficient for the adjudicator while changing nuisance metadata. Every counterfactual transform must preserve the intended event and the adjudicator's semantic decision.

### Attack matrix

| Attack | Input | Question |
|---|---|---|
| M0-Syntax | ID syntax only | Does identifier formatting leak labels? |
| M0-Cardinality | Record counts only | Do template sizes leak labels? |
| M0-Combined | Original M0 family | Does the combined surface leak labels? |
| M1 | Operational metadata | Do sampling and provenance schedules leak labels? |
| M2 | Context shape | Are context fields event proxies? |
| Evidence-aware reference | Semantic evidence | Does the adjudicator remain correct under nuisance shifts? |

### Statistical protocol

- Keep the current failed Gate permanently as a reported historical result.
- Use disjoint Train, development, and new Gate generator seeds and namespaces.
- Hold out entire scenario-template families from Gate, not merely new random seeds from the same templates.
- Use at least 30 seed blocks per event; report class-wise results, confusion matrices, seed-block bootstrap intervals, and the full feature schema.
- Run at least 1,000 independent Train-label permutations to form a null distribution; report the observed score's percentile and empirical p-value. Do not rely on one permutation.
- Freeze all feature engineering and attacker settings before opening the new Gate.
- If any M0 tier fires its registered alarm, stop the claim of metadata isolation and localize the leaking feature before proceeding to M1/M2 interpretation.

## 6. Claims permitted after this review

Permitted:
- "The first 30-block E02-I2-C-E run detected an M0 metadata/identifier-surface leakage signal under its registered threshold."
- "The source of the signal is not yet isolated between identifier syntax and record cardinality."
- "A new scenario-diversity experiment is required."

Not permitted:
- "The benchmark is metadata-isolated."
- "M1/M2 scores prove event understanding."
- "Opaque IDs are statistically independent."
- "The event adjudicator has demonstrated open-world autonomous relation discovery."
- "The fixed-template 100% evidence-aware score demonstrates general intelligence."

## 7. Non-interference

This review is on a separate branch. It does not modify PR #26, PR #17, the hidden-event benchmark branch, `main`, or any other AI's work. The in-progress workflow on PR #26 is left untouched.
