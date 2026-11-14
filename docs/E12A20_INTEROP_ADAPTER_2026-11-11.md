# E12-A20 → CPG-EI v1 adapter

Date: 2026-11-11  
Status: first adapter slice; draft integration PR stacked on the CPG-EI v1 contract PR.

## Scope

The adapter branch carries the unchanged A20-0 exact solver, A20-1 BP implementation, their original focused tests, and the deterministic calibration runner from the E12-A20 research line. This keeps the adapter executable without importing the research branch's unrelated history.

`prototype/e12a20_interop_adapter.py` maps the existing E12-A20 exact finite-domain solver and synchronous sum-product BP engine into the shared `prototype.cpg_interop.InferenceResult` contract.

The adapter does not copy either inference engine and does not alter the native E12-A20 APIs.

## Mapping rules

| Native engine outcome | Shared status | Notes |
|---|---|---|
| Exact enumeration, one feasible complete assignment | IDENTIFIED | Only when the full state space was evaluated |
| Exact enumeration, multiple feasible assignments | AMBIGUOUS | Ranked refs are deterministic; energy is not called probability |
| Exact enumeration, no feasible assignment | INCONSISTENT | No hypothesis refs are emitted |
| Exact enumeration stopped by assignment budget | BUDGET_EXHAUSTED | Partial ranked refs may be retained |
| BP inconsistent messages | INCONSISTENT | Preserve the engine's fail-closed state |
| BP budget exhaustion | BUDGET_EXHAUSTED | Preserve the engine's stop reason |
| BP convergence / iteration limit | AMBIGUOUS | BP returns marginals, not a joint MAP result |

## Critical semantic guard

Belief propagation returns variable marginals. Combining each variable's marginal mode into a synthetic complete assignment would fabricate a joint hypothesis: on loopy graphs, marginal modes need not form the global MAP assignment. Therefore the BP adapter intentionally emits no ranked hypothesis references. It preserves evidence references and resource counters and reports AMBIGUOUS unless the native engine reports inconsistency or budget exhaustion.

The exact enumerator can emit deterministic hypothesis references because it evaluates complete assignments. Its energy remains an ordering cost, not a calibrated probability.

## Validation

Focused tests cover:
- unique and multiple exact assignments;
- no feasible assignment;
- exact search budget exhaustion;
- BP marginal-to-joint non-promotion;
- BP inconsistency and budget exhaustion preservation.

The shared contract is supplied by the parent CPG-EI v1 foundation branch. This PR is stacked and should be reviewed/merged only after that parent is available. No changes are made to `main`.


## BP marginal preservation correction

The adapter result now retains the original BP marginal tuple alongside the track-neutral `InferenceResult`. The shared DTO deliberately does not fabricate a joint hypothesis from marginals, but the adapter must not discard the marginal values themselves. Consumers can inspect per-variable distributions while still seeing `AMBIGUOUS` at the joint-hypothesis layer.
