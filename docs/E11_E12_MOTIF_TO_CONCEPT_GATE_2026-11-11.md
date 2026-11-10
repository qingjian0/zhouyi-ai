# E11 × E12: From Unsupervised Motifs to Defensible Concepts

Date: 2026-11-11
Status: integration protocol / preregistration draft; no empirical result claimed.

## 1. Research question

E12-M2 discovers statistically recurring co-occurrence motifs from unlabeled transactions. E11-A0 proposes recurring attribute conjunctions and evaluates their correspondence to hidden concept schemas. These are related but not equivalent tasks.

The central question is:

> Under what additional evidence may a recurring motif be promoted from a statistical candidate to a reusable concept hypothesis?

A motif must not become a concept merely because it is frequent, has high lift, or passes a permutation test. Statistical dependence is evidence of non-independence under a specified null, not evidence of semantic unity, causal structure, or transferability.

## 2. Capability ladder and terminology

Use four distinct statuses:

1. **MOTIF_CANDIDATE** — a repeated pattern with support/count and an explicit null-model result.
2. **STABLE_MOTIF** — survives held-out samples, environment changes, symbol renaming, and reasonable noise/missingness perturbations.
3. **CONCEPT_HYPOTHESIS** — a motif with a compact operational boundary, predicted membership rule, explicit counterexamples, and a declared scope.
4. **TRANSFERRED_CONCEPT** — the frozen hypothesis predicts on a held-out generator family or novel composition, with no access to evaluator truth.

Do not collapse these statuses into a single "discovered" flag. A candidate may be statistically significant and still fail stability or transfer.

## 3. Data separation and learner interface

The learner receives only immutable observation records:

- opaque object/event ID;
- observed discrete attributes or typed relations;
- environment/context fields only when they are part of the declared observation interface;
- provenance IDs needed to prevent duplicate-source leakage.

The learner must not receive:

- latent concept IDs or memberships;
- hidden schemas;
- generator family labels;
- target motif list;
- evaluator matching assignments;
- locked-test labels or truth.

Evaluator truth must be serialized and stored separately from the learner process for any confirmatory benchmark. The current E11 and E12 in-process objects are development conveniences, not security boundaries.

Every prediction or concept-membership proposal must be frozen before evaluator scoring. Query observations may be unlabeled and visible only according to the declared protocol; their hidden annotations remain evaluator-only.

## 4. Candidate pipeline

### Stage A — Unsupervised proposal

Run at least these candidate proposers on identical learner observations:

- E11 frequent conjunction enumeration;
- E12 support + independence-lift motif mining;
- support-only ranking;
- random candidate generation with matched candidate count/order distribution;
- single-attribute baseline.

Retain the full candidate pool and record proposal cost. Do not let one proposer see candidates produced by another unless testing an explicit shared-pool arm.

### Stage B — Statistical null test

For each motif, use a degree/marginal-preserving null appropriate to the observation structure. Report:

- observed count and support;
- expected support under the null;
- lift / effect size;
- candidate-specific empirical p-value;
- max-statistic or family-wise correction across the searched candidate family;
- permutation-chain diagnostics and effective sample size;
- sensitivity to burn-in, thinning, and independent chains.

A low p-value is not a semantic label. The null test only establishes that the observed co-occurrence is unusual under the declared randomization model.

### Stage C — Stability gate

Evaluate the frozen motif on independent evidence:

- bootstrap/subsample stability;
- object-identity-disjoint repeatability;
- environment-disjoint stability;
- missing/noisy attribute robustness;
- symbol-renaming and input-order invariance;
- nuisance-cue reversal;
- generator-family transfer.

Report candidate-set precision/recall and Jaccard stability after canonicalization. Do not match each hidden concept independently to its best candidate as the primary metric. Use one-to-one assignment or assignment-free set metrics, and keep oracle best-match scores explicitly diagnostic.

### Stage D — Concept hypothesis gate

A stable motif can become a concept hypothesis only if it has:

- a frozen executable membership predicate;
- explicit scope and required context;
- positive support and hard counterexamples;
- a declared abstention region for missing/ambiguous evidence;
- a complexity charge (description length or equivalent);
- a prospective prediction that is evaluated on new objects/events.

A concept hypothesis must not be defined by its evaluator-side latent schema after the fact. Its boundary must be learner-generated and frozen before scoring.

### Stage E — Transfer gate

Test the frozen concept predicate on:
- unseen object identities;
- unseen combinations of known attributes;
- unseen environments;
- generator-family-disjoint data;
- altered surface symbols;
- overlapping concepts and shared attributes;
- concept counts and schema sizes not fixed to the training setting.

A motif that only survives an IID object split is not yet a transferable concept.

## 5. Primary comparisons

All arms use identical observations, split manifests, proposal/evaluation budgets, and locked-test access.

| Arm | Proposal source | Selection / validation |
|---|---|---|
| A | E11 frequent conjunctions | frequency threshold |
| B | E12 motifs | support + lift + conditional null |
| C | random motifs | same order/count budget + same null |
| D | single attributes | frequency baseline |
| E | E11 + E12 union | deduplicate canonical extensions, then shared validation |
| F | shuffled/marginal-preserving data | negative control |

An additional ablation should remove the null gate from B/E to quantify whether the permutation test improves false-discovery control. Another should remove the stability gate to quantify IID overfitting.

No method may receive more candidate evaluations or more permutation draws without reporting a separate cost-matched curve.

## 6. Metrics

Report by seed, generator family, and environment:

- candidate count and candidate-generation cost;
- candidate-specific and family-wise false discovery;
- motif support, lift, and null effect size;
- stability under resampling and perturbation;
- one-to-one concept precision/recall/F1 or assignment-free set metrics;
- concept-count estimate error and abstention quality;
- held-out predictive utility;
- generator-family and compositional OOD performance;
- false concept promotion rate;
- complexity / description length;
- runtime, memory, permutation count, and effective sample size.

All empty-positive and unidentifiable episodes must remain in the denominator with a predeclared scoring rule. Report coverage beside selective accuracy.

## 7. Falsification criteria

The "motif-to-concept" claim fails or must be narrowed if any of the following occur:

1. The same motif scores similarly under the marginal-preserving null.
2. Candidate stability collapses under small changes in sample, environment, or missingness.
3. Nuisance-cue reversal changes the selected concept boundary without a corresponding scope/abstention response.
4. The concept predicate does not predict held-out observations better than frequency, random, or single-feature controls at matched cost.
5. One-to-one matching shows that multiple candidates are duplicates of the same hidden structure or that candidate count is systematically wrong.
6. Performance depends on evaluator-side matching, hidden schemas, or generator metadata.
7. A motif passes statistical significance but fails transfer; in that case it remains a dataset-specific motif, not a reusable concept.

## 8. Relation to Zhouyi-inspired priors

Only after the generic motif-to-concept pipeline is validated should Zhouyi-inspired structures enter as proposal priors.

Compare, at matched proposal and compute budgets:

- no prior;
- generic learned prior;
- Yin/Yang complementary partition prior;
- four-state / trigram factorization prior;
- randomized or permuted Zhouyi mapping;
- deliberately misaligned prior.

The prior may influence which candidate is proposed first, but it must not bypass null testing, stability, evidence gates, or abstention. A misaligned prior that causes confident false promotion is a meaningful negative result.

## 9. Execution order

1. Freeze E11-A0.1 robust generator and one-to-one evaluation interfaces.
2. Freeze E12-M2 motif miner and its permutation/calibration interfaces.
3. Build a common observation schema and canonical candidate representation.
4. Run development seeds to validate data contracts and compute accounting.
5. Preregister locked seeds, primary metrics, thresholds, and failure criteria.
6. Run the confirmatory benchmark once; retain all failed seeds and null episodes.
7. Only then test hierarchy induction and active experiment selection.

## 10. Current status and limitations

This document is an integration contract, not an implementation or benchmark result. It does not assert that E11-A0, E12-M2, or their combination discovers semantic concepts. The first implementation should be a thin runner over existing modules, not a third independent motif algorithm. Existing E11/E12 branches remain separate and are not modified by this document.
