# CPG-EI conditional motif: state-disjoint locked-test protocol

Status: research-only; follows PR #406 and does not change the default learner.

## Correction to the prior experiment

The previous generator sampled six-bit states with replacement. Since the
entire input domain contains only 64 states, the old 512/256/256 row splits
necessarily repeated input states across train and held-out partitions. Different
random seeds did not make those finite-domain states disjoint. The old scores
therefore measure performance on independently sampled records, not generalization
to unseen input states.

This protocol replaces row-level random sampling with an exact partition of
the complete six-bit state space.

## Protocol

- Enumerate all 64 possible six-bit states once per seed and deterministically
  shuffle their order.
- Partition into 32 training, 16 development, and 16 locked-test states.
- Assert pairwise disjointness and exact coverage of all 64 states.
- Generate candidate motifs and fit candidate configurations on training states.
- Select learning rate and epoch count using development states only.
- Resolve ties in favor of fewer epochs, then lower learning rate.
- Refit the frozen configuration on train + development states.
- Evaluate the locked 16 states only after selection and refitting.
- Emit per-seed overlap counts so the split invariant is independently auditable.

## Interpretation

This is a strict unseen-state test within a finite six-bit truth table. It is
stronger than the previous row-level split but remains a small finite-domain
benchmark. It does not establish arbitrary-arity discovery, open-world
induction, natural-language reasoning, or superiority to Transformer models.

The 100% scores previously observed on the row-level split must not be reused
as unseen-state generalization results.
