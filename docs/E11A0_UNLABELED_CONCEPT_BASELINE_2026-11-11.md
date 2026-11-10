# E11-A0: Unlabeled Recurring-Substructure Baseline

Date: 2026-11-11  
Status: implementation scaffold; repository CI and exact test execution pending.

## Question

Can a learner propose reusable candidate concepts from object observations without receiving concept names, concept counts, or object-to-concept membership labels?

E11-A0 is the first executable control, not the target architecture. It asks whether a simple recurring-substructure baseline can recover useful regularities on object-identity-disjoint observations.

## Data contract

- The generator plants three latent concepts, each represented by a conjunction of three opaque attributes.
- Objects may instantiate zero, one, or several latent concepts; overlap is allowed.
- Learner objects expose only opaque object IDs and attribute sets.
- Query objects have disjoint object IDs.
- Latent concept IDs, schemas, and memberships are stored in evaluator-side `Episode.truth` / `Episode.hidden_schemas` fields.
- `propose_concepts()` and `predict()` accept only learner/query object views; neither accepts evaluator truth.

This is an in-process benchmark boundary, not a security boundary. Evaluator and learner data coexist in one Python object.

## Learner

The baseline enumerates attribute conjunctions of order 1 through `max_order` and retains those whose empirical learner support meets `min_support`. Predictions are candidate-presence indicators on held-out objects.

## Evaluation correction

The original per-concept best query-set F1 is retained only as an optimistic oracle diagnostic: it permits the same candidate to match several hidden concepts. It is not a valid one-to-one concept-discovery score.

The evaluator additionally:
- deduplicates candidate patterns by their query-set extension;
- computes an exact maximum-weight one-to-one matching between unique candidate extensions and hidden concepts;
- ensures each candidate extension and each hidden concept is used at most once;
- reports one-to-one mean F1, candidate precision, concept recall, matched/unmatched candidate counts, and selected matches.

The exact dynamic-programming matcher is bounded to at most 16 evaluator concepts. It is still an evaluator-side metric, not a learner-side concept assignment mechanism.

## Required controls in this increment

- Object-identity-disjoint learner/query split.
- Opaque-symbol renaming invariance.
- Input-order invariance.
- Explicit learner API that receives no truth labels.
- Parameter validation and reproducible seeded generation.
- Adversarial test proving one candidate cannot be credited to two concepts.
- Duplicate-extension test proving syntactically different candidates with identical query behavior do not inflate the discovered-concept count.
- Per-concept optimistic diagnostics plus one-to-one scores, candidate precision, and concept recall.

## Known limitations / threats

1. The generator has exactly three planted conjunction concepts. Unknown concept count is not tested.
2. Attribute conjunctions are the hypothesis class. The learner cannot discover relational, causal, temporal, functional, or non-conjunctive concepts.
3. Frequent-pattern enumeration is a standard baseline and may select nuisance patterns. No MDL, predictive-compression, intervention, or causal utility test is implemented yet.
4. Best-match F1 remains an optimistic evaluator oracle and can overstate deployable concept assignment quality. The one-to-one metric corrects candidate reuse but still uses hidden truth for scoring.
5. One fixed generator family does not establish distributional or open-world generalization.
6. Co-resident evaluator truth is not process isolation. A future runner should serialize learner input separately and keep evaluator truth outside the learner process.
7. No empirical performance claim is made until exact repository tests and a multi-seed benchmark are executed on the committed code.

## Next falsification steps

- Add flat single-feature, random-pattern, and fixed-ontology baselines.
- Add a nuisance-correlated generator arm where frequent patterns are not concept-defining.
- Add unknown concept counts, variable schema sizes, missing attributes, and contradictory/noisy evidence.
- Test object-disjoint and generator-family-disjoint transfer separately.
- Add a predictive-compression or MDL score and compare it with frequency-only selection under equal candidate/search budgets.
- Add a role-sensitive relational motif arm before claiming concepts beyond attribute bundles.
- Only after these controls, test concept boundary revision from counterexamples.

## Reproduction

```bash
python -m unittest discover -s tests -p 'test_e11a_unlabeled_concepts.py' -v
python -m prototype.e11a_unlabeled_concepts --json --seed 17
```

No test pass, CI pass, or autonomous concept-discovery claim is asserted here.
