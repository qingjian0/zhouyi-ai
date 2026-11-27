# Under-4B Autonomous Classiang Model: Architecture and Acceptance Protocol v1

**Status:** research design / not yet implemented or trained  
**Target integration branch:** dev  
**Hard model budget:** fewer than 4.0B total learned parameters across every model component used for the core capability.  
**Long-context targets:** 1,000,000 input tokens and 1,000,000 generated output tokens, treated as separate engineering acceptance targets.

## 1. Objective

Build a compact, evidence-grounded Classiang system that can:
1. Observe text and structured inputs, extract evidence-bearing features, and preserve source offsets.
2. Propose, distinguish, split, merge, and reject classes under explicit evidence gates.
3. Discover candidate relations and cross-domain mappings, then test them on held-out examples.
4. Actively choose informative experiments, record hypotheses before observing outcomes, and revise beliefs from counterexamples.
5. Learn incrementally without silently converting its own predictions into Gold labels.
6. Process very long documents and produce very long outputs through bounded, resumable computation.

The intended research advantage is not parameter count or benchmark rhetoric. It is a testable combination of structured representations, evidence provenance, active experimentation, and continual learning.

## 2. Non-negotiable claim boundaries

- A model below 4B parameters is a design constraint, not evidence that it can outperform GPT or DeepSeek.
- A 1M-token document pipeline is not equivalent to dense full-attention over one million tokens.
- A system capable of emitting one million output tokens does not guarantee that all one million tokens are useful, coherent, or factually correct.
- Retrieval, external memory, caches, and tool execution do not count as model parameters, but their storage, latency, security, and compute costs must be reported.
- No model-generated annotation becomes Gold without independent review or a separately validated label-acquisition protocol.
- Synthetic tasks validate implementation and controlled hypotheses; real-domain claims require licensed, source-disjoint, independently reviewed datasets.
- All baselines must use matched data splits, parameter budgets, compute budgets, and evaluation access.

## 3. Proposed system architecture

Use one compact learned core plus explicit, inspectable non-neural state. Avoid requiring a second large model as a hidden dependency.

### 3.1 Learned core: target budget 3.2B–3.8B parameters

The exact allocation is a search space, not a frozen commitment:

| Component | Initial budget envelope | Responsibility |
|---|---:|---|
| Compact language backbone | 2.4B–2.9B | Language interface, instruction following, local reasoning and generation |
| Long-sequence/recurrent blocks and adapters | 0.3B–0.5B | Chunk-state updates, long-range integration and memory-conditioned reasoning |
| Classiang feature/relation heads | 0.15B–0.25B | Feature, relation, boundary, uncertainty and transfer scoring |
| Exploration / experiment policy | 0.05B–0.10B | Query selection, disagreement ranking and budget-aware action proposals |
| Output and calibration heads | 0.05B–0.10B | Structured decoding, abstention and confidence calibration |
| **Total** | **3.0B–3.85B** | Must be measured from the actual serialized trainable model |

Parameter accounting must include embeddings, output heads, adapters, routing networks, and every learned component shipped with the system. Quantization changes storage/compute, not parameter count. If any component is frozen, it still counts toward the total learned-parameter ceiling.

### 3.2 Long-context input: hierarchical streaming, not million-token dense attention

Process a 1M-token input as a sequence of bounded chunks:

1. **Chunk encoder:** process overlapping chunks using a bounded local attention window.
2. **Evidence ledger:** retain exact source spans, offsets, source IDs, timestamps, and content hashes.
3. **Entity/relation state:** update a compact structured state containing entities, attributes, events, relations, temporal links, contradictions, and unresolved questions.
4. **Recurrent memory:** carry a bounded learned state between chunks; store overflow in external indexed memory rather than allowing unbounded KV growth.
5. **Hierarchical retrieval:** retrieve original passages and neighboring evidence by query, relation, time, and provenance.
6. **Conflict-aware consolidation:** preserve competing claims and provenance; never overwrite contradictory evidence with a single summary.
7. **Answer-time evidence reconstruction:** cite original spans and distinguish direct evidence, inference, and unresolved gaps.

Required comparisons: sliding-window baseline, retrieval-only baseline, recurrent-state baseline, and hybrid hierarchical baseline. Report exact token coverage, evidence-link precision/recall, long-distance relation accuracy, contradiction recall, memory bytes, peak RAM/VRAM, and latency.

A 1M-token context claim passes only when a single end-to-end test ingests 1,000,000 tokenizer-counted input tokens, retrieves evidence from early/middle/late regions, detects planted conflicts, and answers held-out questions with auditable source spans under a declared hardware budget.

### 3.3 Long output: one continuous logical generation stream

The 1M-output target is **one continuous logical generation session** for one task, counted by the declared tokenizer. Streaming and persistence are runtime mechanisms, not permission to concatenate independent answers:

- Keep one logical token stream and one evolving model state from the first token to token 1,000,000.
- The transport/storage layer may flush bounded byte/token chunks and assign monotonically increasing checkpoint offsets. These are persistence boundaries only, not independently prompted segments.
- Persist the exact decoder/recurrent state, output offset, rolling constraints, claims ledger, definitions, unresolved items, and content digest needed to resume the same generation session.
- Support pause, resume, and cancellation. A resumed run must continue from the committed state without silently restarting, skipping, duplicating, summarizing, or substituting output.
- If exact state restoration is unavailable, report the divergence and do not count the run as a successful exact-resume acceptance.
- Apply token, time, memory, and tool budgets; never promise unbounded execution.
- Evaluate factual consistency, repetition, and constraint drift at multiple distances, not only next-token quality.

Acceptance requires a tokenizer-counted 1,000,000-token output from one logical generation stream. Persisted chunks must reconstruct the exact emitted stream in order, with no missing or duplicated tokens; independently generated completions concatenated together do not pass. This is distinct from proving that the model can reason well over a 1M-token input.

## 4. Autonomous exploration and evolution loop

Implement a constrained scientific loop:

Observe -> Hypothesize -> Design -> Predict -> Seal -> Reveal -> Evaluate -> Revise -> Version

1. **Observe:** ingest evidence with provenance and license metadata.
2. **Hypothesize:** propose a bounded set of competing class/relation explanations; attach predicted discriminating observations.
3. **Design:** choose experiments by expected disagreement/information gain per unit cost, with a fixed budget.
4. **Predict:** commit predictions before labels or outcomes are revealed.
5. **Seal:** hash and freeze the prediction batch and model version.
6. **Reveal:** evaluator releases independently held-out outcomes only after sealing.
7. **Evaluate:** compute preregistered metrics and compare against simple baselines.
8. **Revise:** accept, narrow, split, merge, or reject a hypothesis with a complete evidence trail.
9. **Version:** create an immutable model/data/experiment manifest; retain rollback and replay capability.

The learner must not control the locked evaluator or inspect hidden labels. Model-generated hypotheses may enter a proposal queue, but they cannot self-certify. Exploration actions run in a sandbox with allowlisted tools, explicit resource budgets, and no autonomous publication, spending, credential access, or destructive repository actions.

## 5. Continual learning without self-confirmation

- Keep immutable Gold, reviewed feedback, weak labels, synthetic data, and model proposals in separate stores.
- Use source-family and time-based splits to prevent near-duplicate leakage.
- Use replay or representative memory, regularization, and selective adapters as competing anti-forgetting strategies.
- Measure old-domain regression after every new-domain update.
- Maintain a frozen regression suite and a hidden holdout.
- Require an independent reviewer or a validated adjudication process for new Gold labels.
- Support rollback to any signed/versioned checkpoint and replay of the evidence events that produced it.

## 6. Training stages

### Stage A — Audit and data readiness

Inventory current CPG-EI, SROK, Classiang pipeline, text span learners, active-review queue, E12 evidence/event infrastructure, and all available datasets. Record exact commit, dataset digest, license, source family, annotation status, and split.

**Gate:** no training run starts without a manifest, deduplication report, source-disjoint splits, and independently reviewed Gold validation/test partitions.

### Stage B — Compact backbone selection

Compare at least two viable sub-4B architectures under matched tokenizer, data, and compute. Keep the simplest architecture that meets quality, memory, and latency gates. Establish a reproducible pretraining/continued-pretraining recipe and checkpoint provenance.

**Gate:** measured total parameter count below 4B; baseline results and compute costs published.

### Stage C — Classiang representation learning

Train feature extraction, boundary localization, relation identification, contrastive discrimination, uncertainty/abstention, and cross-domain mapping heads. Preserve current exact-span provenance and explicit-negative discipline.

**Gate:** positive gains over NB/sparse-linear baselines on source-disjoint real Gold data; no leakage; calibrated abstention; complete evidence offsets.

### Stage D — Active exploration

Train/evaluate the experiment policy using sealed prediction batches and independent evaluation. Begin with finite, auditable action spaces before attempting open-ended exploration.

**Gate:** improved information gained per unit budget over random and uncertainty-only selection; no hidden-label access; reproducible counterexample-driven revision.

### Stage E — Long-context memory

Implement chunking, recurrent state, evidence ledger, hierarchical retrieval, and conflict handling. Test 32K, 128K, 256K, 512K, then 1M tokens; do not skip intermediate gates.

**Gate:** 1M-token end-to-end acceptance on declared hardware with measured memory, latency, coverage, retrieval, and reasoning metrics.

### Stage F — Continual learning

Introduce new domains in sequence and compare replay, regularization, adapters, and hybrid approaches.

**Gate:** positive new-domain transfer while staying within preregistered old-domain regression limits.

### Stage G — Long output and release

Implement resumable streaming generation and one-million-token output stress tests. Release only when safety, quality, reproducibility, model-size, and runtime gates pass.

## 7. Required benchmark suite

Every reported result must include dataset version/digest, source split, model commit, parameter count, tokenizer, seed, hardware, wall-clock time, peak memory, and confidence interval where applicable.

| Capability | Required metrics |
|---|---|
| Evidence extraction | Exact-span P/R/F1, offset integrity |
| Class induction | Macro-F1, open-set AUROC, unknown-class discovery precision |
| Boundary learning | Hard-negative F1, false-accept rate, abstention coverage-risk |
| Relation learning | Relation F1, structural consistency |
| Composition | Held-out combination and rule-family OOD |
| Cross-domain transfer | Leave-one-domain/source-family-out delta |
| Active exploration | Information gain per cost, counterexample efficiency |
| Continual learning | New-domain gain, old-domain forgetting |
| Long context | Evidence recall by position, long-distance links, conflict recall |
| Long output | Segment integrity, repetition, consistency, factual error rate |
| Efficiency | Parameters, tokens/s, peak RAM/VRAM, energy and wall-clock cost |

To support any claim of superiority over GPT/DeepSeek, publish a preregistered, contamination-controlled, independently reproducible comparison on public and held-out tasks. Compare both quality and cost; do not infer superiority from parameter count or selected benchmark wins.

## 8. Immediate implementation order

1. Audit and reconcile the current dev state after PR #614 and the exact-span follow-up; do not branch-sprawl or duplicate existing modules.
2. Produce one canonical experiment manifest and dataset registry.
3. Repair and validate current span-learning failures on exact-head tests.
4. Establish real, licensed, independently reviewed Chinese and cross-domain Gold sets.
5. Add a compact-model benchmark harness with hard total-parameter accounting.
6. Prototype recurrent/hierarchical memory behind the existing Classiang interfaces.
7. Connect the active-review queue to sealed evaluation and versioned feedback.
8. Run matched-budget baselines before choosing a final backbone.
9. Add 1M input and 1M output stress tests only after smaller scale gates pass.

## 9. Current feasibility and execution boundary

This repository integration can define architecture, implement code, run GitHub-hosted CI, and analyze artifacts. It does not itself provide a guaranteed multi-GPU training cluster, licensed large-scale corpus, or a persistent million-token inference service. A real pretraining/fine-tuning run requires declared hardware, dataset access, runtime, and compute budget.

Therefore the present deliverable is an architecture and falsifiable acceptance protocol. It is **not** a trained model, a completed 4B checkpoint, a demonstrated 1M-context runtime, or evidence of superiority over GPT/DeepSeek.

## 9. Repository readiness snapshot (dev baseline)

Audited against `dev` at commit `6740112f20bba4a92ea6f835ac77be04e4ce3933`:

- The repository already contains the Classiang observation, class formation, contrastive span, review-queue, evidence-ingestion, SROK/CPG-EI, event-ledger, token-count, and streaming-memory components. Reuse these interfaces; do not create a parallel agent or evidence stack.
- The current contrastive text learner is a CPU sparse-feature/margin baseline. It is not a pretrained language model or a sub-4B neural backbone. `pyproject.toml` declares no mandatory ML framework dependency; the optional dependency is `tokenizers`.
- The latest integrated synthetic contrastive smoke run (workflow run 46039564165) used 12 generated records, with 10 train and 2 validation records. Its reported validation F1 was 1.0, but the report explicitly labels the data synthetic and the result a pipeline smoke test. It is not evidence of real semantic or cross-domain generalization. The run's checkpoint also exposed an exact-phrase label lookup; follow-up PR #616 removes that shortcut and must pass exact-head CI before merge.
- The classical source catalog contains 148 candidate works. The structured quotation corpus contains 43 candidate records and 52 unreviewed claims; the casebook contains 26 unreviewed cases. These are research/evidence candidates, not an adjudicated training Gold set or a licensed large-scale pretraining corpus.
- Streaming evidence ingestion, evidence retrieval, and tokenizer-count manifests exist. However, the long-context specification explicitly does not claim a demonstrated 1M-token / 64-MiB runtime, lossless semantic compression of arbitrary text, or complete native language generation. No end-to-end 1M-input inference run, 1M-continuous-output run, or sub-4B checkpoint has been demonstrated in this audit.
- The review queue correctly keeps model proposals separate from Gold; independent source verification and annotation adjudication remain required before supervised training.

This snapshot is a repository audit, not a model evaluation. It must be refreshed when the `dev` base changes.

## 10. Release definition

The project is not "complete" until a versioned checkpoint under 4B total parameters passes the real Gold, OOD, active-exploration, continual-learning, 1M input, 1M output, reproducibility, and runtime gates. A green CI badge alone is insufficient.
