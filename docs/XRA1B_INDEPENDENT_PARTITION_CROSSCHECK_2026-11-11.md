# XRA-1b: Independent Exact-Partition Cross-Validation

Date: 2026-11-11
Status: implementation added; execution status must be reported separately
Branch: research/triadic-representation-arbitration-2026-11-11

## Purpose

XRA-1a computes the coarsest deterministic predictive-equivalence partition
using iterative signature refinement. XRA-1b adds an independent evaluator
implementation based on greatest-relation elimination. It is a cross-check,
not a second learner and not a replacement for the primary oracle.

## Independent algorithm

1. Initialize a relation containing every ordered state pair.
2. Remove a pair if any action produces different immediate outcomes.
3. Also remove a pair if that action's successor pair has already been removed.
4. Repeat until no pair is removed.
5. Materialize equivalence classes in input-state order.

The implementation is in `prototype/xra_partition_crosscheck.py`.
The cross-check tests are in `tests/test_xra_partition_crosscheck.py`.

## Validation design

- Exhaustively enumerate all 2-state, 1-action deterministic worlds with
  binary outcomes and transitions to either state.
- Exhaustively enumerate all 3-state, 1-action deterministic worlds with
  binary outcomes and transitions to any of the three states (216 worlds).
- Compare both partition blocks and every ordered pair's equivalence status.
- Run 500 seeded 4-state / 2-action worlds with three outcome values.
- Check malformed and incomplete table rejection.
- Verify immediate, delayed, shortest, and absent distinguishing witnesses.

The two implementations share the mathematical definition of predictive
bisimulation, but use different computational procedures. Agreement is a
stronger implementation check than duplicated examples; it is not a proof
against a shared specification error.

## Leakage and scientific boundary

Both implementations are evaluator-only. The relation, partition blocks,
latent state identifiers, and generator tables must not be included in
learner-visible observations or task manifests. A learner may receive only
the declared observations and action outcomes available at that point in an
episode.

Passing these tests establishes agreement on the enumerated/generated tiny
worlds only. It does not establish stochastic equivalence, partial-observation
identifiability, adaptive MERGE/SPLIT quality, or generalization to changing
worlds.

## Next gate

After execution in a CI-enabled environment, validate shortest distinguishing
action-sequence witness traces against independently simulated outcomes. The
learner-visible evidence contract and deterministic XRA-1c decision helper now exist; task-manifest validation and E12-A8 integration remain open. Do not train the representation selector before those boundaries are frozen.
