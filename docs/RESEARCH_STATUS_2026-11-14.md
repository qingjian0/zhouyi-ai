# Zhouyi-AI research status — 2026-11-14

This status applies to the stacked research branches and open Draft pull requests. None of these changes has been merged to stable main.

| Milestone | Scope | Focused validation | Repository-wide validation | PR |
|---|---|---:|---|---|
| M57 | Non-path / higher-order relational transfer benchmark; binary relations held constant across hard candidates | 9 tests; 900 generated/audited cases | Passed on the M57/M58 stack | https://github.com/qingjian0/zhouyi-ai/pull/488 |
| M58 | Autonomous entity/role mapping with type, path-only, and full-constraint baselines | 5 tests; 90-case comparison | Passed on head c3e851bb4fd65670a4c41a198991aa108fde9e28 | https://github.com/qingjian0/zhouyi-ai/pull/489 |
| M59 | Classical source/witness provenance, exact spans, independent annotations, leakage control | 9 tests | Passed on head eac82ee4d16f31d328abdeb41b2a10f245c61699 | https://github.com/qingjian0/zhouyi-ai/pull/490 |
| M60 | Exact-distribution binary SCM; confounding, mediation, collider, latent confounding, domain renaming | 7 tests | Passed on head 407990b64ec74613a0c3e9915a0b7db87ff9a146 | https://github.com/qingjian0/zhouyi-ai/pull/491 |
| M61 | DAG d-separation, minimum observed back-door set, cycle rejection, correct abstention semantics | 13 tests | Passed on head 55099cccac00323d47b87358d3bb2e33c6be97a0 | https://github.com/qingjian0/zhouyi-ai/pull/492 |
| M62 | Gold-admission gates; pending records excluded from gold counts; scan-verified transcription required | 17 tests passed on code/test head 6032663924243c2ea65ba442fab4d59a1d8c9ead | Run 43590149812 is still running | https://github.com/qingjian0/zhouyi-ai/pull/494 |

## Important scientific boundaries

- M57/M58 demonstrate symbolic performance on controlled synthetic relational graphs. They do not demonstrate learned neural relational reasoning or performance on historical texts.
- M60/M61 cover a limited sufficient back-door criterion for fully specified DAGs. They do not implement general causal identification, front-door, instrumental variables, PAG/CPDAG, or complete do-calculus.
- M62 is a corpus-governance improvement. It does not create an authenticated historical gold corpus.
- The Four Books Congkan Song-facsimile 《周易》 is a promising source candidate, but the CText digital transcription is OCR-derived. It remains discovery-only until its cited spans are verified against scans and adjudicated.
- 《象传》 text and Wang Bi's commentary are separate textual layers. The received 《象传》 text must not be attributed to Wang Bi.

## Next research gates

1. Complete M62 full repository CI and retarget its PR to M61 to restore a clean stacked diff.
2. Build a scan-backed, edition-aware source register, beginning with the Song-witness 《周易》 and a separate Qing Siku collation witness.
3. Add structured identification-strategy scoring beyond back-door adjustment (front-door, IV, and explicit non-identifiability cases).
4. Add finite-sample causal estimation, uncertainty intervals, positivity diagnostics, and sensitivity analysis.
5. Connect the M57/M58 relational tasks to source-grounded annotations only after M59/M62 admission gates pass.
6. Run fair baselines against actual model adapters under fixed data, compute budgets, and held-out source families.

No overall project-completion claim is made. The current work advances infrastructure and controlled diagnostics; the end-to-end yixiang system remains unproven.
