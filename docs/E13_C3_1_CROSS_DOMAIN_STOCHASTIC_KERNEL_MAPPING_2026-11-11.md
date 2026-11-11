# E13-C.3.1 Explicit cross-domain stochastic kernel mapping

Date: 2026-11-11

## Status

Bounded executable mapping and held-out row validation added on top of the
E13-C.3 exact finite stochastic oracle. This is not automatic semantic
alignment, open-world causal discovery, or proof of global mechanism identity.

## Why distribution similarity is insufficient

Two systems can have similar marginal output distributions while differing in
state representation, action semantics, feedback, or conditional transition
rows. Therefore the validation target is not an unconditioned output histogram.
It is a set of conditional transition distributions under explicitly aligned
source and target states/actions.

The validation layers are distinct:
1. Vocabulary alignment: explicit variable, value, and action mappings.
2. Conditional kernel alignment: compare mapped source next-state
   distribution with the target next-state distribution for an aligned
   state/action pair.
3. Held-out intervention evidence: repeat comparison on cases not used to
   propose the mapping.
4. Multi-step trajectory validation: future gate; one-step row agreement alone
   does not prove feedback or long-horizon equivalence.

## Explicit map contract

StochasticKernelMap contains:
- complete bijection between source and target state-variable names;
- explicit per-variable source-value to target-value mappings;
- complete injective mapping of source actions into target actions.

No renaming is inferred from string similarity, labels, or matching marginals.
Missing value mappings yield UNKNOWN. Variable-map omissions or collisions
are rejected as contract errors.

## Conditional distribution comparison

For each KernelValidationCase, the validator:
- maps the source state and action explicitly;
- requires mapped source state and mapped action to equal supplied target
  state and action;
- obtains source and target transition rows;
- maps every source next state into target vocabulary;
- compares categorical distributions with exact total variation:

  TV(P,Q) = 1/2 * sum_x |P(x)-Q(x)|

All probabilities remain exact Fraction values. A configurable TV threshold
is a declared tolerance, not a learned confidence interval.

Statuses:
- PASS: all supplied cases meet the declared threshold;
- MISMATCH: at least one supplied case exceeds it;
- INCOMPLETE: at least one case lacks mapping or transition support and no
  supplied case has already demonstrated a mismatch;
- NO_VALIDATION_CASES: no evidence was supplied.

PASS_ON_SUPPLIED_CASES deliberately does not mean global equivalence. The
coverage of tested state/action support must always be reported.

## Tests added

- Explicit renamed variable/value/action mapping with equal conditional kernel.
- Same support but different transition probabilities -> nonzero TV mismatch.
- Incomplete variable mapping rejected.
- Missing target transition support -> UNKNOWN/INCOMPLETE, never a false pass.
- Action alignment mismatch -> UNKNOWN.

## Limitations and next gates

Not yet implemented:
- mapping of context variables and context-dependent transition kernels;
- probabilistic multi-step rollout comparison across mapped domains;
- posterior version-space revision under noisy evidence;
- likelihood calibration, candidate priors, Bayesian EIG;
- hidden confounder identification or causal sufficiency tests.

Next:
1. Add context-indexed kernels and verify context mappings explicitly.
2. Add multi-step cross-domain trajectory forecasts and held-out action sequences.
3. Construct counterexamples with identical one-step marginals but different
   feedback loops; ensure multi-step tests reject false equivalence.
4. Add evidence ledger events for PASS, MISMATCH, and UNKNOWN without erasing
   prior candidates or silently treating missing evidence as contradiction.
5. Only after defining priors and observation likelihoods, add posterior
   candidate updates and calibrated EIG.