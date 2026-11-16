# E12 / CPG-EI Related Work: Compositionality, Program Synthesis, and Higher-Order Relations

Date: 2026-11-11  
Status: literature map; not an exhaustive systematic review.

## 1. Why this review exists

The project's motivating idea—discover reusable primitives, combine them in non-contiguous ways, and generalize to unseen combinations—is already an active research area under compositional generalization, program synthesis, neuro-symbolic learning, concept learning, and higher-order relational learning.

Therefore CPG-EI must not claim that "composition beyond token sequences" or "parallel candidate evaluation" is itself unprecedented. Its research contribution must be a specific, measurable combination of:
- evidence-grounded primitive induction;
- active selection of observations that distinguish candidate structures;
- sparse, typed, non-contiguous composition;
- explicit ambiguity and abstention;
- reusable concept lifecycle and continual revision;
- optional, falsifiable Yijing-inspired inductive biases.

## 2. Compositional generalization and program synthesis

### Shi et al. (2022), Compositional Generalization and Decomposition in Neural Program Synthesis
Google Research / DL4C at ICLR 2022.  
https://research.google/pubs/compositional-generalization-and-decomposition-in-neural-program-synthesis/  
https://arxiv.org/abs/2204.03758

Relevance:
- Defines multiple axes of compositional generalization, including length generalization and combining known subroutines in unseen ways.
- Provides benchmark tasks based on SCAN and RobustFill.
- Shows that decomposition and attention modifications can improve performance but do not make the task trivial.

Implication for E12-A3:
- Separate unseen-combination generalization from simple interpolation.
- Hold out entire composition structures, not only random examples.
- Compare against program-synthesis and sequence-model baselines.

### Shi et al. (2024), ExeDec: Execution Decomposition for Compositional Generalization in Neural Program Synthesis
Google DeepMind, ICLR 2024.  
https://deepmind.google/research/publications/49061/

Relevance:
- Uses execution-informed subgoal decomposition.
- Reports improved compositional generalization on program-synthesis tasks.
- Demonstrates that explicit decomposition is a serious baseline, not a novelty claim for CPG-EI.

Implication:
- E12-A3 should compare sparse primitive composition with execution/decomposition strategies.
- Evaluate whether active evidence acquisition adds value beyond decomposition alone.

### Klinger et al. (2023), Compositional Program Generation for Few-Shot Systematic Generalization
https://arxiv.org/abs/2309.16467

Relevance:
- Uses modular grammar rules and semantic modules to compose known operations.
- Studies few-shot systematic generalization and incremental learning.

Implication:
- CPG-EI must specify what is learned at the primitive, operator, and composition levels.
- Reuse and incremental extension should be measured directly.

### Ram, Klinger, and Gray (2024), What Makes Models Compositional? A Theoretical View
IJCAI 2024.  
https://www.ijcai.org/proceedings/2024/0533

Relevance:
- Formalizes compositional functions and compositional complexity.
- Connects architecture structure to expressivity and sample complexity.

Implication:
- E12-A3 needs a formal complexity measure for expression DAGs.
- Claims about systematic generalization should be tied to task structure and compositional complexity.

## 3. Neuro-symbolic concept composition

### Kamali, Barezi, and Kordjamshidi (2025), NeSyCoCo: A Neuro-Symbolic Concept Composer for Compositional Generalization
AAAI 2025.  
https://doi.org/10.1609/aaai.v39i4.32439

Relevance:
- Addresses predicate extraction, concept composition, and differentiable computation.
- Explicitly targets limitations from predefined predicates and non-differentiable symbolic composition.
- Reports results on ReaSCAN, CLEVR-CoGenT, and CLEVR-SYN.

Implication:
- E12-A1's finite predicate grammar is only a baseline; it is not a solution to raw-input concept discovery.
- A future neural bridge should compare hard symbolic composition with soft/differentiable predicate composition.
- Avoid presenting symbolic DAG composition as a new idea by itself.

### Yu et al. (2023), A Survey on Neural-Symbolic Learning Systems
Neural Networks, 166, 105–126.  
https://doi.org/10.1016/j.neunet.2023.06.028

Relevance:
- Surveys methods combining neural perception with symbolic reasoning.
- Provides context for modular hybrid architectures.

Implication:
- CPG-EI should define its neural/symbolic boundary and the learning signal passed between modules.
- A symbolic controller must not be treated as evidence that perception has been solved.

## 4. Higher-order relations and hypergraphs

### Kim et al. (2024), A Survey on Hypergraph Neural Networks: An In-Depth and Step-By-Step Guide
KDD 2024.  
https://doi.org/10.1145/3637528.3671457  
https://arxiv.org/abs/2404.01039

Relevance:
- Reviews higher-order interactions represented by hypergraphs.
- Organizes design around input features, structure, message passing, and training strategies.

Implication:
- E02's dynamic hypergraph line has established adjacent literature.
- The potential differentiator is not "using hyperedges"; it is evidence-grounded structure induction, lifecycle governance, active disambiguation, and out-of-family generalization under controlled budgets.

## 5. Active information acquisition

Expected information gain and active model selection are established ideas. E12-A2 should be positioned as a controlled experimental component rather than a novel information-theoretic formula.

A recent discussion of active inference and artificial reasoning reports the importance of information gain over competing models, not only parameter or state uncertainty:
https://www.nature.com/articles/s41467-026-77209-5

For E12-A2-M, compare:
- random and fixed measurement;
- maximum disagreement;
- expected information gain;
- cost-normalized expected information gain;
- exact optimal action on tiny worlds.

The research question is whether the entire evidence-grounded loop improves identification and calibration under held-out worlds, not whether entropy can be calculated.

## 6. Research gap and candidate contribution

The following combination is a candidate contribution to test, not an established novelty claim:

1. A1 proposes typed primitives from permitted observations.
2. A2-M actively selects measurements to distinguish competing primitive hypotheses.
3. A3 composes primitives into sparse, typed DAGs and retains uncertainty when structures are observationally equivalent.
4. E02 stores higher-order relations with provenance and lifecycle constraints.
5. E09 revises concepts from new evidence without silently rewriting history.
6. E10/E11 study cross-domain analogy and abstraction with explicit evidence transfer controls.
7. Yijing-inspired structures enter only as ablatable priors, compared against capacity-matched generic and shuffled controls.

Potential differentiator: the integration of active evidence acquisition, primitive induction, sparse composition, and evidence-governed concept lifecycle, evaluated together under held-out compositional families and matched compute budgets.

This contribution is only supported if the integrated system beats strong baselines on reproducible benchmarks and maintains calibrated abstention on unidentifiable tasks.

## 7. Immediate consequences for the roadmap

- Add SCAN/COGS/ReaSCAN/CLEVR-style compositional evaluation where licensing and task fit permit; also maintain small synthetic worlds with exact ground truth.
- Define composition OOD splits: hold out operator combinations, sparse subsets, nesting depth, and primitive-role assignments separately.
- Include a decision-tree/program-synthesis baseline and a neuro-symbolic differentiable-composition baseline where feasible.
- Report both exact expression recovery and semantic behavior; exact syntax can differ while representing the same function.
- Match compute, candidate budget, and training data across comparisons.
- Do not claim novelty based only on multi-path search, hypergraphs, Boolean composition, or information gain.

## 8. Literature status

This is a targeted initial map. Before publication or strong novelty claims, expand it with a systematic search covering:
- concept bottleneck and concept discovery;
- inductive program synthesis and grammar induction;
- active learning and Bayesian experimental design;
- relational representation learning and hypergraph learning;
- continual learning and concept drift;
- compositional OOD benchmarks and data leakage controls.
