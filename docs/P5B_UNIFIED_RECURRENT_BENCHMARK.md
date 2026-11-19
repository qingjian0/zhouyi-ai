# P5-B unified recurrent benchmark

Status: reproducible synthetic benchmark runner added; no comparative result is
asserted by the runner's existence alone.

## Run

```bash
python -m prototype.recurrent_benchmark --task delayed_copy \
  --train-examples 128 --eval-examples 128 --epochs 5 --gap-length 16
```

Tasks: `periodic`, `delayed_copy`, `associative_recall`, and
`distractor_recall`. The default run uses three deterministic seeds. JSON
output records model, seed, exact parameter count, training updates/loss/time,
evaluation binary cross-entropy, accuracy, throughput, traced Python peak
memory, and chunk-state parity.

## Fairness controls and limitations

- The two reference models are parameter matched at 29 parameters
  (gated hidden size 4; linear hidden size 7).
- Both receive the same train/evaluation examples for a seed and the same
  number of sequence updates and epochs.
- Training currently uses next-symbol loss across the complete context plus
  target sequence. Evaluation scores only the final target after consuming the
  context. This distinction is explicit: the runner is a controlled baseline,
  not a target-only supervised protocol.
- Initializers are architecture-specific; identical integer seeds do not imply
  identical parameter distributions.
- `tracemalloc` measures Python-tracked allocations, not process RSS or device
  memory. Hardware memory profiling remains a separate gate.
- The default three seeds are a smoke/reproducibility baseline, not enough for
  a strong statistical claim. Increase seeds and publish raw JSON for research.

Passing this benchmark does not establish natural-language capability,
million-token input/output, or mobile feasibility. Those remain separate
P5-A/P5-C/P5-D/P5-E/P5-F acceptance gates.
