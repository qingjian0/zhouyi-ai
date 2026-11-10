# E11-A/B: Autonomous Concept Formation and Hierarchical Structure Discovery (2026-11-11)

Status: research specification and preregistration draft only. No learner implementation, benchmark run, or empirical capability claim.
Base: `research/e10bc-joint-analogy-operator-2026-11-11`.
Scope: isolated E11 branch; does not modify main, E02/E09/E10 implementations, or parallel AI branches.

## 1. Research question

Can a learner construct useful concepts and multi-level structure from observations without receiving the target concept labels, object boundaries, hierarchy, or number of abstraction levels?

This is deliberately split into two problems:

- **E11-A Concept formation:** discover reusable units/bundles from raw or weakly structured observations.
- **E11-B Hierarchy discovery:** discover part-whole, instance-class, role, and scale relations among those learned units.

The learner must be able to conclude that a proposed concept is unsupported, context-specific, redundant, or ambiguous. It must not be forced to create a hierarchy for every dataset.

## 2. What counts as a concept?

A concept is not merely a cluster, label, embedding centroid, or frequent itemset. Define a candidate concept schema:

`K=(S, P, R, B, I, C, E)`

- `S`: typed slots / variable positions.
- `P`: attribute and state predicates over slots.
- `R`: internal role-sensitive relational constraints.
- `B`: boundary conditions distinguishing members from non-members.
- `I`: invariants expected to persist across nuisance transformations.
- `C`: context and applicability conditions.
- `E`: provenance-linked support, counterexamples, unknowns, and conflicts.

A concept instance is a grounded assignment of observed entities/events to the schema's slots. A concept is useful only if it compresses repeated observations and supports predictions, interventions, or composition on held-out cases.

Concept identity must be distinct from:
- surface label or symbol;
- one particular instance;
- current state of an instance;
- parent/child hierarchy position;
- a hypothesis version.

## 3. Concept boundary as a falsifiable hypothesis

For candidate schema K, define membership as a partial decision:
`m_K(x,c) in {IN, OUT, UNKNOWN}`.

The learner may not force a binary answer when evidence is insufficient. Membership should be based on structural constraints and context, not on hidden generator labels.

A candidate boundary is evaluated by:
1. within-concept predictive consistency;
2. separation from hard negatives;
3. stability under nuisance transformations;
4. usefulness for predicting unseen attributes/relations;
5. ability to support valid composition with other concepts;
6. complexity and description length;
7. calibrated UNKNOWN/ABSTAIN behavior.

Do not optimize cluster purity alone. A partition that perfectly reproduces arbitrary labels but has no predictive or compositional value is not a discovered concept.

## 4. Candidate discovery mechanisms

Test multiple discovery mechanisms as separate baselines/arms:

- **Recurring-substructure mining:** propose repeated typed subgraphs/hypergraphs.
- **Anti-unification:** abstract common structure across examples into slots and constraints.
- **Predictive compression:** retain a schema when it shortens the description of observations and predicts held-out structure.
- **Invariant discovery:** identify features/relations stable across interventions or nuisance changes.
- **Contrastive boundary search:** actively seek nearest counterexamples that violate one candidate constraint.
- **Compositional utility:** prefer concepts that participate in multiple independently validated higher-order structures.

No single mechanism is assumed best. The combined learner must be compared to each isolated arm to determine which signal contributes.

## 5. Hierarchy is not one tree

A world may contain several overlapping organization systems. Do not force a single taxonomy.

Represent hierarchy as a typed directed hypergraph:
`H=(K, E_h, 	au_h, Gamma)`

Possible edge types:
- PART_OF: component-to-whole;
- INSTANCE_OF: instance-to-schema;
- SPECIALIZES: narrower concept to broader concept;
- ROLE_IN: concept participates in a relation as a role;
- COMPOSES_WITH: compatible concepts jointly form a structure;
- SCALE_OF: same process viewed at a different scale;
- REALIZES: abstract schema is implemented by a concrete structure;
- DEPENDS_ON: one structure's behavior depends on another.

Each edge has scope, evidence, direction, confidence, and counterexamples. Edge types are hypotheses, not interchangeable parent pointers.

Allow:
- multiple parents;
- overlapping concepts;
- cross-cutting role membership;
- context-dependent hierarchy;
- cycles only for explicitly permitted relation types (e.g. DEPENDS_ON cycles must be detected and reported, not silently treated as a taxonomy);
- unresolved relations.

A taxonomy tree is a restricted baseline, not the default ontology.

## 6. Multi-scale discovery

A scale is defined operationally by the granularity of the entities/relations needed to explain a task, not by a fixed number of levels.

For each candidate scale:
1. construct a coarse representation from lower-level structures;
2. preserve links to constituent evidence;
3. test whether the coarse representation predicts outcomes unavailable from isolated parts;
4. compare against a flat model with equal information and compute budget;
5. split the coarse unit if it hides systematic counterexamples;
6. merge only if the merged schema remains discriminative and predictive.

A higher-level concept is justified only when it provides measurable explanatory or predictive gain after accounting for added complexity. Emergent behavior cannot be inferred merely from a large cluster.

## 7. Joint concept/hierarchy learning loop

1. Extract neutral observations with no target concept IDs or hierarchy metadata.
2. Generate candidate substructures and candidate boundaries.
3. Build provisional concept schemas with explicit slots and invariants.
4. Search for counterexamples and near-boundary cases.
5. Test candidate concepts on held-out objects and contexts.
6. Propose typed hierarchy edges among validated concepts.
7. Evaluate whether hierarchy edges improve prediction, compression, or transfer.
8. Discover higher-level structures from validated lower-level concepts.
9. If higher-level failures point to incorrect lower-level boundaries, revise the relevant concept version with lineage.
10. Freeze a version and test it on locked domains.

Compare alternating concept/hierarchy updates with concept-only, hierarchy-only, and one-way pipeline controls. Keep evidence provenance immutable.

## 8. E11-A/B benchmark suite

### E11-1: Unknown concept count and boundaries
Generate worlds with a hidden number of recurring structural motifs, variable nuisance attributes, overlapping memberships, and hard negatives. The learner receives observations only.

Measure:
- concept boundary precision/recall under declared equivalence;
- number of concepts proposed and false concept creation;
- instance assignment coverage and UNKNOWN rate;
- schema complexity and held-out predictive gain;
- robustness to symbol and order permutation.

### E11-2: Object-disjoint and context-disjoint transfer
Train on disjoint object identities and selected contexts; test on unseen objects and held-out contexts. Random row splits are not sufficient.

Measure:
- schema recovery up to automorphism;
- membership calibration;
- false transfer under context shift;
- counterexample discovery latency.

### E11-3: Overlapping and multi-parent concepts
Construct cases where instances belong to multiple valid concepts and where a concept has more than one parent relation. Compare multi-relational hierarchy against forced tree clustering.

Measure:
- typed edge precision/recall;
- invalid forced merges;
- lost valid memberships;
- downstream task utility.

### E11-4: Part-whole and emergent behavior
Construct systems where local parts have incomplete predictive power and a higher-level configuration predicts a new observable. Include controls where the apparent whole effect is explained by a nuisance variable.

Measure:
- higher-level predictive lift over flat and additive-part baselines;
- false emergence rate under nuisance controls;
- minimal sufficient abstraction size;
- intervention prediction at each scale.

### E11-5: Concept revision under drift
Change one defining invariant, one context condition, or one role while retaining other structure. Compare freeze, full relearn, split, merge, and local revision policies.

Measure:
- correct version/split/merge decision;
- preservation of unaffected concepts;
- false deletion and false persistence;
- recovery after transient noise.

## 9. Leakage and identifiability controls

Mandatory controls:
- randomize and independently generate IDs, labels, serialization order, and field cardinality;
- remove hidden concept IDs, hierarchy depth, generator family, and split identity from learner views;
- query-label and hierarchy-edge canaries must leave learner payload bytes unchanged;
- evaluator truth must remain in a separate process or access-controlled evaluator;
- test symbol-renaming invariance and participant-order invariance where semantics permit;
- include metadata-only and nuisance-only attackers;
- reject duplicate IDs, malformed rows, invalid types, and inconsistent evaluator records;
- enumerate observationally equivalent concept/hierarchy hypotheses within the declared hypothesis class.

If two different concept structures make identical predictions on all available observations and interventions, report them as observationally equivalent; do not claim unique discovery.

## 10. Baselines and ablations

Required:
- flat feature model;
- k-means / hierarchical clustering where applicable;
- frequent subgraph/substructure mining;
- fixed human-supplied ontology;
- finite schema/DSL enumeration;
- MDL-only selection;
- predictive-only selection;
- invariant-only discovery;
- E10 relational analogy/operator learner;
- E09 non-gradient baselines;
- parameter/compute-matched gradient learner;
- random and deliberately misaligned structural priors.

Ablate:
- boundary search;
- counterexample feedback;
- context conditions;
- hierarchy edge typing;
- multi-parent support;
- multi-scale feedback;
- Yi-Xiang priors.

Match data, oracle/query budget, candidate evaluations, memory, and wall-clock limits.

## 11. Yi-Xiang correspondence as testable prior

Potential mappings:
- 象 / 类象: reusable structural schema and partial analogy;
- 象数: candidate discrete factorization/encoding, not a required ontology;
- 时位: context and role-conditioned membership;
- 互体: substructure extraction;
- 错综: alternative role/structure transformations;
- 卦变: state transition between concept instances;
- 阴阳: typed complement/dual hypotheses;
- 五行: signed interaction hypotheses.

Each prior is a separate experimental arm. Compare aligned, random, shuffled, and misaligned priors against no-prior. The learner must be able to discard a prior when it increases error or complexity without held-out gain.

## 12. Acceptance gates

- A0: neutral observation schema and deterministic generators.
- A1: leakage-resistant evaluator separation.
- A2: concept proposals recover predictive structural regularities beyond flat baselines.
- A3: boundaries generalize to unseen objects and contexts.
- B1: typed multi-relational hierarchy outperforms forced-tree controls on overlapping cases.
- B2: multi-scale abstraction demonstrates held-out predictive or explanatory gain beyond flat/additive controls.
- B3: counterexample-driven revisions preserve unaffected knowledge and improve drift adaptation.
- B4: joint concept/hierarchy feedback outperforms one-way/frozen controls under matched budgets.

No gate proves open-world understanding. Synthetic success remains limited to tested generators and hypothesis classes.

## 13. Stop conditions and claim discipline

Stop or narrow claims if:
- discovered concepts track IDs, ordering, or nuisance fields;
- a flat baseline matches hierarchy performance at lower cost;
- hierarchy edges do not improve held-out prediction, compression, or intervention accuracy;
- multi-scale gains disappear under nuisance controls;
- concept count is highly unstable across seeds without calibrated uncertainty;
- the system cannot abstain under observational ambiguity;
- apparent discovery is just recovery of a supplied finite ontology or DSL.

Report negative results and per-seed data. Do not use the words "autonomous understanding" or "world model discovered" based solely on cluster recovery.

## 14. Implementation sequence

1. Define observation and concept-schema serialization.
2. Implement candidate schema mining and anti-unification baselines.
3. Implement boundary counterexample search.
4. Add evaluator-isolated unknown-concept-count generator.
5. Add typed hierarchy hypergraph and edge adjudication.
6. Add multi-scale aggregation with provenance links.
7. Implement alternating concept/hierarchy learner.
8. Run leakage, identifiability, nuisance and baseline audits.
9. Only then add Yi-Xiang prior arms and cross-domain transfer tasks.

## 15. Current conclusion

E11-A/B turns "取象比类、由象见类、由类成层、由层观势" into distinct testable computational questions. The central criterion is not whether the system can cluster or draw a hierarchy, but whether it can discover compact, revisable, role- and context-sensitive abstractions that survive counterexamples and improve predictions on genuinely unseen structures.
