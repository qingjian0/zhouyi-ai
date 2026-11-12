# CPG-EI Observation Discovery: Support Identifiability Audit v1

## Purpose

This audit hardens interpretation of the observation-only discovery baseline. It does not change the candidate-generation algorithm or claim improved recovery. It makes the evidence boundary around pairwise influence explicit.

## Finding

The baseline infers a variable as relevant only when it finds at least one observed pair of training states that differ in that variable alone and whose target values differ. This is useful positive evidence, but absence of such a pair is not evidence of irrelevance.

Two distinct failure cases must remain separate:

1. **Unobserved counterpart**: the training sample contains no matched pair for that variable. The data provide no direct pairwise influence evidence.
2. **No influence observed, but matched pairs exist**: sampled contexts may not activate a conditional or higher-order interaction. This is still inconclusive without a coverage argument.

For example, with observed states only `00 -> 0` and `10 -> 1`, variable 1 has no observed counterpart pair. A support estimator that returns only variable 0 may understate what the sample can identify.

## Implemented audit

The companion helper `_support_identifiability_audit` reports, for every input variable:

- number of matched pairs observed;
- number of matched pairs with a target flip;
- evidence status: `observed_influence`, `unobserved_counterpart`, or `no_influence_observed_inconclusive`.

The benchmark summary now reports the mean number of unresolved variables and the fraction of rules with any unresolved support evidence. Existing inferred support and candidate selection remain unchanged, allowing direct comparison with the prior baseline.

## Required interpretation

- `observed_influence` is positive evidence of relevance under the sampled contexts.
- `unobserved_counterpart` is an absence of evidence, not evidence of irrelevance.
- `no_influence_observed_inconclusive` does not prove irrelevance; activation contexts may be missing.
- Locked states remain report-only and must not be used to repair support proposals.
- Teacher manifests remain scoring-only after inference.

## Next experiment gate

Before claiming robust support discovery, run controlled coverage sweeps varying:

- train-state fraction and sampling without replacement;
- input dimension and interaction arity;
- conditional activation prevalence;
- sparse and adversarially missing counterpart pairs;
- label noise and missing observations;
- independent teacher families and unseen operator compositions.

Compare pairwise influence with conditional influence tests, sparse Boolean polynomial recovery, decision-tree/ANF baselines, and a learned support proposer. Report support precision/recall, abstention, candidate coverage, and calibration against sample coverage.

## Claim boundary

This is a diagnostic and epistemic-status improvement to a synthetic Boolean benchmark. It is not a learned neural relation-discovery model, not natural-language or Yi-Xue reasoning, and not evidence of superiority to Transformer models.
