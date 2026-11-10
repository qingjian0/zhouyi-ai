# E12-A2-M Input Validation Hardening Audit

Status: narrow correctness hardening proposal; tests are authored but must be run by CI on this exact branch head.

## Finding

The initial selector validated remaining_budget, epsilon, and tie_tolerance by calling float(value). This unintentionally accepted booleans (for example, True) and numeric strings. Action costs also accepted zero, although the protocol describes a positive measurement cost and utility is defined as IG / (cost + epsilon).

These inputs make the public API less strict than the prior-weight and likelihood validators and can make cost semantics ambiguous.

## Change

- Add one finite-real validator that accepts only Python int/float and explicitly rejects bool.
- Validate budget, epsilon, and tie tolerance before comparisons.
- Require measurement costs to be strictly positive and finite.
- Add regression tests for boolean/string budget parameters, boolean epsilon/tolerance, and zero/boolean costs.

## Non-goals

No change to entropy, expected information gain, posterior update, tie-breaking, action ranking, candidate semantics, or the evaluator boundary. No benchmark result or algorithmic advantage is claimed.

## Validation required

Run the focused E12-A2-M tests and the complete repository test suite on the exact branch head. This audit is not considered complete until CI passes.
