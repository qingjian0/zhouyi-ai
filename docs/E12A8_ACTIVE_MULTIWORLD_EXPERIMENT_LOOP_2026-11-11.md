# E12-A8: Prequential Active Multi-World Experiment Loop

Date: 2026-11-11
Status: first bounded implementation slice; tests authored, CI pending.

## Research question

Can a learner choose interventions that efficiently distinguish competing relational mechanisms, commit predictions before observation, and update its beliefs only after the environment reveals an outcome?

E12-A2 already provides a generic finite-hypothesis expected-information-gain selector. E12-A7 provides a controlled multi-world mechanism benchmark. E12-A8 connects these components in a sequential experimental loop rather than reimplementing a generic selector.

## Protocol

For each step:

1. Construct a permitted action set. An action specifies passive observation or intervention, input value, context, time, and measurement cost.
2. Compute each action's expected information gain under the current posterior and the declared ternary observation-noise channel.
3. Select the affordable action with maximum expected information gain per unit cost. Ties are deterministic.
4. Commit the prior and complete likelihood table to the ledger.
5. Only after commit, ask the environment to execute the action.
6. Reveal the observed outcome. Missing observations are recorded but do not update the posterior.
7. Update the posterior from the frozen likelihood table. A revealed outcome cannot be applied twice.
8. Stop on confidence threshold, exhausted budget, exhausted action set, or no discriminating action.

The learner-facing episode result does not contain the true mechanism. The evaluator wrapper reads the world mechanism only after the learner episode has finished.

## Action model

Actions are bounded to:
- intervention: false / true;
- input x: 0, 1, 2;
- context: 0, 1;
- time: 0, 1, 2, 3.

Passive measurements cost 1.0; interventions cost 2.0. These are explicit synthetic benchmark costs, not measured real-world costs.

The hypothesis family is inherited from E12-A7: direct, inverse, context_gate, confounded, delayed_switch, and null. The selector reuses the existing E12-A2 EIG and Bayesian-update implementation. E12-A7 predictions construct the action likelihoods. A seeded symmetric ternary measurement-noise channel is applied after the action is committed; its assumed probability is also used by the learner. Missing outcomes are treated as censored evidence and do not update the posterior.

## Key identifiability property

Under the declared world generator, passive observations cannot distinguish direct influence from the confounded mechanism: both predict the observed X value. An intervention can distinguish them because the confounded world retains the latent common cause while the direct world follows assigned X.

The active selector should therefore choose an intervention when the posterior mass is concentrated on this pair and the budget permits it. If interventions are unavailable, it must report no discriminating action rather than invent certainty.

## Baselines

Compare:
- active: maximum expected information gain / cost;
- random: seeded random choice among affordable actions;
- fixed: deterministic action-ID order.

All policies receive the same action set, world families, seed list, cost schedule, stochastic measurement-noise rate, and total budget. The synthetic world mechanism itself remains fixed; seeds vary the measurement channel and the random baseline policy, not the underlying world family. Report:
- exact mechanism identification accuracy;
- high-confidence error rate;
- mean measurement cost;
- mean number of measurements;
- confidence and posterior trajectory;
- abstention / no-discriminating-action rate.

Do not claim active selection wins without executed multi-seed results and uncertainty intervals.

## Tests

- passive observational equivalence for direct/confounded;
- intervention selection when the posterior is direct/confounded;
- commit-before-reveal posterior update;
- reveal-before-commit rejection;
- duplicate commit/reveal rejection;
- missing observation leaves posterior unchanged;
- budget excludes interventions;
- learner result contains no truth field;
- active/random/fixed evaluation shape.

## Limitations

- Finite known mechanism class; the learner cannot invent a new mechanism family.
- The action space is enumerated in advance.
- The generator and evaluator share a process. The separation is a protocol boundary, not a security sandbox.
- The symmetric ternary measurement-noise likelihood is assumed rather than learned; the injected measurement noise is seeded and matched to that likelihood.
- The active policy is myopic one-step EIG/cost, not a long-horizon planner.
- World-family observations are synthetic and small.
- No Yijing, Taixuan, or Yinfu prior is included in this slice.
- No causal claim beyond the controlled intervention semantics encoded by the synthetic generator.

## Next falsification steps

1. Remove intervention actions and verify the direct/confounded pair remains unidentifiable.
2. Increase noise and missingness, then measure calibration and high-confidence error.
3. Add action-dependent costs and delayed outcomes.
4. Compare myopic EIG/cost with two-step lookahead and random/fixed baselines.
5. Add no-prior, random-prior, Yin/Yang partition, Taixuan ternary, shuffled, and anti-aligned proposal priors at matched compute.
6. Add evaluator process isolation before using the benchmark as a security-sensitive claim.
