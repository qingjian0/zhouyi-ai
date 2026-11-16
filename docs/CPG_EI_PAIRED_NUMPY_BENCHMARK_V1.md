# CPG-EI paired Python/NumPy hybrid benchmark

## Motivation

PR #426 established NumPy numerical parity and measured the accelerated hybrid on the fixed eight-family corpus. Its Python timing came from the parent PR #422, a separate CI run. The timing ratio is therefore indicative rather than a paired comparison.

This follow-up measures both backends in the same CI job and process against the same in-memory corpus object, interpreter, optimizer settings, and locked states.

## Protocol

- Dataset: seed 20261114, 8 families, 8 inputs, 8 outputs, 2,048 rows.
- Corpus digest is asserted against the #422/#426 baseline.
- Python reference runs first; NumPy runs second.
- One full run per backend; this is a paired single-run measurement, not a timing distribution.
- Both use 600 max epochs, patience 30, min-delta 1e-5, learning rate 0.1, L2 1e-4, zero initialization.
- Corpus generation is excluded from method timing.
- Tracemalloc peak deltas are measured separately for each backend.
- Locked labels remain report-only.

## Correctness gates

The benchmark fails if:
- family-level predictions differ on any of the 256 states;
- feature bases differ;
- locked aggregate metrics differ.

It also reports per-output selected-epoch and exact weight-digest matches. Floating-point implementations may produce different weight bytes while retaining identical decisions; those are reported separately rather than silently conflated with prediction parity.

## Interpretation

A same-job timing comparison reduces runner and runtime confounding, but one measurement per backend is not a performance distribution. Treat the timing ratio as a single-run observation. Repeat on additional runners before claiming a stable speedup.

This remains a synthetic finite Boolean benchmark. It does not establish cross-family transfer, open-world relation discovery, Yi-Xue understanding, causal discovery, language reasoning, or Transformer superiority.
