# E02-I2-C-E: Metadata-Only Leakage Attack Preregistration

**Status:** preregistered design; implementation and empirical results are not yet available  
**Parent work:** E02-I2-C hidden-event development benchmark (PR #16) and integrity hardening (PR #17)  
**Purpose:** determine whether an event classifier can recover evaluator event labels from identifiers or non-semantic structure without reading relation evidence.

## 1. Research question

Can an attacker predict the evaluator-owned event label using only observable identifiers and metadata, while being denied the evidence semantics that should justify the event?

This is a leakage audit, not a new claim that the adjudicator autonomously discovers events. The benchmark's eight event labels are KEEP, MODIFY, CREATE, ABSTAIN, SUSPEND, REACTIVATE, REACTIVATE_MODIFY and RETIRE.

## 2. Threat model and feature tiers

The attacker receives an ObservationView and a separate training label for training episodes. It never receives Episode.episode_id, Episode.truth, generator arguments, seed values, or generator transition plans. The evaluator alone retains those fields.

The audit reports three increasingly permissive feature tiers. Results must not be collapsed into one score.

### M0 — Identifier surface only

Allowed features:
- identifier prefixes and schemes;
- string lengths and character-class counts;
- equality relationships among evidence ID, sample ID and raw reference;
- counts of identifiers and duplicate/equality patterns.

Forbidden:
- raw identifier token values as categorical features;
- event names, episode IDs, seed values, truth labels;
- evidence polarity, candidate signature, identity state, source-version semantics.

**Interpretation:** performance above the majority baseline indicates a direct identifier-format or identifier-correlation leak. Random opaque tokens should make this tier uninformative.

### M1 — Operational/provenance metadata

Includes M0 plus:
- split and environment labels;
- evidence count, sample count, distinct-window count and per-window record counts;
- window gaps, ordering and presentation-order features;
- expected/observed sample counts, coverage and missing-reason category;
- whether source-version provenance is present, but not its literal semantic value;
- sample reuse, duplicate rate and evidence-to-sample cardinality.

Excludes:
- SUPPORTS / CONTRADICTS / ABSENCE polarity;
- candidate signature content;
- identity presence/status/signature;
- generator event or seed.

**Interpretation:** high M1 performance indicates that episode construction or sampling schedules encode event classes in operational structure. This is benchmark-template leakage even if no identifier contains an event string.

### M2 — Context-shape metadata

Includes M1 plus:
- whether an identity snapshot exists;
- identity status as a categorical field;
- candidate-signature length and coarse syntax shape, but not the literal signature;
- source-version presence/cardinality, but not semantic identity.

Still excludes evidence polarity and literal candidate signature.

**Interpretation:** high M2 performance indicates that the current task's context contract itself may make the event label nearly observable. Report this separately; do not misdescribe it as an identifier leak.

## 3. Attackers and controls

Use only deterministic, dependency-free implementations:
1. majority-class baseline;
2. categorical Naive Bayes with Laplace smoothing;
3. shallow decision tree (maximum depth 3, deterministic feature and threshold tie-breaking).

All preprocessing, binning, vocabulary construction and model fitting use Train only. No Gate statistics may influence feature selection or hyperparameters.

Negative controls:
- permute Train labels with a fixed evaluator-only permutation and verify performance returns to the corresponding null range;
- replace every identifier with an independently sampled opaque token and verify M0 predictions remain invariant in distribution;
- bijectively rename identifiers and permute evidence presentation order; the adjudicator's semantic decision must remain unchanged;
- compare metadata-only predictions with an evidence-aware baseline, without allowing the metadata attacker to access polarity or signature values.

## 4. Data split and execution protocol

- Use disjoint Train and Gate seed ranges and disjoint sample namespaces.
- Keep the current 8 event classes and evaluator-owned truth boundary.
- Use at least 30 independent seed blocks per event for the attack study; report the exact episode count and all exclusions.
- Fit each attacker on Train once, freeze it, then evaluate Gate once.
- No tuning on Gate. No locked Test is opened in this phase.
- If feature engineering changes after inspecting Gate, the result is exploratory and requires a new untouched Gate set.

The current generator has a small number of hand-authored event templates. Therefore this attack is explicitly a test of leakage under the current template family, not a generalization test. A subsequent scenario-diversity experiment must vary nuisance schedules independently of event class.

## 5. Metrics and uncertainty

For every tier and attacker, report:
- accuracy and macro-F1;
- per-class precision, recall and F1;
- confusion matrix;
- majority-baseline lift;
- per-seed-block performance;
- 95% confidence intervals using a seed-block bootstrap (resample blocks, not individual evidence packets).

Report M0, M1 and M2 separately. Include the complete feature allowlist and denylist in the result artifact so the attack is reproducible.

## 6. Pre-registered interpretation

- **M0 failure:** identifier construction still exposes label-correlated structure. Stop and repair provenance before interpreting higher tiers.
- **M0 pass, M1 failure:** identifiers are not the problem; operational sampling/template structure leaks event labels. Redesign the generator so nuisance metadata varies independently of event class.
- **M0/M1 pass, M2 failure:** context-shape fields act as event proxies. Determine whether those fields are legitimate inference inputs or accidental shortcuts, then construct matched counterfactual episodes.
- **All tiers near majority baseline:** no detectable leakage for these attackers and this finite benchmark. This does not prove absence of all side channels or open-world robustness.

For M0, pre-register a practical leakage alarm when Gate macro-F1 exceeds the majority baseline by at least 0.05 and the 95% seed-block bootstrap interval for the lift excludes zero. M1/M2 are diagnostic tiers and are not judged against the same simple pass/fail threshold.

## 7. Falsification and stop conditions

Do not claim metadata isolation if:
- Train/Gate seed or sample namespaces overlap;
- any attacker receives Episode.truth, episode ID, generator seed or event-bearing path;
- feature construction uses Gate labels or Gate-derived vocabulary;
- ID replacement changes adjudicator decisions;
- a result is reported without per-class metrics and uncertainty;
- the event mapping is hard-coded into the attacker's feature extractor.

A high score is a finding, not a reason to weaken the attack. Preserve failing traces and publish the feature-level explanation.

## 8. Explicit non-claims

This preregistration does not claim:
- that opaque random IDs alone establish statistical independence;
- that the current eight event templates represent an open world;
- that event adjudication is autonomous relation discovery;
- that the locked Test has passed;
- that REPLACE, SPLIT or MERGE are implemented;
- that E03 global coordination has demonstrated an advantage over independent selection.

## 9. Next experiments after this audit

1. E02-I2-C-F: scenario diversity with nuisance metadata independently randomized across event classes.
2. E02-I2-C-G: environment and sampling-distribution shifts.
3. E02-I2-C-H: freeze rules and thresholds, then run one evaluator-controlled locked Test.
4. Only after these gates, integrate event proposals with the transactional identity/lineage ledger.
