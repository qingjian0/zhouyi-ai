# E12-A3 — Compositional Primitive Induction

Status: research protocol, first implementation not yet claimed. This stage builds on the finite typed-predicate proposal in E12-A1 and the active measurement selector in E12-A2-M.

## 1. Research question

Can a learner discover reusable higher-order concepts by composing previously induced primitives, including sparse non-contiguous combinations, without receiving the target composition or evaluator truth?

The motivating requirement is not merely to enumerate every subset. The learner must propose compact, typed, evidence-supported compositions, evaluate competing structures in parallel under a fixed budget, and retain ambiguity when evidence is insufficient.

## 2. Distinguish three levels

- Primitive: a typed predicate grounded in observed features (E12-A1).
- Composition: a structured expression combining primitive outputs, such as AND, OR, NOT, XOR, ordered role binding, or a bounded relation operator.
- Concept: a reusable composition with a stable interface, evidence record, scope, and version history.

A composition is not automatically a new primitive. Promote it to a reusable concept only when it passes independent validation and demonstrates utility beyond its constituents.

## 3. Sparse composition representation

Represent an expression as a typed directed acyclic graph (DAG), not as a mandatory left-to-right chain.

Each node has:
- stable node ID;
- operator and operator version;
- input role names and expected types;
- child references;
- provenance to source primitives and evidence;
- complexity cost;
- scope and validity conditions.

A candidate may select A, B, C, E while omitting D. The omitted element is not treated as a null placeholder and does not imply that D is false. This is sparse selection over a declared candidate universe.

Initial grammar:
- unary: NOT(p)
- binary: AND(p, q), OR(p, q), XOR(p, q)
- bounded n-ary: ALL_OF({p_i}), ANY_OF({p_i})
- role binding: REL(role_1=p, role_2=q) only when the task schema explicitly defines typed roles and a measurable relation.

Do not add unrestricted recursion, arbitrary code execution, or free-form symbolic operators in the first baseline.

## 4. Candidate generation

Inputs:
- versioned A1 primitives and their types;
- learner-visible Train examples;
- declared composition grammar;
- maximum depth, node count, and candidate-evaluation budget;
- immutable provenance and evidence IDs.

Proposal process:
1. Canonicalize and deduplicate primitive nodes.
2. Generate type-valid one-step compositions.
3. Generate sparse subsets up to a preregistered arity limit.
4. Canonicalize commutative operators so AND(A,B) and AND(B,A) share one identity.
5. Apply safe algebraic simplifications (e.g. AND(p,p)=p) before scoring.
6. Keep structurally distinct candidates separate even when they agree on current Train data.
7. Enforce candidate and compute budgets; on exhaustion, abstain rather than silently truncate a biased search.

The first implementation should use a small grammar and bounded arity (2–4), with maximum depth 2. Larger grammar expansions require separate experiments.

## 5. Parallel evaluation and evidence split

All candidates are evaluated against the same frozen evidence snapshot. Candidate scoring must not mutate shared state or leak results between candidates.

- Train: candidate proposal and fitting only.
- Gate: independent candidate selection and ambiguity assessment.
- Test: locked until the grammar, scoring rule, thresholds, and selected candidate are frozen.

A candidate that is uniquely selected is only identifiable within the declared grammar and observed evidence. It is not globally proven to be the only possible concept.

Statuses:
- IDENTIFIABLE: exactly one candidate survives the preregistered Gate criteria.
- AMBIGUOUS: multiple candidates remain consistent.
- INCONSISTENT: no candidate remains consistent.
- BUDGET_EXHAUSTED: the full declared candidate space could not be evaluated within budget.
- INVALID_GRAMMAR: malformed or ill-typed expression specification.

## 6. Scoring and selection

Do not reward complexity merely because it fits more examples. Use a declared objective such as:

score(c) = evidence_fit(c) - lambda * complexity(c)

The value of lambda and all thresholds must be fixed before Gate evaluation. Report fit and complexity separately, not only a composite score.

Candidate selection must also compare against:
- best individual primitive;
- fixed handcrafted compositions;
- random compositions;
- exhaustive search on tiny instances;
- a simple decision-tree or Boolean-rule learner under matched candidate/compute budget.

A more complex composition is useful only if it provides reproducible held-out gain, improved compositional generalization, or a measurable efficiency advantage.

## 7. Required benchmark families

A. Sparse skip-composition: target depends on A,C,E but not B,D; learner sees all five primitive channels.

B. Non-contiguous interaction: target depends on A AND E, with distractors B,C,D.

C. Alternative structure: target is (A AND C) OR (B AND E).

D. Redundant feature: two primitives encode the same signal; learner should avoid claiming both are necessary.

E. Correlated distractor: a distractor correlates with the target in Train but fails in Gate/Test.

F. Unidentifiable pair: two distinct compositions are observationally equivalent under all permitted examples; learner must remain AMBIGUOUS.

G. Distribution shift: primitive marginals or correlations change between Train and Test while the target composition remains stable.

H. Noisy primitive: one or more A1 predicates have controlled error rates; composition must propagate uncertainty rather than treating every primitive output as certain.

## 8. Metrics

- candidate recall: whether the target structure is proposed;
- exact structure recovery, modulo canonical equivalence;
- semantic agreement on held-out examples;
- false concept promotion rate;
- ambiguity calibration and abstention coverage;
- candidate evaluations and wall-clock/compute cost;
- generalization under sparse, correlated, and shifted inputs;
- improvement over best constituent primitive;
- robustness to primitive permutation and irrelevant distractors.

Report episode-level confidence intervals across independent world seeds. Do not count multiple examples from one generated world as independent worlds.

## 9. Falsification criteria

The composition mechanism fails its intended claim if:
- it only succeeds when the target expression is included in the proposal grammar by a hand-coded special case;
- sparse skip-compositions are not recovered better than matched random or fixed baselines;
- performance collapses when irrelevant primitives are added;
- it promotes unstable Train correlations as reusable concepts;
- it claims uniqueness on deliberately unidentifiable tasks;
- gains disappear under held-out composition families;
- candidate search cost grows so rapidly that the measured advantage disappears under equal compute budgets.

## 10. Relationship to Yijing-inspired structure

Only after the generic sparse composition baseline is stable should symbolic priors be introduced.

Possible experimental priors:
- Yin/Yang: complementary binary feature partition;
- Four Images: two-bit hierarchical partition;
- Eight Trigrams: three-factor state encoding;
- Hexagram: six-factor state encoding;
- Five Phases: typed directed relation templates such as generation/control.

These are candidate inductive biases, not ground truth. Compare each against capacity-matched generic partitions, random permutations, and shuffled symbolic assignments. The learner must be able to reject a symbolic prior when evidence contradicts it.

Do not assume that an ancient classification system is a modern Boolean algebra, neural architecture, or causal model. The experiment asks whether a particular representation helps a defined learning task.

## 11. First implementation plan

A3-M0 should be a deterministic finite baseline:
- typed primitive inputs;
- immutable expression DAG;
- bounded grammar and sparse subset generation;
- canonicalization and deduplication;
- candidate budget with explicit abstention;
- Train/Gate separation;
- exact tiny-world oracle for tests;
- no neural network, no LLM judge, no Yijing prior, and no intervention.

Minimum tests:
1. A,C,E target is discoverable while B,D are irrelevant.
2. Candidate order and input primitive order do not change canonical output.
3. Commutative expressions canonicalize identically.
4. Ill-typed expressions are rejected.
5. Duplicate and tautological expressions simplify safely.
6. Budget exhaustion is explicit and does not return a biased winner.
7. An unidentifiable task returns AMBIGUOUS.
8. Correlated Train distractor is rejected by independent Gate evidence.
9. Adding irrelevant primitives does not change the semantic target.
10. Locked Test/evaluator truth is absent from the learner API.

## 12. Next gate

Do not integrate A3 into a neural or language model until:
- the unit tests pass;
- multi-seed synthetic evaluation is reproducible;
- random, fixed, exhaustive-tiny and decision-tree baselines are reported;
- compute budgets are matched;
- the ambiguity and leakage controls pass.

A successful symbolic prototype establishes only that the finite composition search works on its declared grammar. It does not establish general intelligence, novel representation learning, or superiority over Transformer models.
