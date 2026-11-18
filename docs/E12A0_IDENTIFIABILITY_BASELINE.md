# E12-A0 protocol

Run:

```bash
python -m unittest tests.test_e12a_identifiability -v
python -m prototype.e12a_identifiability --seeds 100 --start-seed 7 --json
```

The first implementation is deliberately a finite two-predicate sanity check:
- `ge2(x) = [x >= 2]`
- `eq2(x) = [x == 2]`

Support values {0, 2} make the two candidates observationally equivalent. Adding value 3 distinguishes them. The intervention-pending arm permits the learner to request value 3 but does not reveal its outcome until the environment applies the probe. The unobservable arm restricts the domain to {0, 2}, so the alternatives remain equivalent under all available measurements.

Expected protocol behavior:
- identifiable: IDENTIFIABLE and correct candidate;
- ambiguous: AMBIGUOUS;
- intervention pending: AMBIGUOUS before probe, IDENTIFIABLE after probe;
- unobservable: AMBIGUOUS;
- inconsistent: INCONSISTENT;
- insufficient search budget: BUDGET_EXHAUSTED.

This is a software/protocol sanity check only. The grammar is known and tiny, and it does not demonstrate learning new predicates, causal discovery, or open-world autonomy. The next stage must expand the grammar and add a genuinely separate evaluator process with hidden truth inaccessible to learner code.
