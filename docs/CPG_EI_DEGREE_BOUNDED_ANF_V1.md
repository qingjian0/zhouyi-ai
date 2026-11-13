# CPG-EI degree-bounded ANF identifiability v1

## Research question

The complete 8-variable ANF basis has 256 coefficients. The current matched corpus provides 128 training observations per output, producing rank 128 and nullity 128. Does restricting the declared hypothesis class to monomials of degree at most d yield a consistent and uniquely identifiable system, and how does that trade off against excluding the true teacher function?

## Method

For each degree bound d from 0 through input_dim, construct all Boolean monomials whose variable-mask popcount is <= d, including the constant term. Build the GF(2) evaluation system using training rows only. Report basis size, rank, nullity, consistency and uniqueness. Compute the exact full-table ANF degree only as a separately labelled oracle reference; it never enters the partial-observation solver.

For 8 inputs the basis sizes are 1, 9, 37, 93, 163, 219, 247, 255 and 256 for d=0..8.

## Leakage controls

Development and locked labels are excluded from every equation. A regression test mutates all locked labels and requires the complete degree summary (rank, consistency, uniqueness and oracle-in-basis rate) to remain identical. The oracle degree is computed from the full table for interpretation only.

## Reproducibility

Seed 20261114, 64 families, 256 states per family, 8 inputs and 8 outputs (16,384 rows total; 8× the original 8-family matched corpus). The workflow records the generator's corpus SHA-256 and uploads a JSON report bound to the exact commit.

## Interpretation

A low-degree basis may be identifiable but inconsistent with the observed teacher, or consistent but underdetermined. These states must not be conflated. A unique solution under a restricted degree bound is only evidence conditional on that declared hypothesis class; it does not prove the true rule lies in that class unless separately supported by the oracle comparison.

## Claim boundary

Finite synthetic Boolean ANF identifiability only. No claims of cross-family learning, generalization beyond the declared generator, Yi-Xue understanding, causal discovery, natural-language reasoning or superiority to Transformers.
