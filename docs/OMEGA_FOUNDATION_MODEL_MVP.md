# ZhouyiAI Omega foundation-model MVP

## Status and scope

Omega is the first independently initialized, trainable language-model prototype in this repository. It owns its architecture configuration and checkpoint format and does not load pretrained model weights. It is a research MVP, not yet a capable general-purpose foundation model.

## Hybrid architecture

Each Omega block combines three paths:

1. **Causal attention path** — a conventional causal self-attention baseline retained for the first hybrid milestone and for controlled ablations.
2. **Recurrent state path** — a GRU that carries information forward through the sequence without attending to future positions.
3. **Classiang workspace** — learned latent-aspect slots, per-position assignments, and a trainable slot-to-slot relation graph. A pairwise CPG-EI proposal head scores candidate slot compositions.

A learned gate mixes the three paths. The language-model head is tied to the token embedding. The training objective combines next-token cross entropy with a low-weight composition-consistency regularizer. The CPG-EI pairwise proposal head is trained to approximate a symmetrized, detached relation-graph distribution. This makes the proposal head trainable, but it is only an internal consistency signal—not semantic supervision, a verified analogy label, or proof that a proposed composition is valid.

## Causality and limitations

- Attention uses an explicit upper-triangular causal mask.
- Recurrent state is forward-only.
- Classiang slots and their relation graph are conditioned independently at each token position by the forward-only recurrent state; the workspace does not pool future token states.
- The composition head currently scores ordered slot pairs. It is not the complete non-autoregressive CPG-EI search or a validated implementation of arbitrary non-contiguous composition.
- The included character tokenizer is only for smoke tests. Production Chinese/multilingual tokenization and corpus governance are not included.
- The learned slots are not automatically meaningful 易象. Semantic grounding requires source-linked data, explicit labels or constraints, and held-out evaluation.
- The attention branch is still present. Transformer replacement is a staged research objective and must be supported by matched compute/data ablations, not assumed from this prototype.
- The current learned absolute position embedding caps context at `max_seq_len`; no 1M context or 1M output claim is made.

## Install

```bash
pip install -e '.[model]'
```

## Train a smoke model

Prepare a UTF-8 text corpus with enough characters for both train and validation splits. Then run:

```bash
python -m prototype.omega_train corpus.txt \
  --steps 500 --seq-len 128 --batch-size 8 \
  --checkpoint artifacts/omega.pt \
  --report artifacts/omega-report.json
```

The run writes:
- a model checkpoint containing config and learned state dict;
- a JSON vocabulary file beside the checkpoint;
- a JSON report with train/validation loss and limitations.

The default tokenizer treats each Unicode character as one token and is not suitable as a production tokenizer.

**Do not train on the current classical-xiang seed corpus yet.** The current `dev` snapshot has 43 candidate records and 52 claims marked unreviewed; candidate quotations are not approved training ground truth. Use `prototype.omega_corpus_gate` to export only records with reviewed claims, witness-verified text, and explicit allowlisted text/database licenses. The exporter writes a provenance manifest and refuses to treat candidate quotations as approved ground truth. The generic trainer accepts a UTF-8 text file and cannot independently verify its provenance.

## Test

```bash
pip install -e '.[model]'
python -m unittest discover -s tests -p "test_omega_model.py" -v
```

## Next research gates

1. Execute CPU and CUDA smoke tests; verify causal invariance, gradient flow, checkpoint round-trip, and training loss.
2. Add source-grounded classiang supervision and held-out relational/analogy tasks; demonstrate that the classiang path contributes beyond the attention/recurrent baselines.
3. Replace the character tokenizer with a versioned, reproducible multilingual tokenizer and build licensed, deduplicated, provenance-tracked training corpora.
4. Implement matched ablations: attention-only, recurrent-only, classiang-only, and hybrid, reporting quality, throughput, memory, and scaling curves.
5. Replace the attention path incrementally only when a non-attention alternative matches or improves quality at comparable compute.
6. Add robust checkpoint metadata, resumable optimizer state, deterministic data pipelines, evaluation suites, and inference-serving interfaces before calling this a usable base model.
