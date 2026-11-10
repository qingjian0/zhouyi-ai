# E10-B1: Pending Evidence Routing and Structural Stability

## Motivation

The first E10-B prototype records observations that cannot traverse the current partition as `unassigned`, but does not revisit them. This creates an evidence-retention defect: if a later merge removes the split key that blocked routing, the old observation remains permanently outside the active concept partition.

This follow-up makes pending evidence explicit and retries routing after structural edits. It does not guess a branch. An observation remains pending while the current tree cannot route its feature map; after a merge makes the route valid, it is inserted into the resulting leaf and every ancestor aggregate.

## State contract

- Every accepted observation remains in the evidence store.
- An observation is either assigned to exactly one active leaf or present in the pending set.
- Pending observations are not silently discarded and are exposed in snapshots.
- Re-routing is deterministic (sorted observation IDs).
- Re-routing occurs after the current evidence step's merge/split pass, avoiding mutation of the node iteration currently in progress.
- A re-route event records count and remaining pending count.
- A missing feature or unseen split value still causes abstention at prediction time.

## Regression scenario

1. Learn a color split from red-positive and blue-negative examples.
2. Add an observation with no color feature; it must remain pending.
3. Reveal counterevidence that makes sibling target rates converge and causes merge.
4. Verify the formerly pending observation is assigned to the merged root and pending count returns to zero.

This tests evidence preservation across a structural transition, not the semantic correctness of the merge threshold.

## Remaining structural risks

This patch does **not** solve split/merge oscillation, statistical calibration, or search-budget accounting. The current implementation can evaluate the same empirical split after a merge and may split again on later evidence. Fixed Gini and target-rate thresholds are not confidence bounds. The next revision should introduce:

- a split/merge hysteresis gap (merge tolerance strictly below the split evidence needed to recreate a boundary);
- a minimum evidence/cooldown interval before reversing a boundary;
- an explicit proposal-evaluation budget, with fail-closed behavior and no partial structural commit;
- event-level structural churn accounting (split count, merge count, reversals, and boundary lifetime).

Do not treat a minimum child count as statistical significance.

## Required controlled evaluation

Replay identical prequential evidence streams and compute budgets across:

1. no structural revision;
2. split-only;
3. merge-only;
4. split + merge;
5. random-boundary proposal control with matched proposal count and cost.

Use multiple seeds and hold out entity identities and feature-value combinations. Record prequential accuracy, coverage, selective accuracy, false split/merge rate, concept count, cumulative complexity, split/merge churn, proposal evaluations, and wall-clock cost. Report every seed and confidence intervals; do not select seeds after observing results.

## Interpretation boundary

Pending evidence routing establishes only a state-management invariant in a bounded categorical, supervised partitioner. It does not establish autonomous semantic concept formation, open-world feature invention, or a Zhouyi-specific advantage. Zhouyi-inspired proposal priors remain a later ablation and must be compared with random proposals under matched compute.
