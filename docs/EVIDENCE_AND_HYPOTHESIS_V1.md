# Evidence Evaluation and Hypothesis Registry v1

Status: first deterministic research-governance implementation; statistical validation and end-to-end integration remain pending.

## Hypothesis records

A hypothesis is an immutable, versioned record containing a falsifiable statement, proposed mechanism, predicted effect direction, scope, explicit falsification criteria, and optional parent hypothesis. The filesystem store writes one JSON record per ID and refuses overwrites. Each record carries a canonical SHA-256 integrity digest. The store uses atomic hard-link publication; the target filesystem must support hard links.

A new version should use a new ID and may reference the prior record through parent_id. This avoids rewriting historical claims after seeing outcomes.

## Evidence evaluator

The evaluate_evidence function consumes independently analysed comparison rows. Every row must identify its split (iid or ood), control (none, shuffled, random), effect estimate, confidence interval, seed count, validity, and preregistration status.

- Invalid, non-preregistered, or below-minimum-seed rows are excluded.
- A row is favorable only if its entire supplied confidence interval is on the predicted side of zero.
- supported requires favorable OOD and favorable shuffled/random-control evidence from two distinct evidence rows; one row cannot satisfy both gates.
- An adverse OOD or control row yields rejected.
- All other cases are inconclusive.

## Scientific limits

This module does not calculate confidence intervals, perform multiplicity correction, estimate statistical power, verify preregistration timestamps, or inspect raw per-seed observations. It trusts supplied analysis fields and is intentionally conservative. A verdict is a review gate, not a claim that a theory is true. Distinct evidence-row IDs are required for the OOD and control support gates to prevent double-counting. IID-only improvement is insufficient. Yijing- or Taixuanjing-inspired priors must compete against shuffled and random controls with matched budgets.

## Next integration gate

Add an analysis adapter that converts archived per-seed experiment outputs into preregistered evidence rows. The adapter must validate task-set identity, missing/failed seeds, metric direction, OOD split provenance, and control matching before invoking this evaluator. Do not connect scheduler completion directly to supported.
