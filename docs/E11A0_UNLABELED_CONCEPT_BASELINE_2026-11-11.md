# E11-A0: Unlabeled Recurring-Substructure Baseline

Date: 2026-11-11  
Status: implementation scaffold; repository CI and exact test execution pending.

## Question

Can a learner propose reusable candidate concepts from object observations without receiving concept names, concept counts, or object-to-concept membership labels?

E11-A0 is the first executable control, not the target architecture. It asks whether even a simple recurring-substructure baseline can recover useful regularities on object-identity-disjoint observations.

## Data contract

- Generator plants three latent concepts, each represented by a conjunction of three opaque attributes.
- Objects may instantiate zero, one, or several latent concepts; overlap is allowed.
- Learner objects expose only opaque object IDs and attribute sets.
- Query objects have disjoint object IDs.
- Latent concept IDs, schemas, and memberships are stored in evaluator-side `Episode.truth` / `Episode.hidden_schemas` fields.
- `propose_concepts()` and `predict()` accept only learner/query object views; neither accepts evaluator truth.

This is an in-process benchmark boundary, not a security boundary. The evaluator and learner data coexist in one Python object.

## Learner

The baseline enumerates attribute conjunctions of order 1 through `max_order` and retains those whose empirical learner support meets `min_support`. Predictions are candidate-presence indicators on held-out objects.

Evaluation reports, for each hidden concept, the best query-set F1 among proposed candidates. This is a diagnostic oracle matching metric: it is useful for checking whether a candidate exists, but it is not an operational mechanism for assigning discovered candidate identities to latent concepts. The mean across planted concepts is reported.

## Evaluation correction\n\nA candidate extension that overlaps multiple latent concepts cannot be counted as discovering all of them. Syntactically different candidates with identical held-out extensions are collapsed before matching, preventing duplicate patterns from inflating concept count. The one-to-one score complements rather than replaces the optimistic best-match diagnostic.\n\n## Required controls in this increment

- Object-identity-disjoint learner/query split.
- Opaque-symbol renaming invariance.
- Input-order invariance.
- Explicit learner API that receives no truth labels.
- Parameter validation and reproducible seeded generation.
- Per-concept optimistic diagnostic and one-to-one matched scores, not only an aggregate.\n- Candidate precision, concept recall, and unmatched candidate-extension counts.

## Known limitations / threats

1. The generator has exactly three planted conjunction concepts. Unknown concept count is not tested.
2. Attribute conjunctions are the hypothesis class. The learner cannot discover relational, causal, temporal, functional, or non-conjunctive concepts.
3. Frequent-pattern enumeration is a standard baseline and may select nuisance patterns. No MDL, predictive-compression, intervention, or causal utility test is implemented yet.
4. Best-match F1 is an evaluator oracle and can overstate deployable concept assignment quality. A future track must use a frozen unsupervised matching rule or report assignment-free set metrics.
5. One fixed generator family does not establish distributional or open-world generalization.
6. Co-resident evaluator truth is not process isolation. A future runner should serialize learner input separately and keep evaluator truth outside the learner process.
7. No empirical performance claim is made until the exact repository tests and a multi-seed benchmark are executed on the committed code.

## Next falsification steps

- Add a flat single-feature baseline and random-pattern baseline.
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
