# CPG-EI conditional motif proposals

Status: experimental diagnostic; separate from the greedy default.

## Motivation

The GF(2) parity teacher is exactly representable by the finite feature basis, but greedy residual-correlation growth reached only 63.37% mean bit accuracy and 30.56% mean support recall over three seeds, with 0/3 exact support recovery. The exact-support oracle reached 100%, showing that the observed gap is in discovery rather than representational capacity.

## Proposal

Treat each 3-line motif as one candidate group containing its three pairwise conjunctions and one third-order conjunction. For each of the 20 possible line triples, fit a ridge-regularized least-squares probe on the training split only, both with the seven bias/unary features and with the four motif features added. Rank motifs by the sum of non-negative residual-SSE reductions across the six output heads.

This directly tests conditional, joint feature proposals rather than relying on the marginal correlation of each pair feature in isolation.

## Guardrails

- The method is an ablation/diagnostic, not the production topology learner.
- Only training rows determine proposal scores; validation is reserved for model selection/reporting and locked-test remains untouched.
- Compare against the greedy residual-growth method, pairwise-only proposals, shuffled-label controls, and equal-compute search budgets.
- A six-line motif prior is a bounded inductive bias. It does not establish arbitrary-arity discovery or natural-language transfer.
- Keep the existing greedy method as default until multi-seed, matched-compute comparisons justify a change.
