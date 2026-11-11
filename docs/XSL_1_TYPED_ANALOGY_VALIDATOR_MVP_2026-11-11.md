# XSL-1: Typed Analogy Bridge Validator MVP

Date: 2026-11-11  
Status: deterministic reference implementation; research prototype, not a learned analogy engine.

## Purpose

Turn the typed-analogy proposal into a small executable contract. The MVP validates an explicitly supplied partial mapping between two relational graphs. It does not discover mappings, infer causal equivalence, authenticate evidence, or establish universal truth for any symbolic tradition.

Implementation:
- `prototype/yixiang_analogy.py`
- `tests/test_yixiang_analogy.py`

## Data model

- `Node(node_id, node_type)`: graph-local object with an explicit type.
- `Relation(relation_type, arguments)`: ordered argument tuple. Argument order is semantic; the validator never silently swaps roles.
- `RelationalGraph`: canonical node/relation tuples with unique IDs and referential-integrity checks.
- `AnalogyBridge`: typed mapping of nodes, node types, and relation types, plus scope, predictions, counterexamples and evidence references.
- `BridgeValidation`: preserved, violated, unmapped and unmatched relations, coverage, preservation rate, status and deterministic digest.

The mapping is partial and injective in this first version. Many-to-one mappings, role permutations and graph morphisms with explicit symmetry groups are deferred until a task requires them; silently allowing them would hide role ambiguity.

## Validation semantics

For each source relation:
1. If its relation type or any argument lacks a mapping, classify it as `unmapped`.
2. Otherwise map the relation type and ordered arguments.
3. If the exact mapped relation exists in the target graph, classify it as `preserved`.
4. Otherwise classify it as `violated`.

Statuses:
- `structurally_preserved`: all source relations mapped and preserved.
- `partial`: no mapped contradiction, but at least one source relation is unmapped.
- `counterexample`: at least one fully mapped source relation is absent in the target.
- `untestable`: no source relation could be checked.

A missing mapping is not a contradiction. A mapped role reversal is a contradiction to the current bridge. Extra target relations are reported separately and do not invalidate a partial source-to-target mapping.

`mapping_coverage = mapped_source_relations / total_source_relations`.

`preservation_rate = preserved / mapped_source_relations`; it is `None` when no relation can be tested. This separation prevents unknown/unmapped relations from being counted as failures or successes.

## Security and epistemic limits

- Evidence refs are identifiers only; this module does not verify source authenticity or split permissions.
- Scope conditions and counterexample strings are declarative metadata, not executable predicates.
- A preserved graph mapping is structural compatibility, not causal equivalence.
- A bridge may be valid only within its declared scope; scope enforcement is a later evaluator responsibility.
- No score or confidence is emitted. A weighted score would conceal the distinction between coverage, contradiction, and untested claims.
- The deterministic digest identifies the bridge payload; it is not a digital signature.

## Tests

The test suite checks:
- positive ordered relation preservation;
- role reversal as a counterexample;
- unmapped relations remain distinct from contradictions;
- explicit node-type alignment;
- deterministic bridge digest;
- wholly untestable mappings.

The Yixiang binary encoder was also hardened: it now rejects floats, strings and booleans rather than coercing them to bits. This prevents malformed observations from silently becoming valid hexagram IDs.

## Next gates

1. Add a small exact graph-mapping enumerator that produces candidate mappings, not just validates supplied ones.
2. Add symmetry/role-permutation policies as explicit, versioned operators.
3. Add adversarial cases: surface similarity with unrelated relations, relation reversal, extra target structure, partial mappings and scope violations.
4. Connect proposals to E12-A6 and evidence to E09 only through their existing owners.
5. Evaluate against semantic-similarity/RAG and generic structure-mapping baselines with identical candidate and compute budgets.

Passing these tests validates only the reference contract. It does not establish that Yi-Xiang features improve general reasoning.
