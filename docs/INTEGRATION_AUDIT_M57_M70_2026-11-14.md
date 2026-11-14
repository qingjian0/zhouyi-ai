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


## Shared-path audit

The per-PR file lists show these intentional or potentially conflicting shared paths:

- M59 (#490) and M62 (#494): `prototype/yixiang_m59_classical_evidence.py` and its tests are modified by the later Gold-admission gate. This is a sequential extension and must be reviewed as one cumulative implementation.
- M60 (#491) and M61 (#492): the M60 causal document, implementation, and tests are extended by M61. The workflow files `m61-general-adjustment.yml` and `m62-gold-admission.yml` occur in both PR diffs. The two M62 workflow versions target different base branches (M60 versus M61), so the current M61 PR has a real workflow-path collision in addition to its stale base.
- M61 (#492) and M63 (#495): M63 extends the shared M60 causal implementation and tests with front-door logic. Review the cumulative module rather than treating M63 as an independent file addition.
- M62 (#494), M63 (#495), M64–M66 (#496–#498), M67 (#499), M68 (#500), and M70 (#503): README/research-status and Gold-admission documentation are touched by successive PRs. These are cumulative documentation updates; check that no later branch drops earlier status or limitations.
- M67 (#499) and M68 (#500) both touch `m68-anderson-rubin-weak-iv.yml`; M68 (#500) and M69 (#501) both touch `m69-heteroskedastic-ar.yml`. These are pre-staged/stacked workflow definitions and should be checked for correct target-branch filters, not blindly duplicated.

The file overlap itself does not prove a code defect. The key distinction is whether the later PR is based on the exact preceding head and whether its changed file intentionally extends the prior version. PR #492 currently fails that condition: its base is two commits ahead of its merge base, and GitHub reports the PR as dirty.


## M61 conflict root-cause check

A direct comparison of the two workflow files on the M60 and M61 branch tips confirms:

- `.github/workflows/m61-general-adjustment.yml` is byte-identical on both branches.
- `.github/workflows/m62-gold-admission.yml` differs only in its `pull_request.branches` filter: the M60 tip targets the M60 branch, while the M61 tip targets the M61 branch.
- The two commits that advanced M60 after the M61 fork are CI workflow setup commits, not additional runtime changes.

This isolates the observed merge conflict to the M62 workflow path rather than the M61 causal implementation. The correct semantic resolution is to preserve the M62 validation workflow while deciding whether it should listen to both stacked target branches or be owned only by the M61 stage. Do not resolve by dropping either workflow purpose. No branch rewrite has been performed.
