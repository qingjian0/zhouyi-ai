# E12-A3 — Yijing-Inspired Priors for Active Measurement (Preregistration)

Status: design-only preregistration. No implementation, benchmark run, or empirical benefit is claimed.
Dependency: E12-A2-M generic passive measurement selector. This protocol must not be implemented as a performance experiment until the exact A2-M implementation has passing CI and its generic benchmark protocol is frozen.
Branch: `research/e12a3-yixiang-active-prior-prereg-2026-11-11`, stacked on the E12-A2-M selector prototype.

## 1. Research question

Given the same finite candidate hypotheses, permitted measurements, observation model, and acquisition budget, do Yijing-inspired structural priors improve active measurement decisions over neutral and capacity-matched generic alternatives?

The target claim is narrow: a prior may improve *measurement efficiency on task families whose generating structure is compatible with that prior*. This experiment cannot establish that traditional correspondences are universally true, that the system has general intelligence, or that it has discovered causal structure.

## 2. Dependency gate

Before A3 implementation begins, A2-M must satisfy all of the following on its exact head commit:

1. CI passes the full repository test suite.
2. The selector matches an exact enumerator on tiny finite cases.
3. Random, fixed-order, maximum-disagreement, raw-IG, and cost-normalized-IG baselines run under identical budgets.
4. Identifiable and observationally equivalent episodes are both represented.
5. The learner receives no evaluator truth or locked Test data.
6. Multi-seed episode-level results, failures, abstentions, and costs are recorded.

If any gate fails, A3 remains a protocol only. A3 must not be used to conceal an A2 defect.

## 3. Separate three possible sources of prior benefit

Do not combine these mechanisms into one opaque "Yijing mode". Evaluate them as separate factors:

### P — hypothesis prior

Changes only the initial weights over an already fixed candidate set. Candidate identities, likelihood tables, and action costs remain byte-identical.

Arms:
- P0: uniform prior (primary neutral baseline).
- P1: generic data-derived prior, estimated only from permitted Train episodes.
- P2: fixed Yijing-structured prior, with its mapping and smoothing frozen before evaluation.
- P3: capacity-matched shuffled Yijing mapping.
- P4: deliberately anti-aligned prior as a stress test.

### L — likelihood / partition prior

Changes only the representation used to estimate or encode measurement-outcome likelihoods. It must not add observations or reveal extra task metadata.

Arms:
- L0: raw observed variables with an unstructured estimator.
- L1: generic learned factorization with matched parameter count.
- L2: Yin/Yang complementary partition.
- L3: four-state / two-factor partition.
- L4: trigram-factorized 3-bit partition.
- L5: six-bit upper/lower trigram product representation.
- L6: shuffled mapping with the same dimensions and parameter budget.

### T — transition/action prior (deferred)

Changes only the proposal distribution over permitted measurement actions or state transitions. This is deferred until P and L have been evaluated independently. A passive measurement must never be described as an intervention.

The first A3 implementation should test P only. L is a later extension; T is out of scope for A3-P.

## 4. Formal setup

For episode e, let H be the fixed learner-visible candidate set, A the fixed permitted measurement set, B the acquisition budget, and o the environment-revealed outcome.

The learner receives:
- candidate IDs and their observable descriptions;
- the prior weights w(h), supplied by the selected prior arm;
- per-action likelihoods P(o | h,a), supplied by the frozen benchmark for A3-P;
- action costs c(a), and remaining budget B.

For each action:

```
P(o | a) = sum_h w(h) P(o | h,a)
IG(a) = H(w) - sum_o P(o | a) H(w(h | a,o))
U(a) = IG(a) / (c(a) + epsilon)
```

The policy selects the affordable action with maximum U(a), using the A2-M deterministic tie-break. After the environment reveals an outcome, update weights by Bayes' rule. No candidate may be silently added after an observation.

Important: changing w(h) changes both the expected information gain and the posterior. Therefore evaluate not only expected IG, but also *realized* entropy reduction, identification error, calibration, and regret under the evaluator's actual hidden world.

## 5. Benchmark families

Use evaluator-private generators and freeze their version/hash before locked Test.

### F1 — aligned complementary structure

Two or more candidate mechanisms differ along a genuine complementary binary distinction. The environment's measurement outcomes preserve that distinction. Yin/Yang prior may be relevant, but the neutral prior remains a valid control.

### F2 — aligned hierarchical / factorized structure

Candidate mechanisms differ in combinations of two- and three-bit factors. Individual factors occur in Train, while selected combinations are withheld for evaluation. Test whether hierarchical/factorized priors help select measurements that distinguish unseen combinations.

### F3 — aligned sparse state transition

Candidate mechanisms predict transitions generated by sparse bit changes. Deferred from A3-P; reserved for a later transition-prior study.

### F4 — misaligned / permuted structure

The hidden generator uses a random permutation or unrelated partition. The traditional mapping should not be expected to help. This is a required diagnostic family, not an optional robustness appendix.

### F5 — observational equivalence

All permitted measurements have identical likelihoods under competing candidates. Every arm must preserve ambiguity and return NO_DISCRIMINATING_ACTION. A prior must not manufacture information that the environment cannot reveal.

### F6 — misleading prior / distribution shift

Train suggests a structured mapping, while Gate/Test changes the mapping or reverses the relation. Measure whether the learner detects and rejects a harmful prior instead of becoming confidently wrong.

## 6. Controls and fairness

For A3-P, compare at minimum:
1. Uniform prior.
2. Generic Train-estimated prior.
3. Yijing-structured prior.
4. Shuffled Yijing prior.
5. Anti-aligned prior (diagnostic stress test).
6. Exact optimal policy under the true evaluator distribution (oracle upper bound only; never a learner baseline).

Keep candidate set, candidate descriptions, likelihood tables, action set, costs, observation noise, budget, and episode seeds identical across prior arms.

For later A3-L, additionally match trainable parameter count, feature access, optimization steps, tuning trials, and inference operations. A representation arm may transform the same raw input; it may not receive extra information.

Random mapping seeds are nested within world seeds. They are not independent world episodes and must not inflate the effective sample size.

## 7. Split isolation and leakage controls

- Split by canonicalized hidden mechanism family and structure, not random rows alone.
- Keep Train, Gate, and Locked Test mechanism families disjoint.
- All candidate and action descriptions exposed to the learner must be identical across prior arms.
- Evaluator truth, generator seed, family label, and locked Test outcomes stay outside the learner payload.
- Permuting evaluator truth while holding the learner payload fixed must leave the learner's action and posterior unchanged.
- Reordering candidates, actions, or mapping tables must not change canonical results.
- File names, IDs, missingness, ordering, and serialization length must not encode family or split.
- The evaluator must verify that F5 truly has zero available information and that F1/F2 contain at least one discriminating permitted measurement.

## 8. Outcomes and metrics

Primary endpoint for A3-P:
- **Cumulative realized entropy reduction per unit acquisition cost** at the fixed episode budget, averaged at the independent world-seed block level.

Key secondary endpoints:
- Correct identification rate on identifiable episodes.
- Ambiguity-retention rate on F5.
- False-identification and confidently-wrong rates.
- Calibration (Brier score / log loss where probability targets are well-defined).
- Number of measurements to identification.
- Total acquisition cost and remaining budget.
- Regret against the exact optimal policy on tiny candidate spaces.
- Performance on F4 and F6 relative to the uniform baseline.

Do not use raw expected IG alone as the success metric: a misspecified prior can inflate expected IG while reducing realized information about the actual world.

## 9. Statistical plan and decision rule

- Use paired world-seed blocks across all prior arms.
- Determine sample size by development-set power / precision analysis; 30 independent world-seed blocks is only a provisional floor, not a power justification.
- Report paired effect sizes and 95% confidence intervals using world-block resampling.
- Pre-register one primary contrast: Yijing prior vs uniform prior on F1+F2, with F4/F5/F6 as mandatory guardrails.
- Apply Holm correction to the predeclared secondary contrasts.
- Set the minimum practically relevant effect before locked Test; do not select it after observing results.
- Report every invalid episode, abstention, timeout, and failed run.

A3-P can support a narrow positive result only if:
1. the primary contrast exceeds the predeclared practical-effect threshold with its confidence interval excluding zero;
2. ambiguity retention on F5 is not worse than the predeclared tolerance;
3. false-identification / calibration guardrails do not materially deteriorate;
4. the shuffled mapping does not reproduce the same gain;
5. the F4/F6 harm limits are respected.

If gains occur only on F1/F2, report a task-conditional inductive bias, not a general advantage. If shuffled mappings perform similarly, attribute gains to generic partitioning or capacity, not the traditional mapping. If no arm beats uniform robustly, retain the neutral prior.

## 10. Required falsification tests

- Yijing prior loses to uniform on aligned families.
- Shuffled mapping matches the claimed gain.
- Anti-aligned prior causes confident errors that the rejection mechanism cannot detect.
- F5 causes a prior-driven unique answer despite zero available information.
- Gains disappear on held-out mechanism families.
- Benefits vanish after matching candidate capacity, compute, or tuning budget.
- Results depend on evaluator truth, seed, ID, ordering, or split leakage.
- Expected IG rises while realized entropy reduction or accuracy falls.

Any one of these can invalidate the broad claim. A prior that cannot be rejected is not acceptable.

## 11. Implementation sequence

A3-P is documentation-first. After the A2 dependency gate:
1. Freeze a tiny finite benchmark generator with F1, F4, F5, and F6.
2. Implement prior arms as pure functions that only return normalized weights over the same candidate IDs.
3. Add truth-mutation, payload-invariance, permutation, and zero-information tests.
4. Run exact enumeration on tiny episodes.
5. Add multi-seed evaluation and locked Test only after Gate review.
6. Implement A3-L only if A3-P shows a reproducible, calibrated benefit.
7. Keep transition priors and Five-Phase relations in separate future protocols.

## 12. Claim boundary

This protocol tests whether a specified symbolic prior improves finite-hypothesis passive measurement selection under controlled synthetic conditions. It does not test divination, metaphysical claims, general intelligence, open-world primitive discovery, causal intervention, or superiority to Transformer models.

A negative result is a valid outcome. The architecture must be able to discard a traditional prior when evidence does not support it.
