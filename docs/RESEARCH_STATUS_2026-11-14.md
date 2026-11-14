# Zhouyi-AI research status — 2026-11-14

This status applies to the stacked research branches and open Draft pull requests. None of M57–M67 has been merged to stable main.

| Milestone | Scope | Focused validation | Repository-wide validation | PR |
|---|---|---:|---|---|
| M57 | Non-path / higher-order relational transfer benchmark; binary relations held constant across hard candidates | 9 tests; 900 generated/audited cases | Passed on the M57/M58 stack | https://github.com/qingjian0/zhouyi-ai/pull/488 |
| M58 | Autonomous entity/role mapping with type, path-only, and full-constraint baselines | 5 tests; 90-case comparison | Passed on head c3e851bb4fd65670a4c41a198991aa108fde9e28 | https://github.com/qingjian0/zhouyi-ai/pull/489 |
| M59 | Classical source/witness provenance, exact spans, independent annotations, leakage control | 9 tests | Passed on head eac82ee4d16f31d328abdeb41b2a10f245c61699 | https://github.com/qingjian0/zhouyi-ai/pull/490 |
| M60 | Exact-distribution binary SCM; confounding, mediation, collider, latent confounding, domain renaming | 7 tests | Passed on head 407990b64ec74613a0c3e9915a0b7db87ff9a146 | https://github.com/qingjian0/zhouyi-ai/pull/491 |
| M61 | DAG d-separation, minimum observed back-door set, cycle rejection, correct abstention semantics | 13 tests | Passed on head 55099cccac00323d47b87358d3bb2e33c6be97a0 | https://github.com/qingjian0/zhouyi-ai/pull/492 |
| M62 | Gold-admission gates; pending records excluded from gold counts; scan-verified transcription required | 17 tests passed on code/test head 6032663924243c2ea65ba442fab4d59a1d8c9ead | Passed: run #43590149812 on the combined M61/M62 stack | https://github.com/qingjian0/zhouyi-ai/pull/494 |
| M63 | Single-observed-mediator front-door criterion and exact binary front-door functional; back-door comparator retained | 5 focused regressions | Passed: focused workflow #43592406857 | https://github.com/qingjian0/zhouyi-ai/pull/495 |
| M64 | Graphical IV screening, exact-population binary Wald ratio, explicit LATE vs ATE semantics | 7 focused tests; run #43593904145 | Passed: full unit suite and all E01/E02 stages in #43593904033 | https://github.com/qingjian0/zhouyi-ai/pull/496 |
| M65 | Bounded-exclusion IV sensitivity interval under linear covariance moments; exogeneity/relevance retained | 4 focused tests; 11 combined M64/M65 tests passed in #43594100977 | **Passed**: full repository run #43594100995; unit tests and every E01/E02 stage succeeded | https://github.com/qingjian0/zhouyi-ai/pull/497 |
| M66 | Multiple graph-screened instruments; per-instrument bounded reduced-form violations; interval intersection and abstention | 6 M66 tests; 17 combined M64–M66 tests passed in #43594859484 | **Passed**: full repository run #43594859442; unit tests and every E01/E02 stage succeeded | https://github.com/qingjian0/zhouyi-ai/pull/498 |
| M67 | Scan-backed source audit of the Four Books Congkan 《周易》, including page 9/10 DJVU locators and commentary-layer separation | Documentation/source audit; no code tests required | Documentation-only; no empirical/model validation claimed | https://github.com/qingjian0/zhouyi-ai/pull/499 |
| M68 | Classical Anderson–Rubin F test and analytic weak-IV-robust confidence-set inversion under iid Gaussian homoskedastic assumptions | 7 focused tests added; pending | Pending | https://github.com/qingjian0/zhouyi-ai/pull/500 |

## Important scientific boundaries

- M57/M58 demonstrate symbolic performance on controlled synthetic relational graphs. They do not demonstrate learned neural relational reasoning or performance on historical texts.
- M60/M61 cover a limited sufficient back-door criterion for fully specified DAGs. M63 adds one binary, single-observed-mediator front-door route. M64–M66 add narrow graph-screened IV diagnostics and linear-moment sensitivity sets; none implements general causal identification or complete do-calculus.
- M62 is a corpus-governance improvement. It does not create an authenticated historical gold corpus.
- M67 advances the Four Books Congkan 《周易》 from catalogue-only discovery to accessible page-image discovery. The scan is a digital reproduction of the facsimile, not the original Song woodblocks; spot-checking is not complete transcription verification or independent adjudication. No Gold source has been admitted.
- 《象传》 text and Wang Bi's commentary are separate textual layers. The received 《象传》 text must not be attributed to Wang Bi; the page 9 phrase “夫易者象也” belongs to the Wang Bi commentary layer in this witness and is distinct from the received 《系辞下》 phrase “是故易者象也，象也者像也”.

## Next research gates

1. Review and merge the stacked Draft PRs in dependency order only when explicitly authorized.
2. Complete page-by-page scan collation and two independent annotations for the selected 《周易》 witness before any Gold admission.
3. Add finite-sample uncertainty, weak-instrument-robust inference, positivity diagnostics, and covariate-adjusted designs to the causal diagnostics.
4. Connect M57/M58 relational tasks to source-grounded annotations only after M59/M62 admission gates pass.
5. Run fair baselines against actual model adapters under fixed data, compute budgets, and held-out source families.

No overall project-completion claim is made. Current work advances infrastructure and controlled diagnostics; the end-to-end yixiang system remains unproven.
