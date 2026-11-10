# E10-A Object-Disjoint Generator Design and A-O/A-C Semantics (2026-11-11)

## Status

Design/proof note only. No A-O implementation, benchmark result, test pass, or autonomous-discovery claim is made.

Base: PR #55 head `755f99353c1e7e2f355c4208e6d9eb7146f1f6c3`.

## 1. Normalize the split semantics

Let:
- (R) be the set of relation-observation nodes;
- (O) be the set of object nodes;
- (E \subseteq R \times O) contain an edge exactly when an object participates in an observation.

This is the **object-observation incidence bipartite graph**. Do not add relation-symbol, template, episode, or source-group nodes when making the equivalence claim below.

For a partition of observations into Support (R_S) and Query (R_Q), define the used-object sets:

`O_S = {o in O | exists r in R_S: (r,o) in E}`

`O_Q = {o in O | exists r in R_Q: (r,o) in E}`

### A-O: object-disjoint

`O_S intersect O_Q = empty`.

If the protocol also exposes object tables, strengthen the check to require the Support and Query object-table ID sets to be disjoint, including unused distractors.

### A-C: incidence-component-disjoint

No connected component of the incidence graph contains both a Support observation node and a Query observation node.

### Proposition: A-O and A-C are equivalent under this graph definition

- A-C implies A-O: if object (o) appeared in both Support and Query observations, those observations would be adjacent to the same object node and therefore belong to one component spanning both partitions.
- A-O implies A-C: if a component contained observations from both partitions, any path between them must transition from a Support observation to a Query observation through an object node adjacent to both sides. That object would be shared, contradicting A-O.

Therefore A-O and A-C are not distinct generalization capabilities under the stated incidence graph. They are alternative ways to enforce the same no-shared-observed-object boundary.

## 2. Keep their operational distinction

- **A-O direct construction:** create disjoint Support and Query object pools before relation instances are generated. This is the preferred benchmark construction because it avoids post-hoc selection bias and makes the intended split explicit.
- **A-C post-hoc audit/split:** build incidence components from an existing dataset, assign whole components to one side, and report whether enough independent components exist. This is useful as a feasibility diagnostic, but object reuse may chain most observations into one giant component.

Do not report A-O and A-C as two independent score tracks if both enforce the same incidence boundary. Report the construction method and the component-size diagnostics separately.

If a future A-C definition includes extra edges (for example, shared template, relation-symbol, or episode nodes), state that graph explicitly; the equivalence above no longer automatically applies.

## 3. Preferred A-O generator architecture

Separate the latent mechanism from object instances and observations:

1. **LatentMechanism**: relation symbols, arity, role constraints, context constraints, and composition rules. This is shared by Support and Query.
2. **SupportObjectPool**: independently generated opaque object IDs and attributes.
3. **QueryObjectPool**: independently generated opaque object IDs and attributes; IDs must be disjoint from Support.
4. **SupportObservationBatch**: instantiate the shared mechanism only using Support objects; expose Support labels.
5. **QueryObservationBatch**: instantiate the same mechanism only using Query objects; hide Query labels from the learner.
6. **EvaluatorTruth**: hold query labels, role mappings, source provenance, and latent mechanism truth outside the learner process.

The mechanism is shared; the objects and base relation instances are not. This tests transfer of a learned relation mechanism to unseen object identities, not cross-world or relation-family transfer.

### Attribute support constraints

Independent random pools can accidentally omit a required role value, creating a generator-induced unobservable task. Prevent this by construction:

- For every mechanism feature key and every required role value, ensure the minimum number of objects exists independently in both pools.
- Add nuisance/distractor values in both pools.
- Match pool-level attribute marginals and relevant context distributions under a declared tolerance.
- Record per-pool support counts and reject episodes that fail the preregistered minimum.
- Do not copy object records from one pool to the other to repair coverage.

Use independent deterministic RNG substreams derived from the episode seed and fixed split labels (for example, `support-pool` and `query-pool`). This prevents changes in Support generation order from silently changing Query object identities.

## 4. Learner-facing payload contract

The learner must receive two temporally distinct payloads:

- **Support phase:** Support object table plus labeled Support observations.
- **Query phase:** Query object table plus unlabeled Query observations, only when predictions are requested.

The Support object table must contain Support IDs only. The Query object table must contain Query IDs only. Query object attributes are necessary for inference and are not labels; they must be provided at query time rather than leaked into the Support phase.

The evaluator must not return a single in-memory object containing learner payloads and hidden truth. Use separate serialization/process boundaries. The evaluator retains the mapping from query observation IDs to labels, role mappings, source IDs, and latent template truth.

Required canaries:
- Support and Query object-table IDs are disjoint.
- Support observation participants are subsets of Support object IDs.
- Query observation participants are subsets of Query object IDs.
- No query object ID or attribute record appears in the Support payload, nested metadata, cache, or manifest.
- Query payload contains no outcome, validity, violation, role map, template ID, or source-group ID.
- Mutating evaluator truth does not change serialized learner payload bytes or hashes.
- A recursive payload scan detects forbidden evaluator fields and values.
- The learner process cannot access evaluator files, descriptors, or APIs.

## 5. Split and statistical reporting

Report:
- number of Support and Query objects;
- object-ID intersection (must be zero);
- observation counts and positive/negative counts on evaluator side;
- per-feature/per-value support counts in each object pool;
- per-relation and per-context coverage;
- incidence component count, size distribution, and maximum component size;
- unsplittable episodes and rejection reasons;
- group-macro and observation-micro metrics;
- seed/world-level uncertainty, not row-level independence assumptions.

A-O is **known-mechanism, unseen-object transfer**. It does not establish:
- unseen relation-symbol transfer;
- unseen mechanism-family transfer;
- cross-episode latent mechanism recovery;
- new primitive/operator invention;
- open-world concept discovery.

## 6. Acceptance tests before benchmark use

1. Same latent mechanism hash for Support and Query generation.
2. Disjoint opaque object IDs and object-table IDs.
3. Every required role value has sufficient Support and Query object coverage.
4. No Support observation references Query objects and vice versa.
5. Query object attributes are present only in the Query-phase learner payload.
6. Query labels and all evaluator annotations are absent from learner payload.
7. Source-instance provenance is split within each pool; no base instance is shared across pools.
8. Identical mechanism, matched budgets, and matched distribution diagnostics across baselines.
9. Determinism under fixed root seed and split-label substreams.
10. Negative controls: deliberately share one object across partitions and verify the validator rejects the episode.

## 7. Current implementation gap

PR #52 provides evaluator-only source provenance and a selectable A-S grouping policy. It does not implement independent Support/Query object pools. Its task adapter currently returns the episode-wide object table in Support, so Query object IDs and attributes remain visible there. The adapter also returns evaluator truth alongside learner payloads, which is not a physical security boundary.

The next implementation should add a generator-level A-O path with phase-specific payload serialization. It should not try to obtain A-O by filtering the existing episode-wide object table after observations have already been generated.
