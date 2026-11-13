# CPG-EI ANF identifiability oracle

## Purpose

Add an independent algebraic reference for Boolean relations and quantify what can
and cannot be identified from partial observations. This is an oracle and a
diagnostic, not a learned relation-discovery model.

## Exact ANF reference

For an input dimension d, every Boolean function has a unique algebraic normal
form over GF(2), with 2^d possible monomials including the constant. The
Möbius transform of the complete truth table returns the exact coefficient
vector. Variable bit i denotes x_i; coefficient masks use little-endian indexing.

The full truth table is used only to compute the explicitly labelled oracle
reference. It is not supplied to the partial-observation solver.

## Partial-observation identifiability

Each observed state contributes one linear equation over GF(2), with one
column per possible ANF monomial. Gaussian elimination returns:
- consistency and matrix rank;
- nullity (dimension of the affine solution space);
- whether the coefficient vector is unique;
- a particular solution plus a nullspace basis when consistent;
- coefficient-level forced-zero, forced-one, or ambiguous status;
- variables that are definitely relevant, possibly relevant, or definitely irrelevant.

A particular solution is never presented as the uniquely identified relation
unless nullity is zero. The exact oracle support must be contained in the set
of variables not certified irrelevant by the training equations.

## Fixed experiment

- Reuse the exact corpus generator and digest from
  `zhouyi-cpg-ei-mixed-operators-v1`.
- Default CI: 8 families, 8 inputs, 8 outputs, seed 20261114.
- The solver receives only each family/output's training rows.
- Full truth-table labels are used only for the separately reported ANF oracle.
- Development and locked labels do not enter the GF(2) system.
- The JSON report records corpus digest, split sizes, basis definition,
  per-output rank/nullity and support identifiability.

## Interpretation boundary

ANF is a complete representational basis, not a compact or automatically
discoverable representation. With d inputs it has 2^d coefficients; sparse
truth functions can still have a large affine ambiguity under limited samples.
This benchmark does not establish open-world induction, cross-family transfer,
causal discovery, Yi-Xue understanding, language reasoning, or superiority to
Transformer architectures.
