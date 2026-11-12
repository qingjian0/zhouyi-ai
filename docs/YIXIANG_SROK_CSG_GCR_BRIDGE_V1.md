# Yixiang → SROK → Typed CSG-GCR Bridge (v1)

## Purpose

This slice compiles explicit, versioned XSL/Yixiang role permutations and bounded
SROK assignments into typed CSG-GCR proposals. It is a hypothesis-generation
and coordination bridge, not a semantic truth validator.

## Data path

1. A caller supplies an explicit source relation, a versioned role transform,
   and a typed SROK workspace.
2. `yixiang_srok_adapter` compiles the role permutation into typed sparse
   composition slots and emits bounded candidate assignments.
3. `yixiang_csg_gcr_adapter` maps each assignment to:
   - one immutable `CandidateProposal`;
   - one `HyperedgeProposal`;
   - declared `VariableSpec` values and typed `RoleBinding` values.
4. `TypedCandidateCoordinator` validates typed compatibility, variable
   constraints, evidence-reference equality, and the coordinator's hard
   selection/cost/state budgets.

## Non-negotiable semantics

- Every typed proposal and coordinated candidate carries an explicit
  `semantic_status=HYPOTHESIS_ONLY`; the status survives coordination and is
  independent of the display-oriented candidate-kind label.
- Alternative assignments from the same SROK search are pairwise mutually
  exclusive. They are ranked as separate hypotheses and cannot be combined
  into a joint fact.
- SROK node evidence IDs flow to the proposal and hyperedge evidence refs.
- XSL transform-prior refs are retained separately as derivation metadata;
  they are not observational evidence and do not increase evidence strength.
- Candidate scores are ranking utilities only, never probabilities or truth.
- A bounded search may truncate recall. Budget exhaustion must remain visible.
- The E12-A6 read-only projection adapter rejects typed `HYPOTHESIS_ONLY`
  status and also rejects the reserved candidate-kind marker. Relabeling a
  candidate cannot erase its typed epistemic status. Regression tests enforce
  this boundary.
- This bridge does not infer relations from raw natural language, ground
  observations, establish semantic equivalence, or prove causality.

## Explicitly not connected yet

- Observation parsing and evidence grounding.
- Trusted world-family/domain provenance and scope authorization.
- E09 evidence acceptance/authorization.
- E12-A6 lifecycle transitions.
- ZPCM persistence and restart/replay.
- Native non-Transformer language expression.

Therefore this bridge is not an end-to-end cognitive lifecycle and must not be
used as a training-ready truth pipeline.

## Acceptance tests

The unit tests verify typed role preservation, exact evidence provenance,
mutual exclusion of alternatives, bounded CSG-GCR coordination, and invalid
context rejection. Full repository CI remains the gate for integration.
