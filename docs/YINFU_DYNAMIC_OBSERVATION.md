# Yinfu-inspired Dynamic Observation — YF-01

Status: experimental design and deterministic prototype. No performance gain has been established.

## 1. Scope and textual caution

This experiment uses the received text of the Huangdi Yinfu Jing as a source of research motifs, not as an empirical scientific theory. Authorship, dating, textual variants, and commentarial interpretations are disputed. A phrase can have materially different readings across commentaries.

Only two narrow, operational hypotheses are tested:

- Timing sensitivity, inspired by “食其时，动其机”: observation value may depend on a suitable temporal/contextual window.
- Complementary sensing, inspired by “瞽者善听，聋者善视”: a less-used observation channel may provide complementary evidence.

No supernatural causation, deterministic fate, or fixed mapping from classical symbols to reality is encoded.

## 2. Competing interpretations remain explicit

“天有五贼” has multiple commentarial readings. Examples include:
- 五行 / five phases, an influential explanatory tradition;
- 命、物、时、功、神, a distinct interpretation preserved in the Zhang Guo commentary tradition.

These readings must not be silently collapsed. Future experiments should compare each against: no symbolic prior, capacity-matched random prior, permuted symbolic prior, and alternative commentarial interpretation.

“三盗” is treated as a reciprocal system–environment–agent interaction motif, not literal theft or an established conservation law.

## 3. Prototype

Implementation: prototype/yinfu_active_observation.py
Tests: tests/test_yinfu_active_observation.py

For each permitted action a, compute expected information gain:

IG(a) = H(H) - sum_o P(o|a) H(H|o,a)

Then apply a transparent policy prior:

U(a) = IG(a) * T(a) * (1 + lambda * N(channel_a)) / Cost(a)

T(a) in [0,1] is externally supplied temporal/context fit.
N(channel) = 1 / (1 + prior observation count for that channel).
lambda >= 0 controls the diversity prior.
Cost is positive; actions outside the budget are excluded.

The environment supplies timing fit. This prototype does not learn a calendar, infer causality, or determine what the “right time” means.

## 4. Relation to E12

This is a separate experimental extension of E12-A2-M. The original information-gain-per-cost selector remains the control baseline and is not replaced.

Comparison arms:
- A: E12-A2-M information gain / cost;
- B: A + timing fit only;
- C: A + channel novelty only;
- D: A + both;
- E: random eligible action;
- F: capacity-matched generic context/channel priors.

## 5. Falsifiable predictions

1. Timing-aware selection should improve sample efficiency only when the environment contains genuine time-window structure.
2. Channel novelty should help only when channels have partially complementary error patterns; it may hurt when one channel is consistently superior.
3. The combined policy is not assumed to dominate either component.
4. With shuffled timestamps and shuffled channel labels, apparent gains should disappear.
5. Under equal observation and compute budgets, report identification accuracy, cumulative information gain, regret, calibration, and action cost.

Evidence for this specific inductive bias requires improvement over generic and shuffled controls across held-out environment families. Otherwise remove the bias or restrict its scope.

## 6. Next work

- Build a synthetic environment generator with controllable temporal regimes and channel error correlations.
- Run multi-seed comparisons against E12-A2-M and random/fixed policies.
- Add prequential evaluation and confidence intervals.
- Study competing Five-Agents feature families and reciprocal Three-Thefts interaction graphs separately; do not add them to this selector until semantics and benchmarks are specified.

## 7. Research discipline

This is a deterministic policy scaffold, not a neural architecture and not proof that Yinfu-derived priors improve reasoning. Preserve provenance, commit hash, seeds, budgets, and negative results. Do not promote to main without independent audit and ablation evidence.
