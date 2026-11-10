# E10-A Query-Boundary Independent Audit (2026-11-11)

Status: independent research audit and protocol proposal; no learner result is claimed.
Base: `research/e10a-latent-world-generator-2026-11-10`.
Scope: additive audit only. Does not modify E10-A v2, PR #36, E09, or main.

## 1. Executive finding

E10-A v2 improves the generator by defining reusable latent role/attribute/context templates before emitting observations and by randomizing participant presentation order. The learner/evaluator serialization boundary is useful.

However, the current generator output is not yet a train/support/query benchmark. `Episode.learner_view()` serializes every generated observation together with its outcome label. There is no per-episode query-label withholding, no support/query manifest, and no learner-facing API that supplies support examples while withholding query outcomes. Consequently, the current tests establish serialization separation and generator invariants, not generalization to unseen instances.

The generator also creates fresh opaque relation symbols, attribute keys/values, context symbols, and template IDs per episode. This is appropriate for symbol-renaming stress tests, but it means cross-episode semantic reuse is not currently established. A learner cannot be credited with cross-episode concept transfer unless a stable latent mechanism is intentionally shared while surface symbols are independently renamed.

## 2. Evidence from source inspection

Inspected:
- `prototype/e10a_latent_generator.py`
- `tests/test_e10a_latent_generator.py`
- `docs/E10A_LATENT_WORLD_GENERATOR_V2.md`
- `docs/E10_XIANG_OPERATOR_LEARNING.md`

Observed facts:
1. `learner_view()` emits all `observations`, including each row's `outcome`.
2. `audit_view()` contains latent templates and role mappings, and tests assert that these are absent from the learner serialization.
3. Participant presentation order is shuffled and evaluator role mappings are kept separately.
4. Current split manifest separates episode/object identities and hashes, but does not define within-episode support/query partitions.
5. The documented v2 limitations already acknowledge that all generated observation labels are exposed and that strict relation-template/attribute-combination OOD splits are not implemented.
6. The identifiability report checks generator-side necessary conditions; it is not a proof that the target is unique over an arbitrary learner hypothesis class.

## 3. Required benchmark boundary

Do not overload one split to answer several different questions. Define three separate evaluation tracks.

### Track A — Within-episode relation induction

- Generate one latent relation template per episode.
- Split observations into labelled support and hidden-label query sets before serialization.
- The learner receives objects, attributes, relation symbol, context, and support outcomes only.
- Query participants/context are visible, but query outcomes and evaluator violation labels are withheld.
- Query samples must be generated independently of support sampling, with object reuse policy explicitly declared.
- Report exact role-structure recovery up to role permutation, query prediction, abstention, and calibration.

This tests whether the learner can infer a relation from examples and apply it to unseen instances in the same world.

### Track B — Cross-episode mechanism transfer

- Reuse a latent mechanism family across episodes while independently renaming object IDs, attribute keys/values, relation symbols, and context symbols.
- Keep the mechanism mapping hidden from the learner.
- Split by latent mechanism identity, not only episode/object identity.
- Include both seen-mechanism/new-symbol and unseen-composition conditions.
- Report whether the learner transfers relational structure rather than memorizing symbol strings.

This tests transfer of a learned relational operator. It must not be conflated with Track A.

### Track C — Relation-family OOD and identifiability

- Hold out complete relation-template families and role-arity/composition patterns.
- Include hard negatives with similar attributes but invalid role assignment, context, or relation composition.
- Run an oracle identifiability check over the declared hypothesis class.
- If multiple hypotheses are observationally equivalent, mark the episode ambiguous and score calibrated ABSTAIN as correct behavior.
- Do not score role permutation as an error when roles are identifiable only up to permutation.

This tests the boundary between valid induction and unsupported extrapolation.

## 4. Minimal data contract

A benchmark episode should expose two physically distinct payloads:

- `support_view`: learner-visible labelled support examples.
- `query_view`: learner-visible query inputs only; no outcome, violation, role mapping, template ID, family ID, seed, or generator truth.
- Evaluator-only payload: query outcomes, latent mechanism, role mapping, violation cause, split provenance, and identifiability certificate.

The serialized learner payload must be constructed from an explicit allowlist, not by deleting known forbidden keys from an evaluator object.

The split manifest must include disjoint sample IDs, partition counts, hashes, mechanism-family IDs (evaluator-only), and the exact split policy. No evaluator-only identifier may appear in learner-visible metadata.

## 5. Mandatory tests before a learner benchmark

1. Query-label canary: mutate all hidden query labels while holding learner payload byte-identical.
2. Evaluator-field canary: mutate role mappings/template IDs/family labels; learner payload must remain byte-identical.
3. Support/query sample-ID disjointness.
4. Query outcome absence recursively, including nested metadata.
5. Participant-order invariance and role-permutation equivalence.
6. Attribute-key/value and relation-symbol renaming invariance.
7. Cross-episode mechanism-sharing tests for Track B.
8. Family-disjoint split tests for Track C.
9. Oracle identifiability/ambiguity detection under the declared hypothesis class.
10. Shortcut attackers over IDs, ordering, cardinalities, field shapes, and generation metadata.
11. Baseline sanity checks: lookup, nearest-neighbour, fixed-rule, finite-DSL enumerator, ordinary graph/hypergraph, random prior, and budget-matched learner.
12. Full candidate-generation and candidate-evaluation cost accounting.

## 6. Acceptance and claim levels

- L0: generator correctness and information-flow boundary only.
- L1: within-episode support-to-query generalization.
- L2: cross-episode transfer under symbol renaming.
- L3: relation-family OOD generalization with calibrated abstention.

Passing generator unit tests supports L0 only. Passing Track A does not establish Track B or C. No result should be described as open-world autonomous discovery unless the learner also invents or revises its own representation/operator language and succeeds on independently generated, previously unseen mechanism families.

## 7. Recommended next implementation sequence

1. Add immutable support/query partition objects and an explicit `learner_episode_view()`.
2. Add query-label and evaluator-field canary tests.
3. Add a small Track A benchmark and oracle baseline.
4. Add Track B only after stable latent mechanism identity is separated from randomized surface symbols.
5. Add Track C after the hypothesis-space identifiability checker is implemented.
6. Only then compare E09 NG-A–NG-E, XPC operator induction, hypergraph baselines, and gradient/hybrid baselines under matched sample and compute budgets.

## 8. Coordination boundary

This branch is an independent audit. It intentionally does not edit the v2 generator branch, PR #36, PR #34, E09, or main. Any implementation should be proposed as a separate follow-up after maintainers review this protocol.
