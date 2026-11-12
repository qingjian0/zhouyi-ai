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

## Decision rule

Use locked accuracy only as a diagnostic with its small 12-state denominator; require consistency across both seeds and all three families. A configuration that only improves training or full-domain score is not accepted as a generalization improvement. If all settings plateau, investigate model parameterization, gate saturation and feature conditioning before increasing search complexity.

## Claim boundary

This is a finite synthetic benchmark with oracle-supplied support. It does not establish open-world relation induction, natural-language reasoning, or end-to-end training readiness.
