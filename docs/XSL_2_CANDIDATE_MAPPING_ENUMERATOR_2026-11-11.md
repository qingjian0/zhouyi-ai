# XSL-2: Bounded Exact Candidate Mapping Enumerator

Date: 2026-11-11  
Status: executable research prototype; deterministic bounded search, not a learned analogy engine.

## Purpose

XSL-1 validates one explicit bridge. XSL-2 enumerates competing injective partial node mappings under caller-supplied node-type and relation-type correspondences, then validates each candidate with the XSL-1 contract.

Implementation:
- prototype/yixiang_mapping.py
- tests/test_yixiang_mapping.py

## Search contract

Inputs are source and target typed relational graphs; explicit one-to-one node-type and relation-type mappings; mapping kind and optional scope/evidence metadata; a minimum number of testable source relations; and maximum recursive search states and returned candidates.

For every source node, search considers each compatible target node and an explicit unmapped choice. Target nodes cannot be reused. Candidate mappings are partial and injective. Relation argument order remains semantic and is checked by XSL-1.

Traversal is deterministic. The state budget counts recursive states. If reached, search_complete is false; an incomplete search must never be interpreted as proof that no better mapping exists.

## Candidate ordering (not confidence)

Candidates are ordered lexicographically by:
1. preserved source relation count, descending;
2. testable/mapped source relation count, descending;
3. violated source relation count, ascending;
4. canonical node mapping as deterministic tie-breaker.

This is retrieval order only, not a probability or truth score. Consumers inspect status, coverage, preservation rate, unmapped relations, violations and search completeness separately. A candidate with more preserved relations may also contain contradictions.

## Limits

- Type and relation correspondences are supplied explicitly; XSL-2 does not invent semantic equivalence.
- Search is exponential in the worst case. State and result budgets are mandatory.
- A truncated search returns only candidates found before the budget; no optimality claim is made.
- Scope conditions and evidence references remain metadata; they are not authenticated or enforced here.
- Structural preservation is not causal equivalence, predictive validity or historical correctness.
- No embedding similarity or language-model score is mixed into this exact enumerator.

## Tests

Tests cover two competing valid mappings, deterministic output, explicit budget exhaustion, strict integer budget validation and injective type-map validation.

## Next research gates

1. Add role-symmetry operators as versioned policies, never implicit argument permutations.
2. Add candidate diversity and Pareto-front reporting so one structural family cannot crowd out alternatives.
3. Add scope predicates and evidence-split checks through existing E09 ownership.
4. Compare XSL-2 with generic SME/graph-matching baselines under equal compute budgets.
5. Add domain tasks from Yi-Xiang material only after each tradition/viewpoint has a source, scope and counterexample record.
