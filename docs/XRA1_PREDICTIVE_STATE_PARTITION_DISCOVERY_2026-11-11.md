# XRA-1: Predictive State Partition Discovery

Date: 2026-11-11
Status: research design; no empirical claim
Parent: XRA-0 representation factorization protocol

## 1. Research question

Can a learner discover how many task-relevant state classes exist, and how observations should be grouped, from predictive evidence rather than receiving the class count and partition from the developer?

This is a deeper problem than selecting binary versus ternary encoding. The learner must infer a partition of observations or histories. Only after that partition is selected should it choose a codebook and coordinate radix.

## 2. Formal distinction: encoding versus abstraction

Let X be the raw observation space. A representation partition is a map:

`P: X -> {1,...,K}`

where K is the number of semantic classes. An encoding is a separate injective map:

`C: {1,...,K} -> product_i {0,...,r_i-1}`

Changing C bijectively does not change P. Changing P can change which distinctions the learner preserves.

The target is not necessarily to recover a generator's private state labels. It is to find a task-sufficient abstraction: states may be grouped when their future task-relevant behavior is indistinguishable under the declared action and observation interface.

## 3. Predictive equivalence

For a fully observed controlled process, two states s and t are behaviorally equivalent under a declared action set A if, for every action a:

1. their immediate reward or task outcome distributions are equal (or within a declared tolerance); and
2. their transition distributions over equivalence classes are equal (or within a declared tolerance).

For a candidate partition P, define a one-step discrepancy:

`D_P(s,t) = max_a [ alpha * d_outcome(O_s^a,O_t^a) + beta * TV(P T_s^a, P T_t^a) ]`

where:
- O_s^a is the outcome distribution after action a;
- T_s^a is the next-state distribution;
- P T is the transition distribution aggregated over partition blocks;
- TV is total variation distance;
- alpha and beta are preregistered task weights.

For deterministic finite generators, distributions reduce to exact outcome and next-block equality. For stochastic generators, use confidence intervals and finite-sample corrections; do not treat a failure to detect a difference as proof of equivalence.

For partially observed systems, the objects being grouped may be histories h rather than instantaneous observations. A stronger predictive-equivalence test compares distributions of future observation/outcome sequences under a declared family of action sequences. The benchmark must state the horizon and action policy family; finite-horizon equivalence is not automatically infinite-horizon equivalence.

## 4. Approximate abstraction and uncertainty

Use three distinct decisions:

- **MERGE:** evidence supports that two blocks are predictively equivalent within epsilon and the validation budget is sufficient.
- **SPLIT:** a replicated counterexample shows a task-relevant difference between members of a block.
- **UNRESOLVED:** evidence is insufficient, tests are underpowered, or competing partitions remain plausible.

Never force a binary merge/split decision when the evidence supports abstention.

For approximate MDP-style abstractions, report separate outcome/reward discrepancy and transition discrepancy. A single scalar score may be used for selection, but its components and thresholds must remain visible.

## 5. Discovering K without leaking K

The evaluator may know the generator's latent state count for scoring. The learner must not receive:
- true K when K is meant to be discovered;
- hidden state IDs or generator family labels;
- the evaluator's partition;
- future outcomes or query labels;
- canonical symbol assignments or permutation seeds.

The learner receives only permitted observations, actions, costs, and revealed outcomes. It proposes a partition, uncertainty over partitions, or abstains.

Report:
- predicted K and partition;
- adjusted Rand index / variation of information only when evaluator labels are available and appropriate;
- predictive accuracy and calibration;
- held-out transition/outcome discrepancy;
- split/merge precision and recall;
- number of unresolved pairs;
- representation stability across seeds and symbol permutations;
- total proposal, measurement, compute, and memory costs.

Label matching is a diagnostic, not the sole objective. Two different partitions may be equally task-sufficient.

## 6. Model selection: predictive MDL with switch cost

Candidate partitions should trade predictive fit against complexity:

`Score(P) = L(D_train | P) + lambda_P * L(P) + lambda_K * K + lambda_S * Switch(P,P_prev)`

where:
- L(D_train | P) is predictive description length or held-out predictive loss;
- L(P) is the description length of the partition / decision structure;
- K penalizes unnecessary distinctions;
- Switch penalizes unstable restructuring.

This is a candidate objective, not a universal law. Compare it against:
- fixed K in {2,3,4,8};
- one flat category per observed item;
- one universal category;
- generic clustering / predictive-state baselines;
- exact finite partition enumeration on small worlds;
- Zhouyi-inspired hierarchical binary partitions;
- Taixuan-inspired ternary partitions;
- shuffled and anti-aligned prior controls.

Tune lambda values only on development data. Report sensitivity and do not use locked-test results to select thresholds.

## 7. Candidate generation and structural priors

A candidate partition can be proposed by:
- predictive feature signatures;
- residual correlation or conditional dependence;
- role-conditioned transition differences;
- hierarchical binary splits;
- ternary branching;
- sparse non-contiguous relation motifs;
- generic clustering or program synthesis.

Classical priors are proposals, not constraints:
- Yixiang may propose complementary binary splits and hierarchical compositions.
- Taixuan may propose a three-way split when a third predictive regime is supported.
- YF-inspired dynamic observation may choose the next measurement that distinguishes competing partitions and may trigger revalidation after context change.

The candidate set must include a no-prior baseline and generic alternatives. A prior that cannot be rejected is not being scientifically tested.

## 8. Evidence lifecycle

Every partition proposal is versioned and evidence-linked:

`OBSERVE -> PROPOSE_PARTITION -> PREDICT -> COMMIT -> REVEAL -> TEST_EQUIVALENCE -> MERGE | SPLIT | UNRESOLVED -> VERSION`

Rules:
- proposal evidence and challenge evidence must be separately typed;
- no candidate is validated on the same observations that created it;
- locked-test evidence cannot be used for routine candidate creation;
- a split creates child blocks with explicit parent lineage;
- a merge records all parent blocks and the evidence justifying the quotient;
- an unresolved decision preserves the prior version and its uncertainty;
- after a detected context change, mark affected partitions REVALIDATION_PENDING rather than silently retaining validity;
- codebook recoding and semantic partition revision are different event types.

Integrate with the existing E10 concept split/merge and E12 lifecycle contracts through adapters. Do not create a competing lifecycle enum or event store.

## 9. Active observation for partition discovery

When multiple partitions remain plausible, choose an action that distinguishes them. For candidate action a:

`Value(a) = E[H(P | D) - H(P | D, outcome(a))] / cost(a)`

Compare:
- passive observation;
- seeded random action;
- fixed-order action;
- EIG-per-cost;
- YF-adaptive context/time-sensitive policy;
- exact oracle on tiny finite tasks.

A one-step EIG policy is myopic. Add two-step lookahead only as a separately budgeted baseline. Missing outcomes are censored evidence and must not update a posterior unless the declared missingness model explicitly says otherwise.

## 10. Benchmark progression

### XRA-P1: deterministic finite worlds
- finite state and action sets;
- exact transition/outcome tables;
- known evaluator equivalence classes;
- exact partition enumeration for small N;
- no noise and complete observations.

Purpose: verify formal definitions, merge/split logic, and identifiability.

### XRA-P2: stochastic and noisy worlds
- outcome noise, transition noise, missingness;
- confidence-aware MERGE / SPLIT / UNRESOLVED;
- calibrated uncertainty and repeated evidence.

Purpose: test whether the system avoids false merges and false splits.

### XRA-P3: changing worlds
- context-dependent transition relations;
- abrupt and gradual drift;
- stable nuisance variation;
- intervention-dependent mechanisms.

Purpose: test YF-inspired observation and revalidation policies.

### XRA-P4: compositional cross-world transfer
- held-out object identities;
- held-out relation families;
- role permutations;
- non-contiguous sparse relations;
- new compositions of known primitives.

Purpose: test whether discovered partitions preserve reusable structure.

## 11. Required falsification controls

1. Randomly permute observation symbols while preserving semantics.
2. Shuffle prior-to-symbol assignments.
3. Use anti-aligned priors whose proposed splits contradict the generator.
4. Add irrelevant nuisance features and test whether K inflates.
5. Add a predictive third regime and test whether a forced binary model underfits.
6. Make two latent states observationally equivalent under all allowed actions; the learner must not claim to distinguish them.
7. Remove the only discriminating action; active selection must report non-identifiability.
8. Introduce context drift; stale partitions must be challenged and revalidated.
9. Compare against exact enumeration on tiny worlds.
10. Match proposal and measurement budgets across all prior families.

## 12. Staged implementation

### XRA-1a — deterministic evaluator oracle (implemented; execution pending)

Added:
- `prototype/xra_partition.py`: exact partition refinement for complete finite deterministic state/action tables. It groups states only when all declared actions produce equal immediate outcomes and transition into the same final partition blocks.
- `tests/test_xra_partition.py`: equivalent-state merging, backward propagation of future distinctions, action discrimination, deterministic block ordering, incomplete-table rejection, invalid-target rejection, and unhashable-outcome rejection.

The oracle is evaluator-side only. It must not be passed into learner-visible task payloads. It is an exact finite deterministic bisimulation-style partitioner, not an approximate stochastic abstraction learner.

### Remaining gates

- XRA-1b: add a task manifest and independent exact partition enumerator / cross-check for tiny worlds.
- XRA-1c: implement MERGE / SPLIT / UNRESOLVED with held-out challenge evidence.
- XRA-1d: connect E12-A8 action selection to competing partition hypotheses.
- XRA-1e: add binary, ternary, generic, shuffled, and anti-aligned proposal families.
- XRA-1f: add context drift and revalidation using the existing lifecycle adapter.

The adaptive K selector remains blocked until the evaluator oracle, leakage boundary, and exact small-world cross-check are validated.

## 13. Current scientific claim

At this stage, the project has a testable hypothesis that useful state cardinality and factorization can be discovered from predictive equivalence and evidence-driven partition revision. It has not yet demonstrated that this approach outperforms fixed encodings, clustering, or existing symbolic/neural baselines.
