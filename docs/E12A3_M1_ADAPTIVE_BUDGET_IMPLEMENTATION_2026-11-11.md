# E12-A3-M1 — Adaptive Budget Allocator (UCB1 baseline)

Date: 2026-11-11  
Status: implementation and deterministic policy tests added; benchmark execution pending.  
Motivation: E12-A3-M0's 20-seed equal-share result found PORTFOLIO selection coverage (27.5%) below RELATIONAL (42.5%) and BOUNDED_ENUM (35.0%). A fixed equal-share scheduler therefore has no demonstrated advantage.

## 1. Scope

This implementation isolates the allocation policy from proposal generation. One allocation unit is one fixed-size proposal batch. The allocator sees only a normalized Gate-Dev incremental-utility reward after each batch.

It does not receive:
- Gate-Final labels or scores;
- Locked-Test labels or scores;
- evaluator truth, hidden rule IDs, or world seeds;
- proposer source code or candidate-generation internals.

This API separation is an engineering boundary, not a security boundary. A future integrated benchmark must place the evaluator in a separate process and enforce the data contract there.

## 2. Implemented policy

The allocator first guarantees each proposer family an exploration floor. It then selects the family with the highest UCB1 index:

`UCB_i = mean_reward_i + c * sqrt(log(t) / n_i)`

where `n_i` is the number of completed batches for family `i`, `t` is the number of allocated batches, and `c` is frozen in configuration.

Ties are broken by stable lexical family ID. Each allocation reserves one batch and must be followed by exactly one Gate-Dev reward before another allocation can be made.

Rewards are required to be finite and in [0,1]. The integrated experiment must preregister how incremental Gate-Dev utility is normalized to this interval; do not clip arbitrary raw accuracy gains after observing results.

## 3. Controls and accounting

- Deterministic equal-budget allocator is included as a fixed control.
- Every call consumes exactly one budget unit.
- The budget must cover all family exploration floors.
- Each reward event requires a unique evidence ID.
- The append-ordered trace records family, reward, evidence ID, and pull counts.
- `freeze()` creates a final allocation snapshot and irreversibly prevents further updates. Gate-Final selection occurs only after this freeze in the future integrated runner.

## 4. Tests

The focused tests cover budget conservation, exploration-floor satisfaction, allocation movement toward a higher-reward family, deterministic ties, mandatory reward feedback, reward validation, unique evidence IDs, freeze semantics, and configuration validation.

The test replay uses pre-generated reward streams. It is a policy unit test, not an empirical benchmark and not evidence that UCB1 improves held-out discovery.

## 5. Required integrated benchmark

Compare on identical worlds and global budgets:
1. best single proposer selected on training worlds only;
2. equal fixed allocation;
3. round-robin;
4. UCB1 with exploration floor;
5. successive halving/racing;
6. exact small-instance allocation oracle (diagnostic upper bound).

Task families must include unary threshold, pairwise relation, sparse A+C+E composition, nested composition, correlated distractors, noisy observations, held-out relation/operator families, and DSL misspecification.

Use Support for proposals, Gate-Dev for allocation rewards, Gate-Final for one-time frozen candidate selection, and Locked Test for one-time final scoring. Count Gate-Dev queries, proposal slots, predicate evaluations, canonicalization, and wall-clock cost separately. Report coverage and unconditional utility with abstention penalty, not only conditional accuracy.

## 6. Acceptance / falsification

UCB1 is promising only if it improves over equal allocation and the best specialist on held-out world families at matched proposal and evaluation cost, without degrading calibration or increasing false acceptance. If it only learns to favor RELATIONAL on the two existing task families, it is a narrow task-family selector, not a general allocator.

No benchmark result or superiority claim is made in this PR.
