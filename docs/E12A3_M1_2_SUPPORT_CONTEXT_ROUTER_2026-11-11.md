# E12-A3-M1.2 Support-Context Task Router

Date: 2026-11-11  
Status: initial router implemented and 20-seed × 3-task benchmark completed; aggregate result did not beat equal allocation; grammar-stratified probe correction is next  
Motivation: M1 and M1.1 show that context-free UCB1 reward variants do not beat equal allocation, while the best proposer changes across task families.

## 1. Research question

Can a proposer coordinator infer the current task structure from a held-out portion of Support and route proposal budget toward the relevant specialist, without inspecting Gate-Dev, Gate-Final, or Locked Test?

This is a task-conditioned routing hypothesis, not a claim that the system has learned a general cognitive architecture.

## 2. Split design

Keep the outer four-way split:
- Support: 64 observations
- Gate-Dev: 32 observations
- Gate-Final: 32 observations
- Locked Test: 32 observations

Internally divide Support into:
- Proposal-Support: 48 observations, passed to proposer generators.
- Context-Support: 16 observations, used only to compute task descriptors.

Use deterministic stratification by label so both subsets retain both classes where possible. The proposer generator must not receive Context-Support rows or labels.

Gate-Dev, Gate-Final, and Locked Test retain their existing roles.

## 3. Context descriptor

For each proposer family f:
1. Generate its candidate pool from Proposal-Support only.
2. Evaluate each candidate on Context-Support.
3. Reserve the first four proposals from each family as the shared exploration/context-probe batch (12 proposal slots total). Compute the family descriptor as the mean of the top three accuracies among those four proposals. All compared methods pay this same 12-evaluation context-probe cost; only the context router uses the descriptor.
4. Record candidate count, unique candidate count, and score dispersion as diagnostics.

The initial router uses only this Support-derived descriptor. It does not receive Gate-Dev labels. The first four context-probe proposals per family are also the mandatory exploration batch, so context measurement is included in—not added on top of—the global proposal budget.

This is a supervised task descriptor computed from training evidence. It may overfit the 16-row Context-Support subset, so it must be tested on independent world seeds and an additional held-out task family.

## 4. Router policy

- Give every family one exploration batch (four slots).
- Allocate remaining batches to the family with the highest Context-Support top-three mean.
- Use deterministic family-ID tie-breaking. With a 31-slot budget, the first 12 slots are the shared probes; the remaining 19 slots follow the highest-scoring family.
- Respect the exact global proposal-slot budget.
- Deduplicate candidate expressions in the final registry while retaining all proposer provenance.
- Count duplicate emissions as proposal slots; evaluate each unique expression once on Gate-Final.

Controls:
- equal allocation;
- round-robin;
- global UCB1 mean-reward allocator;
- single specialists;
- bounded enumeration.

## 5. Task matrix

Retain Threshold and Pairwise Difference, and add PARITY as a previously untested rule family:
`label = int(x % 2 == 0)`.

PARITY is expressible by the existing STAT grammar but was not present in M1/M1.1. It tests whether the router can identify a specialist from Support context rather than memorize only the two previous task types.

## 6. Leakage invariants

- Proposal-Support mutation may change candidate pools.
- Context-Support label mutation may change routing, but must not change proposal generation.
- Gate-Dev mutation must not change the pure Support-context router allocation.
- Gate-Final mutation must not change allocation or proposal pools.
- Locked-Test mutation must not change any proposal, allocation, or Gate-Final selection.
- Locked Test is scored only after selection is frozen.

These are API-level invariants; process isolation remains a separate future requirement.

## 7. Acceptance criteria

The context router is promising only if:
1. It improves over equal allocation on the new PARITY task and does not collapse on the prior tasks.
2. It improves an unconditional Locked-Test metric under the same proposal-slot budget.
3. Its advantage survives paired seed-clustered uncertainty estimates.
4. It is robust to context sample size and label noise.
5. It beats a simple oracle-free task router, not merely global UCB1.

## 8. Known limitations

- A 16-row context subset may produce noisy descriptors.
- Top-three selection can be optimistic when candidate pools are large.
- Proposal-slot matching does not match CPU or wall-clock cost.
- A single static context router is not a contextual bandit with learned uncertainty.
- No Yijing-inspired prior is used in this experiment.

## 9. Initial result and diagnosis

The initial random four-candidate context probe completed 60 episodes. The Support-context router reached 77.19% mean Locked-Test accuracy versus 77.60% for EQUAL. Its task-specific performance was uneven: it improved on Threshold and PARITY but lost on Pairwise Difference.

The Support-context descriptor failed to identify STAT as the PARITY specialist. The likely cause is that a random four-proposal probe missed the rare PARITY operator and its top-three mean diluted the signal.

Full results: `E12A3_M1_2_CONTEXT_ROUTER_RESULTS_2026-11-11.md`.

## 10. Next stage

If the Support-context router is promising, compare:
- top-three mean routing;
- context mean plus Gate-Dev UCB update;
- contextual Thompson-style allocation;
- fixed equal and round-robin;
- capacity-matched generic and permuted context descriptors.

Only after this generic task-conditioned baseline is validated should Yijing-derived structure be introduced as a separately ablated prior.
