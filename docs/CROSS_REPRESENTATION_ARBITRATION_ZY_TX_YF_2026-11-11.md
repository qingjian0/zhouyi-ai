# Cross-Representation Arbitration: Zhouyi × Taixuan × Yinfu (2026-11-11)

Status: research protocol / architecture proposal. No empirical advantage is claimed.
Parent: `research/cpg-ei-cross-track-synthesis-2026-11-11`.
Isolation: this track must not modify `main`, and must not merge the three classical-theory tracks into one undifferentiated prior.

## 0. Research question

Can a learner select, combine, or abstain among different state representations and observation policies according to task evidence, rather than committing globally to binary, ternary, or a fixed symbolic scheme?

The project currently has three distinct research resources:

- **Zhouyi / Yixiang:** binary state and structured transformation hypotheses (yin-yang, line position, trigram/hexagram composition and change).
- **Taixuan / TX:** variable-cardinality state representations, especially a ternary alphabet and reversible codebooks.
- **Yinfu / YF:** dynamic observation, context-sensitive relation hypotheses, and evidence-governed update policies.

These are not three interchangeable encodings. In particular, Yinfu-inspired dynamic observation is a policy/mechanism family, not simply a third symbol alphabet. The experiment must preserve this distinction.

## 1. Hypotheses (all falsifiable)

- **H1 — Task-dependent cardinality:** the best state cardinality depends on the latent task family and available evidence; no fixed K is uniformly best.
- **H2 — Adaptive representation value:** a selector trained only on development episodes can outperform the best fixed representation on a preregistered mixture of task families under matched parameter and compute budgets.
- **H3 — Structural-prior value:** Zhouyi-inspired structural transforms provide benefit only on task families whose generative invariants match those transforms; any benefit must survive symbol permutation and capacity-matched controls.
- **H4 — Dynamic-observation value:** Yinfu-inspired observation policies improve information gained per unit cost only when observation actions have meaningful, measurable costs and the environment contains unresolved ambiguity or changing relations.
- **H5 — Complementarity:** combining representation selection with dynamic observation can produce an interaction benefit beyond the sum of their isolated effects. This is a separate hypothesis and must not be inferred from either main effect.

Null hypotheses include: fixed one-hot/learned representations match or exceed adaptive selection; observed gains disappear under symbol permutation or capacity matching; dynamic observation is no better than random/fixed-order measurement; or any apparent combination gain is explained by additional compute.

## 2. Factorization: do not confound representation, prior, and policy

Treat the system as three orthogonal experimental axes.

### Axis A — State representation

- BINARY
- TERNARY
- ONE_HOT
- HYBRID
- LEARNED
- PERMUTED control
- ADAPTIVE selector (chooses among the above using development-only evidence)

Representation cardinality and codebook geometry must be explicit. A ternary code is a modern computational representation choice, not a historical claim about the numeric values or semantic interpretation of Taixuan symbols.

### Axis B — Structural prior / transform family

- NONE: no Zhouyi-specific structural bias.
- ZY_BINARY: preregistered yin-yang / line-composition transforms.
- TX_TERNARY: preregistered ternary composition hypotheses.
- GENERIC_COMPOSITION: capacity-matched non-classical structural control.
- SHUFFLED_PRIOR: same prior complexity with independently permuted symbol/transform identities.

Do not encode YF as a structural prior on this axis. Its observation policy belongs to Axis C.

### Axis C — Observation and update policy

- PASSIVE: consume the supplied observation set.
- RANDOM: seeded random query/action selection.
- FIXED_ORDER: deterministic measurement order.
- EIG_COST: expected-information-gain divided by declared measurement cost.
- YF_ADAPTIVE: preregistered context/condition-sensitive observation policy.
- ORACLE: evaluator-only upper bound on tiny finite tasks; never learner-visible.

The primary design is a factorial comparison, not a single bundled “classical AI” condition. Report main effects and interactions separately.

## 3. Benchmark suite

Use separate task families so a representation cannot win merely because the generator was designed around it.

### B1 — Finite algebraic relation episodes

Extend TX-02A's cross-episode hidden-rule protocol. Vary K=2,3,4,5, include canonical and episode-permuted symbols, affine and preregistered non-affine rule families, and multiple support sizes. Keep episode seeds and rule families disjoint across Train / Validation / Locked-Test.

Before training, run exact identifiability analysis on tractable K. Report the posterior ambiguity and Bayes-optimal query accuracy under the declared finite hypothesis family. Never score an unidentifiable query as if its answer were inferable from support.

### B2 — Structured composition and non-contiguous relations

Use latent generators that create compositional rules before rendering observations. Include contiguous and non-contiguous structures (for example A+B+C+E while D is irrelevant), role permutations, nuisance features, XOR/parity, modular controls, and rule-family OOD. Keep source-instance/object provenance outside learner-visible data.

The generator must not expose hidden relation IDs, target labels, source group IDs, or query objects through support metadata.

### B3 — Dynamic observation and relation change

Create episodes in which multiple candidate mechanisms remain observationally equivalent until a particular measurement or intervention is chosen. Include:
- passive observation only;
- noisy and missing observations;
- action-dependent measurement cost;
- context switch and relation drift;
- transient noise versus persistent change;
- interventions whose outcomes distinguish correlation from mechanism.

YF_ADAPTIVE must be specified as an executable policy before evaluation. It cannot inspect hidden mechanism labels or future observations. Intervention outcomes are not automatically causal evidence unless the generator defines the intervention semantics and the action is actually executed.

### B4 — Cross-world transfer

Train on a subset of latent world families and test on held-out generator families, symbol permutations, object pools, and context combinations. Separate:
- same-world query generalization;
- unseen rule instances;
- unseen rule families;
- unseen object identities;
- unseen world mechanisms.

Do not collapse these into one OOD score.

## 4. Learner contract

All conditions must implement a shared interface:

```text
fit(train_episodes, validation_episodes, budget, seed)
propose_representation(observation, context)
encode(observation, representation_id)
propose_candidates(encoded_episode, budget)
select_observation(candidate_set, action_set, cost_model, history)
predict(query)
abstain(reason)
revise(revealed_evidence)
state_dict()
metadata()
```

The interface is a protocol target, not a claim that every existing branch already implements it. Existing TX and YF prototypes should be wrapped with thin adapters; do not rewrite their internals merely to satisfy naming consistency.

Every proposal and prediction must carry:
- immutable candidate / prediction ID;
- representation ID and codebook version;
- prior/transform family and version;
- proposer and observation-policy IDs;
- source observation IDs and evidence lineage;
- train/gate/test role;
- uncertainty, identifiability status, abstention reason;
- proposal, measurement, validation, and inference cost;
- grammar, generator, learner, and random-seed metadata.

## 5. Evidence and leakage boundaries

Use a strict event sequence:

```text
OBSERVE -> PROPOSE -> PREDICT -> COMMIT
        -> (optional) QUERY / INTERVENE
        -> REVEAL -> APPEND -> REVISE
```

- Query targets and evaluator truth are never serialized into learner-visible episodes.
- Candidate generation and representation selection may use Train and designated Gate-Dev only.
- Gate-Final is reserved for the frozen candidate/selector decision.
- Locked-Test is opened once by the evaluator after all code, thresholds, and hypotheses are frozen.
- Missing observations append a missingness event but do not mutate posterior or structure state unless the declared model explicitly treats missingness as informative.
- A representation switch must create a versioned state transition; do not silently reinterpret old evidence under a new codebook.
- Record all rejected candidates and abstentions to prevent survivorship-only reporting.

The shared evidence ledger is the preferred integration target. This document does not authorize a competing event store or a second lifecycle enum. Before code integration, pin exact dependency SHAs and run adapter conformance tests against the shared protocol.

## 6. Baselines and fairness

At minimum compare:

1. Uniform / majority predictor.
2. Fixed BINARY, TERNARY, ONE_HOT, HYBRID, LEARNED.
3. PERMUTED representation and SHUFFLED_PRIOR controls.
4. Best fixed representation selected on Validation (not Test).
5. ADAPTIVE representation selector.
6. PASSIVE, RANDOM, FIXED_ORDER, EIG_COST and YF_ADAPTIVE observation policies.
7. Generic composition prior with matched description length.
8. Tiny exact-hypothesis / exact-action oracle where enumeration is tractable.

Report both parameter-matched and compute-matched comparisons. Include training updates, proposal count, candidate evaluations, action count, wall time, peak memory, and inference latency. An adaptive method must pay for selector training and selection-time computation.

Do not use one global average as the primary result. Stratify by task family, K, canonical/permuted condition, support size, identifiability, noise, cost regime, and OOD split.

## 7. Metrics

- Query accuracy and episode exact match.
- Identifiable-query accuracy and all-query accuracy.
- Exact latent-structure recovery, where the generator makes it identifiable.
- Posterior ambiguity and Bayes-optimal accuracy.
- Calibration, error confidence, abstention coverage, and selective risk.
- Observation utility: information gain, predictive improvement, and structural identification per unit cost.
- Representation switch frequency, regret against best fixed representation, and switch stability.
- Transfer by OOD level and world family.
- Structure lifecycle precision/recall and time-to-correct-revision.
- Total compute and memory costs.

A model that predicts correctly with a different but observationally equivalent structure must be credited for prediction but not for exact structural recovery.

## 8. Preregistered decision rules

- H1 is supported only if the best fixed representation differs across task families under matched budgets, with uncertainty intervals and replication across seeds.
- H2 is supported only if ADAPTIVE beats the Validation-selected best fixed representation on Locked-Test, not merely a randomly chosen fixed baseline.
- H3 is supported only if the corresponding classical prior beats GENERIC_COMPOSITION and SHUFFLED_PRIOR controls on its preregistered task family, while not being assumed to win elsewhere.
- H4 is supported only if YF_ADAPTIVE beats EIG_COST, RANDOM, and FIXED_ORDER on the preregistered dynamic tasks at matched action cost.
- H5 is supported only by a preregistered interaction test in the factorial design, with multiple-seed confidence intervals and compute accounting.

If a claim fails, preserve the negative result and narrow the claim. Do not retune the prior, selector, or task generator after inspecting Locked-Test.

## 9. Staged implementation plan

- **XRA-0 — Protocol freeze:** finalize task-family manifests, learner-visible schemas, seed splits, exact-identifiability checks, and metrics.
- **XRA-1 — Adapters:** wrap TX-02 and YF prototypes without changing their semantics; add shared-protocol conformance tests.
- **XRA-2 — Fixed representation baselines:** implement uniform-capacity baselines and validate leakage boundaries.
- **XRA-3 — Adaptive selector:** train a small development-only selector; include DEFER / fallback and report selector overhead.
- **XRA-4 — Observation policy comparison:** connect passive, random, fixed, EIG-cost and YF-adaptive policies to E12-A8's prequential multi-world runner.
- **XRA-5 — Factorial evaluation:** run frozen multi-seed Gate-Final and Locked-Test; publish all negative and positive results.

No stage should be declared complete solely because unit tests pass. Unit tests establish implementation invariants; empirical claims require the locked benchmark protocol.

## 10. Current decision

The next implementation should begin with **XRA-0 and XRA-1 only**. Do not train an adaptive selector until the task families, exact identifiability, learner-visible schema, and cost accounting are frozen. Do not merge this proposal into `main` or claim that Zhouyi, Taixuan, or Yinfu has a demonstrated advantage.

This protocol is intended to turn the three research traditions into separable, testable computational hypotheses while allowing the eventual system to learn when none of them is useful.
