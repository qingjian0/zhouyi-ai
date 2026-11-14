# M57–M70 integration audit

Date: 2026-11-14

## Purpose

This branch is an isolated integration-review checkpoint for the existing M57–M70 research stack. It does not merge anything into `main`, close research PRs, or declare the stack production-ready.

## Repository refs observed

- `main`: `1e0fa3341607df7e6c11918ec54e254d7e3696cd`
- M56 base branch `research/yixiang-m56-executable-core-2026-11-14`: `6e9d1503465abacec212fff9c85bd4e1705a6293`
- M70 head: `8c27c0258eb870f7461faffc17187e99a9e465f2`
- Review branch: `integration/m57-m70-review-2026-11-14`, created from the exact M70 head above.

## Pull request state

The following PRs were observed open, Draft, and unmerged:

- M57–M61: #488–#492
- M62–M69: #494–#501
- M70: #503

PR #493 and #502 are not part of the active chain; they were superseded/closed. PR #492 currently reports `mergeable=false`.

## Dependency and divergence findings

1. The active research chain is stacked: M57 starts from the M56 branch, and later stages build on preceding research branches. M70 is based on M69.
2. Comparing M69 to M70 reports three commits ahead and two changed files: README plus the M70 witness-collation plan. This is consistent with M70 being a documentation-focused final layer.
3. Comparing M60 to M61 reports a diverged history: M61 is 15 commits ahead and 2 behind its current M60 base, with merge base `407990b64ec74613a0c3e9915a0b7db87ff9a146`. This explains why PR #492 needs explicit reconciliation before it can be treated as a clean stack transition. Do not force-merge it.
4. Comparing M56 to `main` reports a diverged history (M56 1,145 commits ahead and 2 behind; merge base `b8b43926e666d83a9ce09d2e71eb9294b2d86c97`). Therefore, do not retarget the M57–M70 stack directly to `main` or assume it is a small isolated patch. First determine which pre-M57 commits are intentional research work and reconcile the two commits on `main` that are absent from the M56 line.
5. The exact M70 head has a successful full repository workflow run: `43596163260`. Its unit-test and E01/E02 steps all completed successfully. This validates that head in that workflow; it does not resolve the branch-history divergence or prove real-world yixiang generalization.

## Integration policy

- Keep `main` unchanged.
- Keep all research PRs Draft and unmerged during this review.
- Do not force-push, force-merge, or discard either side of a divergent history.
- Reconcile the M60/M61 boundary first, then inspect the M56-to-main history boundary.
- Compare changed paths and semantics across the stack, especially shared files modified by multiple milestones.
- Run focused tests after any conflict resolution, then the full repository workflow on the exact resulting commit.
- Preserve limitations: synthetic causal benchmarks are not evidence of causal relations in classical texts; no scan-authenticated Gold record is currently established by M70.

## Current status

Integration review has started. No source-code merge or production promotion has been performed. The next safe action is a file-level and commit-level audit of the M60/M61 divergence before any branch reconciliation.
