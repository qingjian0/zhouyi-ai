# P5-B: recurrent benchmark protocol v0.1

Status: task generators and gradient checks are being introduced. This is a
protocol foundation, not a completed model comparison or capability result.

## Controlled task families

`prototype/recurrent_benchmark_tasks.py` emits deterministic binary
context/target episodes with explicit seeds and task metadata:

- periodic next-symbol prediction;
- delayed copy after a distractor gap;
- key/value associative recall;
- recall with repeated decoy delimiters;
- periodic-regime distribution shift with distinct train/evaluation periods.

The same immutable `SequenceExample` instances can be passed to every model.
A training sequence is context plus target, while evaluation must score the
probability emitted after consuming context. Do not train on evaluation seeds.

## Required experimental controls

1. Fix and publish train/evaluation seeds and episode counts.
2. Report exact parameter counts; use gated H=4 and linear H=7 for the
   existing 29-parameter matched pair.
3. Hold episode count, total supervised symbols, optimizer, learning rate,
   clipping, update count, and initialization protocol constant.
4. Sweep context/gap lengths independently; do not infer long-range ability
   from a single length.
5. Report binary cross-entropy, accuracy, per-length degradation, examples/s,
   symbols/s, peak RSS, and explicit chunk-state equivalence.
6. Run multiple seeds and publish mean, standard deviation, and raw results.
7. Keep a held-out task/length split for compositional and length generalization.

## Gradient correctness gate

`tests/test_recurrent_bptt_gradients.py` compares manual BPTT updates with
central finite differences for every scalar parameter in small gated and
linear models. A model must pass this gate before benchmark comparisons are
interpreted. Gradient checks do not prove optimization quality or generalization.

## Claim boundaries

These synthetic binary tasks are mechanism tests, not natural-language
understanding. Passing them does not establish language modeling, million-token
input, million-token output, mobile feasibility, or classiang transfer. Those
require separate end-to-end tokenizer, memory, cognition, and hardware gates.
