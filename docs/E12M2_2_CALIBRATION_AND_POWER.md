# E12-M2.2 — Null calibration and planted-motif recovery

## Purpose

M2.1 introduced a degree-preserving conditional null. M2.2 adds a controlled
synthetic harness to measure two distinct properties:

- **Type-I diagnostic:** how often a pre-specified pair is rejected in data
  generated without planting that pair.
- **Power diagnostic:** how often the planted pair is detected after controlled
  degree-preserving injections.

The generator creates a balanced bipartite incidence graph. Every row has the
same cardinality and every item has the same marginal count. A planted injection
uses a legal 2-switch, so it increases the target pair's joint count without
changing either margin.

## Run

```bash
python -m prototype.e12m2_m2_calibration --seeds 10 --permutations 39 --swaps-per-edge 3 --injections 12 --json
```

The program emits null and planted candidate-specific p-values, max-statistic
p-values, rejection/detection rates with 95% Wilson score intervals,
applied injections, pair-count gains, and mean swap acceptance rate.

## Interpretation

This is a harness, not yet a benchmark result. The defaults are intentionally
small enough for quick iteration. A p-value grid with B permutations has
minimum attainable value 1/(B+1); with 39 permutations the minimum is 0.025.
That resolution is too coarse for a stable 0.05 calibration estimate across
only ten seeds.

For credible calibration, increase independent datasets substantially, use
hundreds or thousands of permutations per dataset, and report binomial
confidence intervals around rejection/detection rates. Compare independent
chains and inspect acceptance and autocorrelation. The current implementation
reports acceptance but does not claim that its Markov chain has mixed.

## Important limitations

- The null and planted data are synthetic and balanced; real observations may
  have heterogeneous row degrees and item marginals.
- The tested pair is pre-specified. The max-statistic result addresses a
  bounded candidate search, but does not cover arbitrary downstream selection.
- Pair injection creates a known association, not a semantic concept or causal
  mechanism.
- No neural architecture or training advantage is demonstrated here.
- A failed null calibration or poor power result should block claims of
  motif-discovery validity until the null sampler or statistic is revised.
