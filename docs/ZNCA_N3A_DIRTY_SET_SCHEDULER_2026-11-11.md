# ZNCA N3-A: bounded dirty-set scheduler

Date: 2026-11-11  
Status: executable scheduling primitive; not integrated with N1/N2 runtime

## Contract

Input:
- event-touched IDs;
- an explicit forward dependency index (changed item -> dependent items);
- maximum traversal hops;
- maximum returned nodes.

Output:
- deterministic ordered affected IDs;
- explicit unprocessed frontier when node budget is exhausted;
- scanned edge count;
- maximum reached depth;
- COMPLETE or BUDGET_EXHAUSTED.

The touched roots count toward max_nodes. A COMPLETE result means the supplied index was traversed within the requested hop and node budgets; it does not prove the index is globally complete. BUDGET_EXHAUSTED is never converted to NOT_FOUND or COMPLETE.

## Complexity

For the traversed subgraph, work is approximately O(V_r + E_r) plus neighbor sorting costs, where V_r/E_r are visited nodes/edges within the configured bounds. This does not imply constant-time updates. High-degree nodes, large hop limits, index construction, persistence and synchronization can dominate.

## Deliberate exclusions

- No persistence layer or event-log ownership.
- No automatic dependency inference.
- No state mutation or candidate commit.
- No concurrency, cancellation, crash recovery, or incremental index maintenance yet.
- No mobile RSS, latency, energy or thermal measurements.
- No claim that this outperforms a Transformer or graph database.

## Tests

The unit tests cover deterministic traversal, multi-hop expansion, hop limits, node-budget frontier reporting, duplicate roots, cycles, empty input and invalid budgets/edges.

Next integration gate: connect event IDs from the N1 event ledger to this scheduler's dependency index, then test index freshness, version races, partial resumption and crash recovery.
