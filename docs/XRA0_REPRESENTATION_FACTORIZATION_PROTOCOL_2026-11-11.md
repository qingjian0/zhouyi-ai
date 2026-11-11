# XRA-0: Representation Factorization and Adaptive Selection Protocol

Date: 2026-11-11
Status: research specification + encoding primitive
Branch: research/triadic-representation-arbitration-2026-11-11
Parent protocol: CROSS_REPRESENTATION_ARBITRATION_ZY_TX_YF_2026-11-11

## 1. Correction: cardinality is not radix

The project must distinguish:

1. **Semantic cardinality K** — number of distinguishable states in a task's declared latent partition.
2. **Coordinate radix R** — alphabet size used by an individual code coordinate (binary R=2, ternary R=3, etc.).
3. **Factorization F** — how a state or object is decomposed into coordinates, roles, levels, and compositional parts.
4. **Operator grammar G** — permitted transformations and relation-composition rules over those parts.
5. **Observation policy O** — which evidence is requested, measured, or acted upon.

A task with K=3 semantic states can be encoded using two binary digits or one ternary digit. Therefore, the statement "binary cannot represent a ternary state" is false. For a fixed-width radix-R code, the minimum digit count is:

`d_R(K) = min{d >= 1 : R^d >= K} = ceil(log_R K)`.

This is only a code-capacity statement. It says nothing by itself about learning speed, generalization, robustness, or cognitive quality.

The E02-A binary parity and E02-B Z3 modular-addition experiments are different task generators. Their scores cannot be compared as if they were a controlled binary-vs-ternary representation experiment.

## 2. Representation object

A representation candidate is a tuple:

`Rep = (P, K, R, C, F, G, V)`

- P: partition or abstraction map from raw observations to semantic state IDs.
- K: number of semantic equivalence classes represented by P.
- R: coordinate radix or a mixed-radix vector.
- C: injective codebook from semantic state IDs to codewords.
- F: factorization / compositional layout.
- G: operator grammar over represented components.
- V: immutable version and provenance metadata.

The observation policy O is evaluated separately. It must not be folded into the encoding score.

For mixed radix `R=(r_1,...,r_d)`, representable capacity is `product(r_i)`. A codebook must be injective over the active semantic IDs. Unused codewords must be explicit and decode to an abstention / unknown result, never silently mapped to a valid state.

## 3. Classical theory mapping without category errors

### Zhouyi / Yixiang

- Yin-yang: a binary contrast / complement hypothesis over a declared feature.
- Four images: a two-coordinate binary composition hypothesis.
- Eight trigrams: a three-line binary state code (8 codewords).
- Sixty-four hexagrams: a six-line binary state code (64 codewords).
- Line change: a state transition operator.
- Taking images by analogy: a candidate structure-preserving mapping between domains, subject to evidence and counterexamples.

These are candidate representational priors, not proof that all domains have binary ontology. The current repository's bit convention is bottom-to-top, with 1=yang and 0=yin; the six-bit ID is a computational index, not King Wen sequence order.

### Taixuan

A ternary alphabet is a candidate coordinate radix and potentially a candidate structural grammar. The ternary encoding must be tested against:
- binary codebooks with the same semantic cardinality;
- one-hot codes;
- learned embeddings;
- explicit symbol/codeword permutations;
- generic finite-algebra baselines.

A Z3 operation is a task-generating rule, not a generic demonstration that ternary is superior.

### Yinfu-inspired dynamic cognition

YF contributes hypotheses about observation, context-sensitive relation updates, and evidence-governed structural revision. It is not a third symbol radix. Its observation and update policy is axis O and its lifecycle semantics must remain explicit.

## 4. Hypotheses and nulls

- H0-A: for fixed P, K, F, G and a permutation-equivariant learner, bijective codeword relabeling should not change the underlying task's Bayes-optimal accuracy.
- H1: under fixed task semantics and matched resources, radix/factorization choices may change finite-sample optimization, sample efficiency, robustness, or compute cost.
- H2: adaptive selection can improve over the Validation-selected best fixed candidate on locked test tasks, after charging selector cost.
- H3: structural priors inspired by Zhouyi or Taixuan help only when their declared invariants align with the task generator, and must beat generic capacity-matched priors.
- H4: YF-inspired active observation helps only where observation choices affect information and have declared costs.
- H5: representation and observation adaptation may interact; this requires a factorial interaction test.

Null explanations to actively test: codeword ordering shortcut, unequal capacity, unequal parameter count, unequal training compute, task-generator leakage, selector overfitting, and a task family tailored to one prior.

## 5. Experimental design: separate five axes

A factorial or carefully blocked design must vary independently:

A. Semantic partition P and cardinality K.
B. Coordinate radix R (including binary, ternary, and mixed radix).
C. Factorization F (flat, hierarchical, role-factorized, learned).
D. Operator grammar G (none, generic composition, preregistered Yixiang, preregistered Taixuan, shuffled controls).
E. Observation policy O (passive, random, fixed order, information-gain-per-cost, YF-adaptive).

Do not compare a binary flat code with a ternary hierarchical grammar and attribute the difference to radix. Ablate one axis at a time first, then test interactions.

## 6. Mandatory controlled comparisons

For each fixed semantic task and each K:
1. Binary codebook with minimum fixed-width digits.
2. Ternary codebook with minimum fixed-width digits.
3. One-hot code.
4. Randomly permuted binary codebook.
5. Randomly permuted ternary codebook.
6. Learned embedding with matched parameter budget.
7. Mixed-radix codebook where useful.
8. Oracle / exact finite hypothesis baseline for tractable tasks.

The same semantic IDs, examples, labels, train/validation/test split, optimizer family, update budget, and evaluation queries must be used across encoding arms. If model capacity cannot be exactly matched, report both parameter-matched and compute-matched comparisons.

For each result, report:
- semantic K, radix R, digit count and unused capacity;
- codebook and permutation seed;
- representation and model parameter count;
- update steps, candidate evaluations, wall time, memory and latency;
- in-distribution, symbol-permutation, rule-family OOD, and object-disjoint results;
- calibration, abstention, and error under noise.

## 7. Adaptive selector: selection target and objective

The selector must not choose radix based on a hand-coded belief that one classical theory is true. It selects among a development-time candidate set using evidence available before the locked query.

A candidate's utility can be modeled as:

`U(Rep | D_dev) = E[heldout predictive score] - lambda_c * compute - lambda_m * memory - lambda_s * switch_cost - lambda_u * uncertainty_penalty`.

The exact score and lambdas must be frozen on validation. A complexity-aware MDL / minimum-description-length criterion may be included as a baseline, but it is not a substitute for held-out predictive performance.

Selector options:
- fixed best-on-validation candidate;
- learned task-context selector;
- Bayesian model averaging over representation candidates;
- online selector with prequential regret tracking;
- DEFER / abstain when evidence does not distinguish candidates.

The selector must pay its training and inference costs. It cannot use hidden generator IDs, true K, rule labels, test labels, or future observations unless a benchmark explicitly marks them evaluator-only.

## 8. Representation uncertainty and versioning

Do not force a single representation prematurely. Maintain a posterior or candidate set over plausible partitions and codebooks while evidence is insufficient.

A representation switch is a versioned state transition:
- preserve original raw evidence and semantic IDs;
- record old and new codebook hashes / versions;
- record the mapping or explicit non-mapping between versions;
- distinguish reversible recoding from a changed semantic partition;
- replay or re-encode only through a logged migration operation;
- never silently reinterpret historical evidence.

A bijective recoding changes the codebook but not the semantic partition. A partition refinement or coarsening changes what distinctions are represented and requires separate evidence and lifecycle decisions.

## 9. Identifiability and leakage

For every episode, the evaluator must calculate whether the support evidence uniquely identifies the target under the declared hypothesis family. If multiple hypotheses remain observationally equivalent, score prediction against the Bayes-optimal posterior and preserve ambiguity; do not mark a valid alternative structure as wrong.

Learner-visible inputs must exclude:
- true K when K is meant to be discovered;
- generator family and hidden rule IDs;
- semantic symbol mapping and permutation seed;
- source groups or object identity labels that leak the target;
- future query labels and evaluator truth.

Run metadata-only attackers and symbol-permutation controls. A model that succeeds only on canonical codeword assignments has not demonstrated representation-invariant abstraction.

## 10. Implementation already added

The branch now contains:
- `prototype/xra_representation.py`: explicit injective fixed-width radix codebooks, canonical and permuted assignments, round-trip encode/decode, capacity and unused-code accounting.
- `tests/test_xra_representation.py`: tests for K=3 in binary and ternary, multiple cardinalities/radices, permutation round trips, invalid assignments, and strict input validation.

This primitive is intentionally not an adaptive learner. It establishes encoding invariants before model comparisons.

## 11. Next implementation gates

- XRA-0a: run codebook tests and record CI evidence.
- XRA-0b: add task manifest schema that explicitly declares semantic K only to the evaluator when K is hidden from the learner.
- XRA-0c: implement same-task generator with hidden symbol/codebook permutations and exact identifiability checks.
- XRA-1a: adapters for E02-A, E02-B, Yixiang and YF policy interfaces, without rewriting their internal semantics.
- XRA-2: fixed representation baselines.
- XRA-3: adaptive selector only after all controls and leakage checks pass.

Do not merge to main or claim a radix advantage based on codebook round-trip tests. Those tests prove implementation invariants only.
