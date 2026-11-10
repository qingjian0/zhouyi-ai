# YF-02 / YF-03 — Competing Five-Agents Models and Reciprocal Interaction Dynamics

Status: research protocol + deterministic synthetic mechanism. No empirical advantage is claimed.

## 1. Textual basis and interpretation plurality

The received text of the *Huangdi Yinfu Jing* has multiple commentarial readings. Zhang Guo's commentary identifies the Five Thieves as 命、物、时、功、神; other commentary traditions identify them with 五行. Other exegetical traditions use further correspondences. These are competing historical interpretations, not interchangeable synonyms and not established scientific variables.

The Three-Thefts passage is also interpreted differently. Some commentaries emphasize reciprocal generation and destruction among Heaven, things, and humans; others frame the interaction as cycles of use, depletion, and transformation. This experiment extracts only a minimal abstract motif: three interacting roles with directed effects and feedback. It does not assert that this is the single correct exegesis.

## 2. YF-02: competing feature ontologies

Create separate model families rather than a fused feature set:

- F0: generic statistical features, no classical prior.
- F1: Five-Phase relational features (生、克、制化) with mappings declared before training.
- F2: 命、物、时、功、神 as five independent feature families; no forced one-to-one mapping to the Five Phases.
- F3: capacity-matched random features.
- F4: permuted symbolic mappings.

Evaluation must use held-out task families and equal parameter/compute budgets. Report which feature families are useful, redundant, or harmful. Never select a mapping based on test-set outcomes.

## 3. YF-03: triadic reciprocal interaction graph

Prototype: `prototype/yinfu_interaction_dynamics.py`

A directed edge (i\to j) carries a context-sensitive effect:

`effect(i,j,c) = base(i,j) + sensitivity(i,j) * c`

All edges read a single prior-state snapshot and update synchronously. This avoids accidental dependence on edge iteration order. A context change can reverse an edge's sign; such a reversal is a measurable property of the model, not a metaphysical claim.

The three roles in the demo are generic environment, resource, and agent. The graph includes:
- environment -> resource replenishment;
- resource -> agent benefit;
- agent -> resource extraction/depletion.

This provides a controlled test bed for reciprocal effects and delayed costs.

## 4. YF-04: joint trigger as a hypothesis

A future experiment should compare:
- environment-only trigger;
- agent-only trigger;
- additive environment + agent trigger;
- interaction trigger with a cross-term;
- random trigger and shuffled-time controls.

A simple candidate form is (g(e,a)=w_e e+w_a a+w_{ea}ea). The interaction term is retained only if it improves held-out prediction and calibration over additive controls.

## 5. YF-05: benefit/harm reversal

The prototype exposes a sign-reversal diagnostic:
- short-term intervention delta;
- long-term joint outcome delta;
- thresholded reversal flag.

The demo deliberately distinguishes an immediate agent benefit from a longer-horizon joint score that includes resource viability. It is a toy example to verify the metric plumbing, not evidence that real-world effects reverse in the same way.

Future benchmark dimensions:
- horizon length;
- resource replenishment rate;
- extraction pressure;
- delayed feedback;
- observation noise;
- distribution shift.

## 6. YF-06: adaptive control

Do not jump directly to autonomous action. First test a constrained controller:
1. infer a posterior over competing interaction models;
2. select an observation by expected information gain;
3. estimate action effects under each model;
4. choose a bounded action subject to budget/safety constraints;
5. observe the outcome and update;
6. abstain when models disagree too strongly or evidence is insufficient.

## 7. Required controls and metrics

Controls:
- no-symbolic-prior baseline;
- random feature baseline;
- permuted-symbolic baseline;
- additive-only vs interaction model;
- shuffled context/time;
- ablation of each directed edge;
- equal observation, parameter, and compute budgets.

Metrics:
- held-out prediction error;
- calibration / Brier score;
- intervention regret;
- sign-reversal precision and recall;
- sample efficiency;
- stability under noise and distribution shift.

Run at least 20 seeds for initial screening and report confidence intervals. Do not merge into main until the full suite passes and the benefit replicates on held-out environment families.

## 8. Research safeguards

Classical terms are provenance-bearing hypotheses, not labels for hidden truths. Keep original quotations, commentary source, chosen interpretation, mapping rationale, and experiment ID together. Preserve negative results. Never retrofit a symbolic mapping after inspecting test outcomes.
