# CPG-EI Conditional Context Coverage Sweep v1

## Question

How does sampling coverage affect observed-pair support recovery for a conditional relation, and can an adversarially incomplete context sample defeat the proposer even when it contains many rows?

## Controlled teacher

Four binary inputs with target:

`y = x0 XOR x1` when `x3 == 1`, otherwise `y = 0`.

The planted support is `{x0, x1, x3}`; `x2` is irrelevant. The benchmark compares the existing pairwise observed-influence proposer with the known support, while separately recording per-variable counterfactual context coverage.

## Protocol

- Randomly permute the complete 16-state input space for fixed seeds.
- Sample fractions 12.5%, 25%, 50%, 75%, and 100%.
- Report support precision, support recall, mean context coverage, and unresolved-variable count.
- Include an adversarial control containing all eight states at the inactive context `x3 == 0`.
- Keep the truth support out of the proposer; use it only for post-hoc metrics.

## Acceptance interpretation

The full truth table should recover all three support variables. The inactive-context adversary should demonstrate a hard identifiability boundary: it contains complete operand variation but never activates the conditional relation, so zero observed influence cannot establish irrelevance. The audit must label this as inconclusive / unobserved counterpart rather than silently treating all variables as absent.

The sweep is deterministic and intentionally small enough for CI. It is a mechanism diagnostic, not a statistical claim about all conditional functions.

## Claim boundary

Synthetic Boolean sampling only. This does not establish a learned relation-discovery model, causal inference, natural-language reasoning, Yi-Xue understanding, or real-world transfer.
