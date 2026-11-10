# E12-A2-M Exact Oracle Validation Gate

Date: 2026-11-11  
Status: test design and implementation added; execution/CI status must be read from the branch's workflow runs.

## Why this gate exists

The existing selector computes expected information gain as prior entropy minus expected posterior entropy. That identity is correct, but tests that exercise the same formulaic path are not an independent correctness oracle.

This addition defines mutual information directly from the joint distribution:

`I(H;O)=sum_{h,o} p(h,o) log2(p(h,o)/(p(h)p(o)))`

The oracle is deliberately implemented in the test module and does not call the production entropy or posterior helpers.

## Coverage added

1. Exhaustively checks all 125 three-hypothesis binary likelihood combinations on the grid {0, .25, .5, .75, 1}, using a non-uniform prior.
2. Checks that the selector's cost-normalized action choice agrees with an independently computed exact action score.
3. Checks candidate/action mapping-order invariance.
4. Checks that observationally equivalent hypotheses yield exactly zero information and an explicit abstention.

## Interpretation limits

Passing these tests would validate the finite probability calculations and these invariants only. It would not establish calibration of supplied likelihoods, sequential policy optimality, robustness under model misspecification, or any Yijing-specific advantage.

## Required next tests

- Multi-step adaptive episodes against a dynamic-programming exact policy on tiny worlds.
- Random, fixed-order, maximum-disagreement, raw-IG, and cost-normalized-IG baselines under identical budgets.
- Evaluator/learner process separation and truth-mutation tests.
- Held-out world-family and multi-seed evaluation.

Do not start the A3 prior experiment until the generic A2-M test and benchmark gates pass on the exact commit.
