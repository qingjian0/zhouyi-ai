# P5-B: linear recurrence comparison baseline

This adds a trainable diagonal linear recurrence to compare against
`DiagonalGatedRNN`. The transition is
`h[t] = tanh(a) * h[t-1] + b*x[t] + c`; the output head is logistic.
It uses explicit full-sequence BPTT, SGD, and global gradient clipping.

Parameter counts:
- gated model: 7H + 1
- linear model: 4H + 1

For an approximate parameter-matched comparison, choose linear hidden size
near 1.75 times the gated hidden size (for example gated H=4 gives 29
parameters; linear H=7 gives 29). Report exact counts rather than claiming
identical architectures.

Both models currently train binary next-symbol prediction only. Chunk-state
continuity is tested, but delayed-copy, associative recall, distractor
robustness, language modeling, selective SSM, and long-context generalization
are not yet implemented or demonstrated. The linear model is a baseline, not
a substitute for a full controlled benchmark.
