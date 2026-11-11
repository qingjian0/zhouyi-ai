# XSL-3: Versioned Relation-Role Transform Operators

Date: 2026-11-11  
Status: executable research prototype; transforms are explicit hypotheses, not semantic facts.

## Why this layer exists

XSL-1 correctly treats ordered relation roles as meaningful. XSL-2 enumerates node correspondences without silently permuting relation arguments. XSL-3 adds a separate, auditable operator layer so a role reversal, cyclic permutation or other re-expression can be proposed explicitly without weakening either validator.

## Contract

A `RoleTransform` declares:
- stable transform ID and version;
- source and target relation types;
- a complete argument permutation;
- optional scope conditions and evidence references.

The permutation is an output-position-to-input-position map. It must be a bijection over `0..arity-1`; booleans are rejected even though Python treats bool as an int subtype.

Applying a transform returns the transformed relation and an audit record with `semantic_status=HYPOTHESIS_ONLY`. The transform does not assert that the source and target relations are equivalent, symmetric, inverse, causal counterparts or valid in a Yi-Xiang tradition.

No transform is applied implicitly. The default remains no transform / identity mapping. Any non-identity operator must be named, versioned, scoped and evidence-linked by its caller.

## Composition

For two output-to-input permutations (p) then (q), the composed mapping is (p[q[j]]). Composition is permitted only when both permutations have equal arity. The caller remains responsible for checking relation-type compatibility, scope compatibility and semantic legitimacy across the operator chain.

## Test gates

- identity;
- binary reversal;
- ternary cyclic permutation;
- wrong relation type and arity;
- duplicate and boolean indices;
- deterministic permutation composition.

## Boundaries

- A mathematically valid permutation is not evidence that a relation is symmetric.
- Role reversal is not the same as inverse relation semantics.
- Scope/evidence fields are carried as metadata, not authenticated or evaluated.
- No automatic rule mining or LLM-generated operator authorization.
- No changes to main; this work is a Draft research PR stacked on XSL-2.
