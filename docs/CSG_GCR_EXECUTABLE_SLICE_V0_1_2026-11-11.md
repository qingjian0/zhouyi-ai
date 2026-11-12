# CSG-GCR executable slice v0.1

Date: 2026-11-11  
Branch: `integration/csg-gcr-executable-slice-2026-11-11`  
Status: bounded research prototype; pending CI validation  
Upstream design: PR #164  
Kernel input: SROK-0 immutable composition candidates

## 1. Purpose

This slice turns one narrow part of CSG-GCR into executable code: bounded coordination of immutable local proposals under explicit compatibility, dependency, parent-state, and resource constraints.

It is deliberately not a general cognitive runtime. It is a reference coordinator that can be tested independently before adding learned proposers, dynamic hypergraph mutation, or device-specific optimization.

## 2. Ownership boundaries

- SROK proposes local role-bound structures and reports its own search limits.
- CSG-GCR combines compatible proposals and reports global coordination limits.
- E09 remains the authority for prediction commits, evidence reveal, learner visibility, and evaluation split policy.
- E12-A6 remains the sole authority for candidate lifecycle and structure-version transitions.
- E17 CandidateBundle is a content/provenance/validation contract proposal. Its `CandidateRegistry` lifecycle must not be imported as a second authority.
- ZPCM remains the persistence/projection authority; this prototype performs no persistence.

The coordinator returns immutable `CoordinatedCandidate` values. It does not commit facts, publish structure versions, mutate shared state, or convert scores into probabilities.

## 3. Executable contract

Input `CandidateProposal` contains:
- stable proposal ID;
- parent state version reference;
- branch ID;
- typed-by-caller key/value bindings;
- evidence references;
- prerequisite proposal IDs;
- explicit exclusion proposal IDs;
- finite ranking utility and non-negative integer cost.

`GlobalConstraints` provides required/forbidden bindings, maximum selected proposals, total cost, explored states, and result count.

A proposal set is feasible only when:
1. all proposals share the same parent state version;
2. repeated binding keys agree;
3. explicit exclusions are respected;
4. every prerequisite is included;
5. required bindings are present and forbidden bindings absent;
6. candidate count and total cost remain within limits.

Different branch IDs may be combined when they share a parent state and are otherwise compatible. Branch identity is preserved in the result. Branches are not assumed mutually compatible merely because their parent is shared; proposers must declare exclusions when alternatives are mutually exclusive.

The search is deterministic for the same input and budgets. It is bounded by `max_states`; truncation returns `BUDGET_EXHAUSTED`, never a false complete result. Scores are ranking utilities only, not probabilities, truth values, or evidence strength.

## 4. Current limitations

This first slice does not yet implement:
- canonical semantic deduplication and alias/provenance consolidation;
- typed hyperedge unification beyond caller-provided bindings;
- Pareto-frontier objectives or diversity-aware selection;
- incremental branch deltas and structural merge operators;
- a SAT/SMT, factor-graph, or exact global constraint backend;
- evidence independence assessment or E09 commit/reveal;
- E12-A6 lifecycle integration;
- persistent events, crash recovery, or process isolation;
- learned candidate proposers or calibrated scores.

These are explicit follow-up tasks, not implied capabilities.

## 5. Acceptance tests

The focused suite covers:
- compatible cross-branch combination;
- binding conflict and parent-version isolation;
- explicit exclusions and prerequisites;
- required/forbidden global bindings;
- candidate-count and cost limits;
- explicit search-budget exhaustion;
- input-order determinism;
- invalid references and numeric values;
- empty input.

The full repository test suite must run on the PR head. Passing tests establishes implementation conformance for this bounded prototype only, not scientific superiority or general reasoning capability.

## 6. Next implementation gates

1. Add semantic deduplication without collapsing distinct evidence provenance.
2. Add typed variable unification and hyperedge role constraints.
3. Add branch delta and explicit mutually exclusive worldline semantics.
4. Add Pareto candidate selection and diversity controls under matched budgets.
5. Build an adapter that emits the existing CandidateBundle content contract while delegating lifecycle to E12-A6.
6. Add fault-injection and resource scaling tests before integration maturity is raised.
