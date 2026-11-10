# E10-A Object-Disjoint Generator Protocol (A-O) — 2026-11-11

Status: design/preregistration proposal. No implementation, test, CI, or benchmark result is claimed.

Base: PR #55 head `755f99353c1e7e2f355c4208e6d9eb7146f1f6c3`.

## 1. Research question and claim boundary

A-O asks whether a learner can infer and apply a relation mechanism to object identities that never appeared in Support.

It is not enough to split the existing observation list after generation. The current E10-A generator creates one shared object table, reuses those objects across source instances, and the current task adapter copies the full object table into Support. A post-hoc filter can leak Query object attributes through that table and can change the generated sample distribution.

A valid A-O episode must therefore allocate disjoint object pools before emitting observations and instantiate the same latent relation mechanism independently inside each pool.

A-O supports the narrow claim:

> Given a relation mechanism and attribute vocabulary evidenced by Support, the learner can apply that mechanism to previously unseen object identities whose attributes are supplied at Query time.

It does not establish transfer to a new relation family, new attribute vocabulary, new environment, causal discovery, or open-world primitive invention.

## 2. Generator construction order

The generator must follow this order. Reordering steps 3–6 into post-hoc filtering is not equivalent.

1. Sample a world seed and a latent mechanism specification: relation arity, role constraints, context gate, and the values required by each role.
2. Create two disjoint object-ID namespaces/pools: `support_pool` and `query_pool`. IDs must be unique across the complete episode.
3. Sample object attributes independently inside each pool from the same declared categorical distribution. Use stratified category allocation per pool so every required role value and at least one violating value are represented. Record any balancing constraints in the manifest.
4. Instantiate the exact same latent mechanism in each pool: same relation symbol, role-value mapping, context key/value, arity, and semantics. Do not reveal this latent specification to the learner.
5. Generate source role assignments separately within each pool. Every positive, context-negative, and role-near-miss derived from a source assignment remains inside that pool and shares its evaluator-only source provenance.
6. Emit Support observations only from `support_pool`, and Query observations only from `query_pool`. Query outcomes are retained only by the evaluator.
7. Serialize the two learner payloads independently. Support payload contains Support objects and labelled Support observations. Query payload contains Query objects and unlabelled Query observations, and is supplied only after the learner has committed its predictions.

Use independent deterministic RNG streams derived from the world seed for mechanism generation, Support object generation, Query object generation, and each pool's observation generation. This prevents incidental random-number consumption in one pool from silently changing the other pool.

## 3. Object and attribute semantics

Object-disjointness concerns object identity, not feature vocabulary.

Allowed across Support and Query:
- same attribute keys and categorical value vocabulary;
- same relation symbol and latent role/context mechanism;
- same environment definition when the experiment is explicitly an in-distribution object-transfer test.

Forbidden across Support and Query:
- any shared object ID;
- any Support payload field, cache, lookup table, or serialized side channel containing Query object IDs or Query object attributes;
- any observation whose participant list mixes objects from the two pools;
- any evaluator-only provenance, latent role mapping, validity, violation, or Query outcome in learner payload.

Query object attributes are legitimate prediction inputs. They must be visible in the Query inference payload, but must not be visible in Support payload before prediction. The learner must receive the Query payload only after a prediction-commit record is durably written.

The generator should use opaque, independently sampled object IDs. IDs must not encode pool membership, role category, template, or outcome. Pool membership remains evaluator-only.

## 4. Sampling and identifiability requirements

A pool must be rejected before evaluation if it cannot instantiate the declared mechanism with sufficient support.

At minimum, for every relation template and each pool:
- all required role values are represented;
- at least two distinct object identities are available for every required role value;
- at least one non-required value is available for each role constraint to construct a role near-miss;
- the context gate and at least one context-mismatch value are represented;
- each role has at least two distinct positive source assignments, unless the preregistered experiment explicitly studies a lower-support regime;
- participant identities within each observation are distinct.

These are generator feasibility checks, not learner-visible hints. Report pool sizes, category counts, positive/negative counts, role support, and rejected-seed reasons. Do not silently shrink the number of examples or reuse Support objects to repair a deficient Query pool.

The exact minimum counts should be fixed before locked evaluation. If a requested configuration cannot meet them, return a typed failure such as `INSUFFICIENT_ROLE_POOL`; do not downgrade the split policy.

## 5. A-O task contract

The evaluator should return two independent learner payload byte strings and retain truth separately.

### Support payload
- episode/schema version;
- Support object table only;
- Support observations with labels;
- relation symbols and observable context;
- no Query object IDs, Query attributes, Query observations, or evaluator metadata.

### Query payload
- episode/schema version;
- Query object table only;
- Query observations without labels;
- relation symbols and observable context;
- no Support labels or evaluator truth.

### Evaluator-only records
- pool assignment for each object;
- source-group provenance;
- latent templates and role mappings;
- Query outcomes and violation labels;
- split manifest and payload hashes.

The runner must place evaluator truth in a separate process or service boundary. Returning `support`, `query`, and `evaluator_truth` in one Python dictionary is not an isolation guarantee.

## 6. Required invariants and canary tests

A-O must fail closed unless all of the following hold:

1. `Support.object_ids ∩ Query.object_ids = ∅`.
2. Every Support observation participant belongs to Support objects only.
3. Every Query observation participant belongs to Query objects only.
4. Every generated observation maps to exactly one evaluator truth record.
5. Every source group and all its derived observations belong to exactly one pool.
6. The same declared latent mechanism is used in both pools.
7. Support serialization contains no Query object ID or Query attribute value attached to a Query object.
8. Query serialization contains no Support outcome/label or evaluator-only field.
9. Mutating evaluator truth leaves both learner payload byte strings unchanged.
10. Mutating Query labels leaves Support payload bytes and the object-pool assignment unchanged.
11. Repeating the same seed/configuration reproduces exact payload hashes; changing the seed changes opaque identities without changing the declared mechanism family.
12. An invalid or underpowered pool returns an explicit failure, never a fallback to A-P or A-S.

Use recursive key/value canaries, not only top-level key checks. Include deliberately colliding opaque strings in adversarial fixtures so the tests verify object-scoped records and nested payloads rather than relying on accidental string absence.

## 7. Manifest and diagnostics

The manifest must include:
- generator/schema version and world seed;
- explicit `split_policy: A-O` and `sampling_unit: object_id`;
- independent RNG derivation/version;
- Support/Query object counts and object-ID set hashes;
- Support/Query observation counts and observation-ID set hashes;
- relation/template coverage and positive/negative coverage per side;
- per-role distinct-object support and attribute-category histograms;
- source-group counts and source-group size histograms per side;
- object-ID intersection count (must be zero);
- learner payload hashes and evaluator truth hash;
- all excluded seeds and machine-readable failure reasons.

Do not expose pool membership or object-set hashes as learner features. The manifest is evaluator metadata.

## 8. A-C connected-component track is related but not interchangeable

Build the bipartite incidence graph with object nodes and observation nodes. Connect each observation node to every participant object node. A connected component is the transitive closure of object reuse through observations.

A-C assigns whole connected components to one side. A-O assigns object identities to disjoint pools before observation generation. A-O can still split a naturally connected component across sides if its objects are independently assigned and no observation crosses pools; A-C forbids splitting any component, including indirect object-sharing chains.

For A-C:
- compute components from emitted participant edges, not from source-group IDs;
- report component count, size distribution, largest-component fraction, and per-relation coverage;
- require enough components to populate both sides and meet the preregistered coverage constraints;
- return `INSUFFICIENT_COMPONENTS` or `UNSPLITTABLE` when constraints cannot be met;
- never relabel a weaker A-O/A-S split as A-C.

A generator that deliberately emits one connected component per pool can make A-C trivially equivalent to a pool split. Such a fixture is useful for correctness tests, but it is not evidence that the general E10-A generator supports component-disjoint evaluation. Report this distinction.

## 9. Matched experiment design

Compare A-P, A-S, A-O, and A-C as separate evaluation tracks. Do not pool their scores into one headline metric.

For A-O:
- freeze mechanism families, attribute distributions, sample budgets, and feasibility thresholds on development seeds;
- evaluate on locked world seeds not used for generator tuning;
- use at least 30 independent world-seed blocks as an initial uncertainty target, increasing the count if intervals remain wide;
- report per-seed results, group-macro metrics, observation-micro metrics, and object-level coverage;
- compute uncertainty by resampling independent world-seed blocks, not correlated observation rows;
- compare against memorization, majority, simple attribute-rule, and bounded exact-search controls;
- include a negative control in which Support and Query use deliberately different role mappings; the learner should abstain or fail rather than appear to transfer;
- include an attribute-distribution-shift arm separately, so ordinary object transfer is not conflated with OOD feature transfer.

The learner receives equal total compute and the same prediction/revision budget across candidate methods. Query labels remain locked until all predictions for that episode are committed.

## 10. Implementation sequence and acceptance gates

1. Add a new generator entry point for A-O; do not silently change the existing A-P/A-S generator semantics.
2. Add evaluator-only pool provenance and validate every participant against its pool.
3. Add separate Support/Query object tables and explicit query-time payload delivery.
4. Add process-boundary runner and recursive payload-canary tests.
5. Add object-disjoint and same-mechanism assertions.
6. Add feasibility diagnostics, manifest fields, and typed unsplittable failures.
7. Run focused tests, the full repository test suite, and GitHub Actions on the exact PR head.
8. Only after exact-head CI and independent protocol review, mark the PR ready for review.

Until these gates pass, describe A-O as a protocol proposal, not an implemented split or a measured transfer result.

## 11. Explicit non-claims

This protocol does not demonstrate:
- generalization to unseen relation families or unseen attribute vocabularies;
- causal reasoning or intervention discovery;
- autonomous creation of new primitive predicates;
- natural-language understanding or general intelligence;
- a non-autoregressive model advantage;
- an empirical advantage for Yijing-inspired priors.

Those require separate hypotheses, controls, and locked evaluations.
