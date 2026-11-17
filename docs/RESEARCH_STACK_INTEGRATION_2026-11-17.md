# M23–M70 research integration candidate — 2026-11-17

## Integration target

This branch is based directly on stable `main` at `a20a72bb844306f55d3498f862e9e968bf78db1b`. It imports non-conflicting files from the M57–M70 stacked research tree at `13210b8e505df9366959869f7a108ae0821db3bf`, while preserving files that exist only on `main` and preserving the `main` versions of paths that exist on both sides but differ.

## Merge strategy

- Add research-only files without replacing any existing `main` file.
- Preserve main-only orchestrator, E02E–E02I, E03A, E12A3, schemas, and their tests.
- Preserve main versions of `README.md`, `ROADMAP.md`, `.github/workflows/tests.yml`, `prototype/yixiang_encoding.py`, and `tests/test_yixiang_encoding.py`.
- Do not rewrite stable `main` directly. Submit this integration candidate as a draft PR and require exact-head CI before review or merge.

## Validation

The source research head has completed its M61 focused workflow and repository-wide workflow successfully. Those results do not validate this new combined tree. Exact-head validation for this integration candidate is pending.

## Evidence and interpretation boundaries

- M60/M61 cover declared causal-graph identification conditions; they are not general causal discovery or unrestricted do-calculus.
- M64–M69 diagnostics retain their stated assumptions and sensitivity limits.
- M67 records two-page visual spot-check progress, not complete manuscript transcription or adjudicated variants.
- M70 is a witness map and collation protocol; it does not claim that manuscript variants have been fully collated or admitted as Gold.
- Synthetic benchmark results do not establish general intelligence, broad superiority over Transformers, or historical truth of classical analogies.
