# CPG-EI joint motif diagnostic — 2026-11-12

## Scope

The bounded proposal operator evaluates 20 four-edge motifs (three pairwise conjunctions plus one matching third-order relation). It selects candidates by training binary cross-entropy; validation is held out and reported after selection.

## Exact-head result

PR #363 head: `5f7b0933404cd7344e2aa41c86d308272d40ed9b`.

Workflow run #43211461122 succeeded. The test job ran 9 tests in 203.58 seconds.

### Initial two-seed proposal diagnostic

| Seed | Active edges | Support precision | Support recall |
|---:|---:|---:|---:|
| 11 | 4 | 1.000 | 0.333 |
| 23 | 4 | 1.000 | 0.333 |

This confirms that a bounded joint proposal can recover a subset of synergistic planted relations in the finite synthetic universe. It does not establish full support discovery.

### Matched-compute comparison (seed 11)

| Metric | Joint motifs | Greedy |
|---|---:|---:|
| Training passes | 696 | 700 |
| Relative budget gap | 0.571% | — |
| Active edges | 12 | 13 |
| Support precision | 1.000 | 0.923 |
| Support recall | 1.000 | 1.000 |
| Held-out validation bit accuracy | 0.5365 | 0.8229 |

The near-matched compute comparison shows equal planted-support recall and higher support precision for joint motifs, but substantially worse held-out predictive accuracy. This is a material counter-signal: the current training-BCE candidate selection can produce a structurally attractive support set without generalizing well.

## Decision

- Keep joint motifs as an experimental proposal strategy only.
- Do not replace greedy discovery or make joint proposals the default.
- Report structural support metrics and held-out predictive metrics separately.
- Next validation should test multiple seeds, calibrate candidate selection against a validation protocol that does not leak test data, and inspect whether motif-group regularization or minimum improvement thresholds improve generalization.
- Do not claim open-ended relation discovery: the search space is explicitly bounded to 20 motifs.


### Second parity teacher cross-check (exact head 2026-11-12)

- Current PR #363 head: `75b8994567d8b2b07d1d7fa8589706a2f47e75df`; workflow #43213671969 succeeded (9 tests).
- The distinct GF(2) three-input parity teacher diagnostic (greedy residual growth, 3 seeds) reports mean support precision 1.000, mean support recall 0.3056, mean validation bit accuracy 0.6337, zero false discoveries, and exact support recovery 0/3.
- This is a second counter-signal: the finite model's exact 12-edge parity support is representationally sufficient (oracle test reaches 100% bit and exact-state accuracy), but current greedy structure growth does not recover most of that support. High precision here means the selected edges are plausible, not that discovery is complete.
- Combined with the joint-vs-greedy matched-compute result above, do not promote joint motifs: its first teacher seed recovered full support but validation accuracy was only 0.5365 vs greedy 0.8229. More seeds and a clean train/selection/locked-test protocol are required.
