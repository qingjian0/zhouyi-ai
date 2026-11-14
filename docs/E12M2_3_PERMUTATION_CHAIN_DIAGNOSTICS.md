# E12-M2.3 — Permutation-chain mixing diagnostics

## Motivation

The M2.1 conditional null uses bipartite 2-switches. A valid switch preserves
all row cardinalities and item marginal counts, but this invariance alone does
not establish that a finite Markov chain has mixed or that its samples are
uniform over all realizations with those margins.

M2.3 adds an explicitly diagnostic multi-chain runner:

- independent pseudorandom streams, each initialized from the observed graph;
- configurable burn-in and thinning, measured in attempted switches per edge;
- candidate motif-score traces;
- per-chain score mean, variance, range, lag-1 autocorrelation, and an
  initial-positive-sequence ESS approximation;
- acceptance rates and between-chain mean dispersion.

## Run

```bash
python - <<'PY'
from prototype.e12m2_m2_calibration import make_fixed_margin_dataset
from prototype.e12m2_chain_diagnostics import diagnose_permutation_chains

rows = make_fixed_margin_dataset(seed=17)
report = diagnose_permutation_chains(
    rows, ("item_0", "item_1"),
    chains=4,
    samples_per_chain=200,
    burn_in_swaps_per_edge=30,
    thinning_swaps_per_edge=5,
    seed=91,
)
print(report)
PY
```

## Interpretation protocol

Do not treat a high acceptance rate as evidence of mixing. Compare score
traces, lag-1 autocorrelation, ESS, between-chain means, and sensitivity to
longer burn-in and thinning. Run multiple seeds and graph families, including
heterogeneous row degrees and skewed item margins, before trusting the null.

The ESS value is a lightweight initial-positive-sequence approximation, not a
substitute for a validated MCMC diagnostic suite. Chains share the same initial
observed graph; distinct RNG streams alone do not guarantee independent
stationary samples. The report deliberately emits a warning stating these
limitations.

## Next experiment

M2.3's next gate is a sensitivity matrix over burn-in, thinning, and graph
density, with repeated independent datasets. Only after the null sampler's
mixing behavior is characterized should the project report a larger type-I
error calibration or motif-recovery power curve. Do not interpret synthetic
pair recovery as semantic understanding, causal discovery, or general
intelligence.


## Heterogeneous-graph sensitivity runner

M2.3 now includes a reproducible sensitivity-grid runner and a second synthetic
graph family with variable row degrees and Zipf-like item popularity.

```bash
python - <<'PY'
from prototype.e12m2_mixing_sensitivity import run_mixing_sensitivity

result = run_mixing_sensitivity(
    dataset_seeds=5,
    chains=4,
    samples_per_chain=100,
    burn_in_grid=(0, 5, 20, 50),
    thinning_grid=(1, 3, 10),
    seed_start=500,
)
for configuration in result["configurations"]:
    print(configuration)
print("margin profiles:", result["margin_profiles"])
PY
```

The runner reports, per burn-in/thinning configuration, mean normalized ESS,
mean lag-1 autocorrelation, between-chain score-mean variance, and acceptance
rate across generated datasets. It also reports row-degree and item-degree
summaries, including item-degree Gini concentration.

This is a sensitivity experiment, not a proof of sampler correctness. The
heterogeneous generator is a synthetic family with a Zipf-like weighting rule;
its results must not be generalized to arbitrary real incidence graphs. A
future validation stage should include exact-enumerable small graphs, known
stationary-frequency checks, and multiple graph families before treating the
2-switch null as calibrated.


## Exact finite-state kernel audit

A separate exact audit enumerates all simple bipartite graphs for a supplied
small degree sequence, builds the directed 2-switch transition graph, checks
connectivity, and compares forward/reverse proposal multiplicities.

```python
from prototype.e12m2_exact_state_audit import audit_small_state_space

print(audit_small_state_space(
    row_degrees=(1, 1),
    item_degrees={"a": 1, "b": 1},
))
```

For the 2x2 example there are exactly two realizations; the 2-switch graph is
connected and each direction has equal proposal multiplicity. This supports a
uniform stationary distribution for that finite example when the proposal
kernel includes its natural self-loop probability. It does not establish
finite-time mixing, nor does one example prove connectivity for every degree
sequence. The audit is deliberately state-capped because exhaustive
enumeration grows combinatorially.
