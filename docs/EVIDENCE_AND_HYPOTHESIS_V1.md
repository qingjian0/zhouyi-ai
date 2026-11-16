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

## Current integration state

The paired raw-observation analyzer now converts task outputs into evidence rows using matched seed, split, control, parameter-count, and compute-budget keys. The archive adapter verifies the archive digest and structural provenance before evaluation. The active experiment selector ranks researcher-authored, preregistered candidates against explicit evidence gaps and a compute budget.

## Next integration gate

Build a raw-observation producer contract for actual experiment handlers and preserve per-seed raw outputs as immutable artifacts. Then add end-to-end tests from ExperimentMatrix TaskSpec -> handler observations -> raw analyzer -> archive -> evidence evaluator -> candidate selector. The producer must bind observation IDs to task IDs and verify split/control provenance. Do not connect scheduler completion directly to supported.
