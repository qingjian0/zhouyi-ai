# ZNCA × XSL Integration Contract

Date: 2026-11-11  
Status: architecture integration proposal; no runtime integration claimed.

## 1. Objective

Define how typed Xiang-Shu-Li structures and explicit analogy operators participate in ZNCA/RSDN without creating a second memory system, bypassing evidence governance, or treating traditional correspondences as unquestionable facts.

## 2. Responsibility mapping

| ZNCA responsibility | XSL / existing component | Contract |
|---|---|---|
| 象 / observation grounding | Observation extraction | Emits source-grounded entities, attributes, events and relation candidates; uncertain extractions remain uncertain |
| 数 / state and combinatorics | Hexagram/line encoding + typed graph | Encoding is a representation, not a semantic conclusion; graph identity and role identity remain distinct |
| 理 / invariants and constraints | E13 contract + relation schemas | Types, role semantics, arity, context, time and evidence state are explicit |
| 变 / state transitions | CPG-EI lifecycle / E12-A6 | Mutations are versioned events with rollback and dependency impact |
| 类 / structural transfer | XSL-1, XSL-2, XSL-3 | Validate explicit bridges, enumerate competing node maps, and apply only declared role transforms |
| 择 / candidate arbitration | E09 evidence ledger + evaluator | Candidate selection is evidence-aware and multi-dimensional; evaluator data stays isolated |
| 言 / realization | Language/action adapter | Emits language or actions from selected structured outputs; does not own canonical memory |

## 3. Canonical data flow

1. **Observe**: retain raw text/image/audio/tool results with source spans and provenance.
2. **Ground**: create candidate typed nodes and relations. Mark each item OBSERVED, INFERRED, DISPUTED or UNKNOWN.
3. **Encode**: optionally attach Yi-Xiang encodings and viewpoint metadata. Never overwrite the underlying observation.
4. **Constrain**: validate node types, relation arity, role semantics, context keys, time validity and source references.
5. **Enumerate**: XSL-2 proposes a bounded set of injective partial node mappings under explicit type/relation correspondences.
6. **Transform**: XSL-3 may create a separately versioned transformed-relation hypothesis. It does not mutate the source graph and is not implicitly applied.
7. **Validate**: XSL-1 checks exact ordered relation preservation for each candidate or explicitly transformed candidate graph.
8. **Commit prediction**: bind query, scope, split and commit digest through E09 before hidden evidence is revealed.
9. **Evaluate**: report support, counterexample, unknown, conflict, coverage, search completeness, resource cost and provenance separately.
10. **Revise**: E12 lifecycle records promote/suspend/reject/split/merge/rollback; the event ledger remains append-only.
11. **Realize**: language/action layer renders the selected result and cites supporting evidence.

## 4. Canonical object boundaries

### Observation
Immutable reference to source material plus extracted claims: source ID/span, modality, timestamp, extraction version, claim status and optional confidence metadata. Confidence is never substituted for evidence status.

### Relational graph
A graph is a versioned projection of observations, not the source of truth. It contains typed nodes; typed relations and ordered argument slots; explicit role semantics (ORDERED_NAMED, ORDERED_POSITIONAL, UNORDERED, UNKNOWN); scope, temporal validity and context; provenance edges to observations and evidence events.

### Analogy candidate
A candidate contains source/target graph version IDs, node and relation correspondence declarations, optional type abstraction, optional XSL-3 transform IDs/versions, XSL-1 validation, XSL-2 search budget/states/search_complete/results_truncated, unmatched/preserved/violated relations, predictions, counterexamples, evidence refs and evaluator split.

No single scalar "analogy confidence" is canonical. Any downstream ranker must expose its features, calibration set, version and cost.

### Transform application
A transform application is a new hypothesis object with transform ID/version, source relation, transformed relation, argument permutation, scope/evidence refs and semantic status HYPOTHESIS_ONLY until independently validated. It must not rewrite original observations or silently change the role schema.

## 5. Role semantics and symmetry policy

E13 role semantics are authoritative for representation:
- ORDERED_NAMED: named roles are semantically distinct.
- ORDERED_POSITIONAL: argument slots are positional and ordered.
- UNORDERED: participants may be treated as a set/multiset only under declared schema.
- UNKNOWN: preserve opaque positions; do not infer symmetry.

XSL-3 is a hypothesis operator layer, not a replacement for these semantics. A non-identity permutation can be proposed even for an ordered relation, but remains a distinct transformed hypothesis and cannot be treated as an equivalent fact unless a domain-specific validator supplies evidence.

Do not conflate symmetry, inverse relation, role reversal, temporal reversal and yin/yang inversion. Each needs a distinct operator family, schema, version and test set.

## 6. Evidence and lifecycle ownership

- E09 owns prediction commitment, evidence reveal, query/scope/split binding and evaluator separation.
- E12-A6 owns candidate lifecycle events and rollback lineage.
- E12-A20 owns exact probabilistic/constraint solver semantics; energies, marginals and probabilities remain distinct.
- E13 owns shared experience representation and role semantics.
- XSL owns candidate structural mappings and explicit transform proposals.
- ZNCA/CSF owns persistent state projection, event sourcing and bounded working-set orchestration.

XSL must not create a parallel evidence ledger, and ZNCA must not treat a generated summary as authenticated evidence.

## 7. Selection protocol

Candidate arbitration is constrained multi-objective decision-making, not a universal weighted score. Report separately:
1. structural preservation and contradiction count;
2. relation/node coverage and type compatibility;
3. scope/context/time compatibility;
4. evidence quality and independence;
5. predictive support and counterexamples;
6. search completeness and result truncation;
7. computational cost and memory footprint;
8. viewpoint/transform provenance.

Outcomes: SELECTED, AMBIGUOUS, UNTESTABLE, REJECTED, ABSTAINED. Incomplete search cannot claim global optimality; no counterexample found does not prove none exists.

## 8. Mobile execution implications

CSF stores an append-only observation/event ledger, compact graph versions and provenance index, candidate/transform records, and active task state plus a bounded working subgraph. It does not keep every historical token in active model state. Exact details are retrieved by source span. Structural summaries retain evidence links and can be invalidated when source claims change.

Budget independently: graph/index bytes, active subgraph bytes, candidate count and mapping states, transform branches, retrieval IO/decode memory, and neural encoder/realizer working memory. No O(1) claim is allowed for arbitrary full-history or full-graph queries.

## 9. Required ablations and failure tests

- ZNCA/RSDN without XSL; XSL-1 only; XSL-1 + XSL-2; XSL-1 + XSL-2 + XSL-3.
- XSL-3 disabled vs identity-only vs explicit transforms.
- Generic graph matcher vs Yi-Xiang multi-view mappings.
- UNKNOWN role semantics vs declared UNORDERED.
- Random and inverse transforms.
- Source/target domain and entity-disjoint splits.
- Counterexample injection, scope violations, evidence leakage and post-reveal contamination.
- Graph growth and working-set memory pressure.

Measure transfer accuracy, negative transfer, false-preservation rate, calibration, abstention, search completeness, CPU, PSS/RSS, IO, energy and update cost.

## 10. Non-goals and falsification

This contract does not claim Yi-Xiang encodings are universally valid, XSL candidates are causally equivalent, explicit graph reasoning beats Transformer models, 1M source tokens equal 1M native attention tokens, graph memory has constant cost, or XSL-3 transforms are semantic truths.

If XSL adds complexity without improving held-out transfer, evidence traceability or resource efficiency, retain only independently useful representations and reject added operator complexity.

## 11. Implementation sequence

1. Freeze shared relation schema and role semantics across XSL and E13.
2. Add provenance-bearing graph projection from observations.
3. Add XSL candidate records with search completeness and transform lineage.
4. Bind E09 commit/reveal to candidate digests.
5. Bind E12 lifecycle transitions to candidate versions.
6. Implement CSF graph/event persistence and incremental invalidation.
7. Run ablations before neural RSDN integration.
8. Only then train relation/state operators and compare against strong sequence and graph baselines.
