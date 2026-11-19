# P5-B: diagonal gated recurrent baseline

Status: first executable reference baseline; not a production sequence model.

## Model

`prototype/diagonal_gated_rnn.py` implements a diagonal gated recurrent
state update with a shared logistic next-symbol head. It uses explicit manual
backpropagation through time (BPTT), SGD, and global gradient clipping. It has
no third-party runtime dependency and carries hidden state explicitly across
chunks.

For each hidden dimension:

- candidate = tanh(Wx*x + Wh*h_previous + b)
- gate = sigmoid(Ux*x + Uh*h_previous + c)
- h = gate*candidate + (1-gate)*h_previous
- p(next_symbol=1) = sigmoid(V·h + d)

## Scope and limitations

This is a trainable recurrent *mechanics baseline* on binary next-symbol
prediction. It is not a tokenizer, language model, embedding stack, general
sequence learner, selective SSM, or evidence of long-context reasoning. The
diagonal transition omits cross-dimension recurrent mixing. Full-sequence BPTT
uses memory proportional to the training sequence length; truncated BPTT,
streaming optimizer state, batching, mixed precision, and accelerator kernels
are not implemented.

## Required next comparisons

1. Add a matched-parameter linear recurrence baseline.
2. Add a selective state-space baseline under the same data and compute budget.
3. Evaluate periodic, delayed-copy, associative-recall, distractor, and
   distribution-shift tasks with held-out seeds and lengths.
4. Record loss curves, parameter counts, throughput, peak memory, and
   state-carry equivalence across chunk boundaries.
5. Only after the synthetic protocol is stable, connect learned representations
   to classiang tasks and measure transfer against symbolic and non-classiang
   ablations.

No 1M-token input or output claim is made by this change.
