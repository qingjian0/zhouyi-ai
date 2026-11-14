# M58 — Autonomous entity alignment and relational mapping

Status: first executable symbolic baseline; exact-head CI required.  
Base: M57 hard non-path controls.  
Question: can a solver discover role-to-entity correspondences from the pattern and target graph, without being handed candidate mappings?

## Implemented slice

- A deterministic backtracking solver constructs role-to-node assignments from node types and graph constraints.
- Three controls: type-only, binary/path-only, and full constraints.
- Full mode enforces binary relations, ordered hyperedges, forbidden relations, injectivity/all-different, and graph-wide counts through the M57 constraint evaluator.
- Minimum-remaining-values ordering and an explicit state budget prevent unbounded search.
- A same-case runner evaluates type-only, binary/path-only, and full-constraint solvers with exact accuracy, coverage, selective accuracy, and per-difficulty breakdowns.
- Ambiguous, unsatisfiable, and budget-exhausted outcomes are explicit; the solver does not silently guess.
- The public candidate list is not read by the solver. Evaluator labels remain outside the model-facing input.

## Interpretation

This is a symbolic exact-search baseline, not a learned representation, language understanding, or evidence that a human/LLM can independently extract the graph from a classical text. M57's synthetic generator contains two nodes per role and limited generator families. Success here demonstrates executable entity alignment under a known schema only.

## Literature motivation

- Das & Balke (INLG 2025), [From Prototypical to Relational](https://aclanthology.org/2025.inlg-main.28/): reports that strong embedding/prototypicality scores do not guarantee fine-grained relational mapping. This motivates separating type-only, path-only, and full-constraint controls.
- Minegishi et al. (2026), [Emergent Analogical Reasoning in Transformers](https://arxiv.org/abs/2602.01992): formalizes analogy as cross-category correspondence and analyzes relational-structure alignment separately from applying the mapping. This supports evaluating mapping discovery and relation application as distinct stages.

## Required next comparisons

1. Compare all three modes on identical M57 cases and publish coverage plus selective accuracy, not accuracy alone.
2. Add a typed-degree heuristic baseline and a learned graph matcher only when a reproducible implementation is available.
3. Add generator-family holdouts and adversarial graph mutations.
4. Add independently annotated classical-text graphs with source/edition provenance and adjudication before claiming domain transfer.
5. Keep evaluator artifacts inaccessible during prediction; report paired family-cluster bootstrap intervals.

## Literature motivation

Relational analogy research distinguishes surface/prototypical similarity from fine-grained relational mapping. Mechanistic work on Transformers further separates encoding relational structure from successfully applying a mapping. M58 therefore separates candidate generation from M57's candidate-selection evaluation rather than conflating them.
