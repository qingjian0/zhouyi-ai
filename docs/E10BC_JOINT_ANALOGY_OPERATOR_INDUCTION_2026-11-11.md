# E10-B/C Joint Relational Analogy and Operator Induction (2026-11-11)

Status: formal research proposal and preregistration draft; no implementation, run, or performance claim.
Base: `research/e10-xiang-operator-learning-2026-11-10`.
Scope: independent E10 research branch. Does not modify E09, E02, E10-A generator/task-view branches, or main.

## 1. Research question

Can a learner jointly discover:
1. partial structural correspondences between different experience domains ("xiang"/analogy);
2. reusable executable transformations over those structures ("change operators");
3. new concepts/relations created by applying those operators;

and use prediction errors to revise both the correspondence and the operator?

The target is not surface similarity. A successful analogy must preserve selected typed, role-sensitive relations under explicit context conditions, and must predict behavior on held-out instances. A successful operator must execute on unseen structures, not merely name or memorize a training transformation.

## 2. Typed relational world model

Represent an experience graph as a typed attributed hypergraph:

`G=(V,A,H,C,	au_V,	au_A,	au_H,ho,epsilon)`

- `V`: object instances.
- `A`: typed attribute/state facts attached to objects.
- `H`: relation hyperedges.
- `C`: context/environment facts.
- `tau_V, tau_A, tau_H`: object, attribute, and relation types.
- `rho(h,i)`: role label of participant `i` in hyperedge `h`; roles are ordered/typed, not pooled as an unordered set.
- `epsilon`: evidence state for each fact/edge: SUPPORT, COUNTEREXAMPLE, UNKNOWN, or CONFLICT, plus provenance and scope.

A relation instance is:
`r(x_1^{q_1},...,x_k^{q_k} | c, t)`
where `q_i` is a role, `c` is context, and `t` is time/state. Keep instance identity, concept identity, and current state separate.

## 3. Partial relational analogy

An analogy from source `G_s` to target `G_t` is a partial typed mapping:
`M=(f_V,f_A,f_H,f_C,pi_Q)`
where `f_V` maps selected objects, `f_A` maps selected attribute types/values, `f_H` maps relation types/instances, `f_C` maps context variables, and `pi_Q` maps roles.

For a source hyperedge `h_s`, preservation is evaluated only when:
- all mapped participants exist;
- mapped participant types are compatible;
- role mapping is well-typed;
- the target relation is supported in the mapped context;
- no confirmed target counterexample contradicts the proposed preservation.

Define a weighted preservation score:
`P(M)=sum_e w_e * I[preserved(e)] / sum_e w_e`
over the *declared* source relation set, while separately reporting contradicted, unknown, and unmapped edges. Unknown is not counted as preserved.

A mapping must include a scope certificate:
- preserved relation/role constraints;
- contradicted constraints;
- unmapped structure;
- context assumptions;
- support/counterexample counts;
- calibrated confidence or ABSTAIN.

Do not collapse the mapping into a single similarity score. The learner must be allowed to return partial mapping or ABSTAIN.

## 4. Operator representation and semantics

An operator is a typed executable AST:
`O : (G, c, s) -> (G', delta, status)`
where `s` is an explicit input slot/interface, `G'` is the resulting structure, `delta` is a provenance-linked edit script, and status is SUCCESS / PARTIAL / ABSTAIN / INVALID.

Initial primitive families (as experimental language, not truth):
- SELECT / FILTER: choose typed substructures;
- COMPOSE: join compatible structures under shared variables;
- DECOMPOSE: extract substructures with preserved provenance;
- ROLE_MAP / ROLE_PERMUTE: map participant roles;
- DUALIZE: propose a typed complement/dual mapping;
- CONDITION / RELAX_CONDITION: add or remove an explicit condition;
- INVERT: reverse a declared directional relation where type rules permit;
- ABSTRACT: replace repeated concrete structure with a variable/slot;
- INSTANTIATE: apply an abstract schema to new objects;
- TRANSFER: apply a mapping/operator in a new domain;
- REVISE: make a bounded local AST edit after a counterexample.

Every operator must declare input/output types, preconditions, postconditions, affected roles, context requirements, and failure modes. An operator that silently drops violated constraints is invalid.

### Operator novelty levels

- O0: reuse a supplied primitive.
- O1: compose supplied primitives into a new program.
- O2: compress repeated programs into a reusable macro with an explicit interface.
- O3: invent a new typed primitive/semantic transformation not reducible to the supplied DSL under the tested equivalence.
- O4: revise its own representation vocabulary or type system.

Claims must name the achieved level. O1 is not open-ended operator invention.

## 5. Joint induction objective

Given evidence set D, analogy mappings M, operators O, and concept/schema inventory K, select a joint model by constrained multi-objective selection:

1. hard type/role constraints must hold;
2. confirmed counterexamples cannot be silently overwritten;
3. support must meet a predeclared minimum;
4. maximize held-out predictive utility and structural preservation;
5. minimize description length of M, O, and K;
6. minimize query and execution cost;
7. calibrate uncertainty and reward appropriate abstention.

A scalar MDL-style diagnostic may be reported:
`Score = L(M,O,K) + L(D | M,O,K) + lambda_q * QueryCost + lambda_x * ExecCost`
but it is not the sole acceptance rule. Report each component and use preregistered thresholds. Do not tune lambdas on locked test data.

## 6. Alternating joint-learning procedure

For each training episode:

1. **Discover candidate xiang:** propose object bundles, role slots, attribute invariants, and relation fragments from observations. Keep proposal provenance.
2. **Align structures:** construct a bounded set of partial mappings between candidate structures; include hard negatives with high surface similarity but incompatible role/context constraints.
3. **Propose operators:** anti-unify repeated successful mappings, compose existing ASTs, and propose bounded local edits.
4. **Generate predictions:** apply candidate mappings/operators to held-out support/query inputs without access to hidden outcomes.
5. **Select discriminative tests:** choose queries that distinguish competing mappings/operators under a shared query budget.
6. **Adjudicate evidence:** append support, counterexample, unknown, and conflict evidence; never convert UNKNOWN into SUPPORT.
7. **Revise jointly:** if failure localizes to role mapping, revise M; if to transformation steps, revise O; if context boundary, revise condition; if unlocalizable, lower confidence or ABSTAIN.
8. **Compress and retain:** merge equivalent macros only after behavioral equivalence tests; preserve immutable versions and lineage.
9. **Transfer:** evaluate the frozen candidate on new objects, new surface symbols, new compositions, and new contexts.

The update schedule must be predeclared. Compare joint alternating updates against (a) analogy-only then frozen operator, (b) operator-only with fixed mappings, and (c) one-pass pipeline. This isolates whether feedback between M and O contributes.

## 7. Core falsifiable experiments

### E10-BC-1: Role-sensitive analogy

Source and target worlds share a latent relational skeleton but have independently randomized object IDs, attribute names, surface values, relation symbols, and participant presentation order. Hard negatives preserve marginal attributes and arity while changing role assignment or context.

Primary metrics:
- exact/partial mapping recovery up to declared automorphisms;
- relation preservation precision/recall;
- false analogy acceptance on hard negatives;
- query prediction accuracy;
- selective risk versus coverage and calibration.

### E10-BC-2: Operator composition transfer

Train on a subset of primitive compositions. Test on unseen compositions and unseen objects. Include compositional generalization splits by AST subtree/composition identity, not random rows.

Primary metrics:
- exact transformation execution;
- postcondition satisfaction;
- edit-script minimality;
- transfer success and counterexample rate;
- AST size, candidate evaluations, wall time, memory.

### E10-BC-3: Context and potential boundaries

Use worlds where the same structural mapping is valid in one context and invalid in another, including context reversal and confounding context cues. The learner must discover condition boundaries and avoid promoting conditional mappings to universal rules.

Primary metrics:
- condition recovery;
- false unconditional transfer;
- boundary detection delay;
- correct ABSTAIN under ambiguous evidence.

### E10-BC-4: Joint feedback ablation

Compare:
- J0: no analogy/operator learning (nearest-neighbour baseline);
- J1: fixed mappings + operator search;
- J2: analogy search + fixed operators;
- J3: one-way analogy -> operator pipeline;
- J4: alternating joint M/O revision;
- J5: J4 + Yi-Xiang structural prior;
- J6: J4 + randomized/misaligned prior control.

All methods receive identical observations, query budgets, candidate-evaluation budgets, and compute limits. Include parameter-matched gradient/hybrid baselines separately.

### E10-BC-5: Self-revision and novelty

Hold out transformation families and AST compositions. Require the learner to propose a new macro/operator, publish its typed interface and semantics, and execute it on unseen inputs. Compare against enumerating all programs in the supplied DSL. If behavior is reducible to the DSL, classify as O1/O2, not O3.

## 8. Identifiability and ambiguity

Before scoring a mapping/operator, determine whether support evidence uniquely identifies it within the declared hypothesis class.

For each episode:
- enumerate or otherwise bound observationally equivalent hypotheses;
- if multiple mappings differ only by a valid automorphism, score equivalence classes;
- if multiple non-equivalent hypotheses remain, mark the episode ambiguous;
- permit ABSTAIN and score it against calibrated selective prediction;
- do not treat the generator's hidden mapping as uniquely inferable merely because the generator knows it.

The hypothesis class and equivalence relation must be declared before evaluation. No universal identifiability claim is made outside that class.

## 9. Leakage and benchmark integrity

Learner-facing payload must be explicit allowlist serialization. Evaluator truth, latent mapping, operator target, split family, seed, and generator provenance remain separate. The benchmark runner must not expose evaluator payload to the learner process.

Mandatory attacks:
1. query-label canary: changing hidden labels leaves learner bytes identical;
2. latent-mapping/operator canary: changing truth leaves learner bytes identical;
3. ID/order/cardinality/field-shape attacker;
4. surface-symbol renaming invariance;
5. role permutation and automorphism controls;
6. object-disjoint and structure-disjoint splits;
7. context leakage and nuisance-only attackers;
8. duplicate and malformed evaluator records fail closed.

Report both episode-local interpolation and cross-episode transfer; never merge them into one headline score.

## 10. Baselines and fair accounting

Required baselines:
- lookup and nearest-neighbour;
- fixed analogy templates;
- fixed operator library;
- finite DSL enumeration / CEGIS;
- graph and hypergraph structure matching;
- E09 NG-A through NG-E;
- random and deliberately misaligned structural priors;
- parameter/compute-matched gradient learner;
- hybrid learner.

Count generation, candidate proposal, candidate evaluation, oracle/query calls, retries, and failed executions. Report per-seed results and confidence intervals. Lock validation/test seeds before tuning.

## 11. Yi-Xiang prior treatment

Yi-Xiang ideas are candidate inductive biases, not benchmark labels:
- Xiang/class analogy -> relation-preserving partial mappings;
- Yin/Yang -> testable typed dual/complement hypotheses;
- trigram/hexagram structure -> structured state-factorization prior;
- mutual/incorrect/reversed hexagram transformations -> candidate substructure/role transformations;
- Shi/Wei -> context and role constraints;
- Wu Xing -> signed influence hypotheses, tested only in environments where causal direction can be identified.

Compare no-prior, random-prior, aligned-prior, and deliberately misaligned-prior arms. A useful prior should improve data efficiency or generalization without increasing false analogy acceptance; it must also be rejectable when misaligned.

## 12. Acceptance gates and claim discipline

- G0: type-safe data model and deterministic generator.
- G1: leakage-resistant learner/evaluator boundary.
- G2: within-domain role-sensitive analogy.
- G3: held-out object and symbol transfer.
- G4: unseen operator compositions.
- G5: context-conditional transfer with calibrated abstention.
- G6: joint feedback demonstrably outperforms one-way/frozen ablations under matched budgets.
- G7: O3/O4 novelty only if a new semantic operator/representation is demonstrated outside the supplied DSL and validated on held-out tasks.

No gate implies the next. Unit tests establish implementation correctness only. Synthetic benchmark success does not establish open-world intelligence.

## 13. Implementation sequence

1. Define typed graph and evidence schema, plus canonical serialization.
2. Implement mapping object and preservation/contradiction evaluator.
3. Add synthetic role-sensitive analogy generator and hard negatives.
4. Add support/query isolation using the E10-A task-view interface after its validation gates are met.
5. Implement fixed primitive operator AST and interpreter.
6. Add operator anti-unification and bounded composition search.
7. Add joint alternating learner and frozen/one-way controls.
8. Add Yi-Xiang prior ablations only after X0 baseline is stable.
9. Add open-vocabulary bridge only as a separately attributed experiment.

## 14. Current conclusion

The proposed contribution is a falsifiable joint learning loop: relational analogy proposes reusable structure; operator induction turns repeated correspondences into executable transformations; counterexamples revise both; held-out transfer tests whether the abstraction is real. It remains a research proposal until implemented and evaluated under the gates above.
