# E02-J Level-A implementation status

**Status:** prototype core implemented on an isolated research branch; no benchmark result or locked-test claim.

## Implemented

- Typed-by-construction integer expression AST with variables, constants, and modular add/subtract/multiply.
- Runtime bottom-up AST generation up to a configurable depth.
- Semantic deduplication over a declared input domain, with shortest-expression retention.
- Shortest consistent program selection from observed input/output examples.
- Counterexample-guided iterative synthesis (CEGIS), with one counterexample returned per oracle call and an explicit query budget.
- Non-contiguous role indices, including a representative `(0, 2, 5)` selection.

## Scope boundary

This is a Level-A program-synthesis core over known primitives. It does not discover new primitive operators, does not implement Level B macro invention, and does not establish autonomous open-world relation discovery.

The current code is a development implementation. It has not yet been compared against random-program, MDL, evolutionary, finite-enumeration, or autoregressive controls. It has no locked Test, no preregistered effect-size result, and no claim of generalization beyond the finite ternary DSL.

## Next gates

1. Audit AST type/arity/depth and semantic canonicalization.
2. Verify that the counterexample oracle exposes only one counterexample per query and never reveals hidden labels or generator internals.
3. Add rule-family splits and nuisance-metadata randomization.
4. Add matched-budget baselines before running comparative experiments.
5. Freeze the benchmark protocol and run only after implementation review.
