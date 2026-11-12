# N0.10 deterministic experiment runner v1

Status: implementation draft; component-level experiment runner, not full Zhouyi-AI training readiness.

## Input contract

Use UTF-8 JSONL, one record per line:

```json
{"id":"train-0001","split":"train","rule_family":"family-A","nodes":[{"node_id":"a","node_type":"r0","features":[1.0],"tags":["eligible"],"evidence_ids":["ev-a"]},{"node_id":"b","node_type":"r1","features":[0.5],"tags":["eligible"],"evidence_ids":["ev-b"]}],"target_ids":["a","b"]}
```

Required fields: `id`, `split`, `nodes`, `target_ids`. Optional `rule_family` defaults to `unspecified`. Splits are exactly `train`, `dev`, and `locked_test`. IDs must be globally unique; node IDs must be unique within an observation; target IDs must uniquely match the ordered role list.

## Run

```bash
python -m prototype.n010_experiment \
  --dataset data/n010.jsonl \
  --checkpoint artifacts/n010-run.json \
  --feature-dim 8 \
  --roles-json '[{"name":"subject","allowed_types":["entity"],"required_tags":[]},{"name":"relation","allowed_types":["relation"],"required_tags":[]}]' \
  --epochs 30 \
  --beam-width 64 \
  --git-sha "$(git rev-parse HEAD)"
```

Resume a partial run with the same dataset and training configuration, increasing the requested total epoch count if needed:

```bash
python -m prototype.n010_experiment --dataset data/n010.jsonl --checkpoint artifacts/n010-run.json --feature-dim 8 --roles-json '...' --epochs 60 --git-sha "$(git rev-parse HEAD)" --resume
```

The runner writes an integrity-checked model checkpoint after every epoch and a JSON report after evaluation. The run bundle binds the model checkpoint to the dataset SHA-256, split IDs, rule-family IDs, role schema, hyperparameters, seed and Git SHA.

## Isolation and metrics

- Only `train` rows are passed to `LearnableSROK.fit`.
- `dev` and `locked_test` rows are evaluated after training; their target labels are not supplied to the learner.
- Locked-test labels are used only by the evaluator for final metrics.
- Reports include exact-match accuracy, coverage, abstention, budget-exhaustion rate and covered accuracy.
- Both exact product enumeration and bounded beam inference are evaluated with the same maximum expansion budget; beam width is recorded separately.
- The dataset manifest records rule families by split. When a recognized N0.10 synthetic-generator sidecar is present, the runner verifies its dataset SHA-256, checks the declared family split against the actual JSONL rows, rejects locked-test family leakage, and embeds the full generation manifest into the checkpoint-bound dataset manifest. For arbitrary datasets without that sidecar, callers remain responsible for the OOD family policy.

## Resume semantics

N0.10's current optimizer is deterministic full-batch gradient descent without momentum or adaptive optimizer state. Saving model weights, training step count, completed epoch count, loss history, dataset digest and hyperparameters is sufficient for exact epoch-boundary continuation under the same code and data. This is not a mid-epoch or minibatch resume mechanism. If Adam, momentum, dropout, shuffling or stochastic augmentation is introduced, its state and RNG state must be added to the checkpoint schema before claiming exact resume.

## Limitations

This runner is for the N0.10 structured component. It is not a language-model pretraining pipeline, does not establish general semantic reasoning, and does not certify full-model training readiness. Current evaluation uses exact structured role binding and reports both product and beam search; parameter/FLOP-matched MLP, graph, tensor and transformer baselines remain separate gates.
