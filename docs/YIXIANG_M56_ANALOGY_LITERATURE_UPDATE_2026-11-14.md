# M56 analogy literature update and benchmark implications — 2026-11-14

## Scope

This note updates the M56 benchmark design with recent analogy-evaluation literature. These papers motivate controls; they do not establish that Zhouyi-AI or any yixiang-specific method is superior.

## Findings relevant to M56

### 1. Cross-domain transfer must be tested beyond familiar symbol systems

Stevenson, Pafford, van der Maas, and Mitchell (TACL 2026) tested letter-string analogy solving in the Latin alphabet, a near-transfer Greek alphabet domain, and a far-transfer symbol domain. Their reported human participants generalized across these domains more readily than the tested LLMs.

**M56 implication:** split by representational domain, not just by paraphrase or random item. Include:
- familiar-to-near transfer (same relation template, changed symbol inventory);
- familiar-to-far transfer (unfamiliar visual or abstract token inventory);
- relation-preserving transfer with changed surface attributes;
- relation-breaking controls with similar surface attributes.

The benchmark must separately report within-domain, near-transfer, and far-transfer performance.

### 2. Analogy quality is relational and often multi-plausible

Das and Balke (INLG 2025) propose complex analogy cases with multiple semantically plausible options and overlapping relational structures. Their reported results distinguish embedding/prototypicality behavior from fine-grained relational mapping.

**M56 implication:** do not force every case into one gold analogy when several mappings may be defensible. Store:
- candidate mappings;
- required relation set;
- optional or competing relations;
- relation salience and adjudication provenance;
- acceptable, partial, and invalid mappings.

A relation-preservation score must not be replaced by surface embedding similarity.

### 3. Robustness needs to be evaluated at multiple analogy granularities

Wu et al. (Findings of EMNLP 2026) review analogy generation and evaluation and emphasize that evaluation methods depend on granularity, including lexical and compositional analogy. Their review also identifies human-in-the-loop design as important in LLM-based analogy work and notes continuing debate about whether model performance demonstrates genuine analogy.

**M56 implication:** separate lexical/category resemblance, feature-level analogy, relational analogy, process/mechanism analogy, and long-context scenario analogy. Keep human annotation and adjudication as a first-class evidence source, not merely a final spot check.

### 4. Accuracy alone is not sufficient

Lewis and Mitchell (TMLR 2025) report that tested GPT models can be sensitive to answer order and paraphrasing on analogy variants. Mitchell (Current Directions in Psychological Science, 2026) argues for evaluating abstraction and analogy with robustness, transparency, and insight into solution processes, not accuracy alone.

**M56 implication:** report answer-order variance, paraphrase variance, explanation/evidence traceability, abstention quality, and counterexample response in addition to task accuracy.

## Required protocol changes for the next M56 revision

1. Add transfer_distance: within_domain, near_domain, far_domain.
2. Add analogy_granularity: lexical, feature, relational, mechanism, long_context.
3. Permit multiple adjudicated mappings and partial relation matches.
4. Add answer-order, paraphrase, role-permutation, and surface-conflict variants.
5. Separate retrieval quality from mapping quality on long-context/source-bank tasks.
6. Record human annotator agreement, adjudication decisions, and evidence spans.
7. Report robustness deltas and false-transfer rates alongside accuracy.

## References

- Stevenson, C. E., Pafford, A., van der Maas, H. L. J., & Mitchell, M. (2026). “Can Large Language Models Generalize Analogy Solving Like Children Can?” *Transactions of the Association for Computational Linguistics*, 14, 612–626. https://aclanthology.org/2026.tacl-1.28/
- Das, M., & Balke, W.-T. (2025). “From Prototypical to Relational: How LLMs Navigate Complex Analogies.” *Proceedings of INLG 2025*, 465–485. https://aclanthology.org/2025.inlg-main.28/
- Wu, S., Zhang, T., Wang, H., Lu, Y., Yang, J., Tang, J., & Bai, Z. (2026). “A Systematic Review of Analogy Generation and Evaluation: Methods, Metrics, and Challenges.” *Findings of EMNLP 2026*, 9710–9734. https://aclanthology.org/2026.findings-emnlp.463/
- Lewis, M., & Mitchell, M. (2025). “Evaluating the Robustness of Analogical Reasoning in GPT Models.” *Transactions on Machine Learning Research*. https://openreview.net/forum?id=t5cy5v9wph
- Mitchell, M. (2026). “On Evaluating Abstraction and Analogy in Humans and Machines.” *Current Directions in Psychological Science*, 35(3), 140–147. https://doi.org/10.1177/09637214261433528

## Limitations

This is a literature synthesis, not a reproduction of these experiments. M56 has not yet run Transformer baselines, human analogy studies, or cross-domain LLM comparisons. The benchmark changes above are requirements for future data and adapters, not claims of measured performance.
