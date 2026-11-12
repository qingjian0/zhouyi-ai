# CPG-EI known-support optimizer sweep

## Question

Does the current low-data parity failure come from candidate discovery, optimizer settings, or the model/data regime?

PR #388's five-seed, three-family sweep showed that the exact-support oracle remains near 52% locked accuracy after 500 epochs, while full-universe in-sample accuracy is 87.5%. Search-strength and default regularization were close, so regularization alone is unlikely to explain the gap.

## Protocol

- Use two fixed seeds (11, 47), three finite six-bit parity families, 40 training states and 12 locked states.
- Supply the true pair/triple support to the model to isolate optimization from support discovery.
- Sweep learning rates 0.05, 0.15, 0.35 and 0.7 for 800 epochs.
- Compare the existing search-strength regularization with model-default regularization.
- Fit only on the 40 training states. The 12 locked states are evaluation-only.
- Report train, locked and complete 64-state domain accuracy separately, plus final BCE.
- The complete-domain score is a diagnostic over the finite truth table, not an OOD claim.

## Selection and leakage control

- The only configuration-ranking metric is mean final training BCE over the fixed seed/family set.
- Locked accuracy and complete-domain accuracy are report-only diagnostics. They are not used to select, rank, or tune configurations.
- The 12-state locked denominator is small; interpret per-seed/per-family outcomes rather than treating a pooled mean as a stable generalization estimate.
- This sweep is diagnostic, not a replacement for a separately preregistered validation split or independent confirmation seeds.

## Decision rule

If all settings plateau, investigate model parameterization, gate saturation, feature conditioning, and optimizer dynamics before increasing search complexity. Any follow-up configuration selected from validation data must be evaluated once on a fresh, untouched test split.

## Claim boundary

This is a finite synthetic benchmark with oracle-supplied support. It does not establish open-world relation induction, natural-language reasoning, or end-to-end training readiness.
