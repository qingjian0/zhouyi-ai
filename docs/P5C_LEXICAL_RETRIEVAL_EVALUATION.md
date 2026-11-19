# P5-C lexical retrieval evaluation

Status: deterministic evaluation harness; results are only as representative as
the supplied relevance labels and query cases.

## Metrics

`evaluate_lexical_retrieval` evaluates a fixed set of queries with explicit
relevant candidate record IDs. It reports macro-averaged recall@k,
precision@k, MRR, hit rate, mean candidate scans, scan-budget exhaustion count,
and mean serialized MemoryPacket bytes.

An explicit no-memory baseline returns zero retrieval recall, precision, MRR,
and hit rate. It is a retrieval ablation baseline only; it does not claim that
a language model without memory has zero task accuracy.

## Interpretation boundaries

- The current retriever is lexical overlap (Latin/digit terms and CJK
  unigrams/bigrams), not semantic or vector retrieval.
- Relevance labels must be independently authored/held out. The harness does
  not create labels or prevent leakage from training data.
- Synthetic fixtures validate metric implementation, not real-world retrieval
  quality.
- The harness does not evaluate downstream answer correctness, evidence use,
  analogy transfer, or cognitive gains.
- A meaningful experiment needs multiple scopes, query families, distractors,
  held-out documents, and independently reviewed relevance judgments.
