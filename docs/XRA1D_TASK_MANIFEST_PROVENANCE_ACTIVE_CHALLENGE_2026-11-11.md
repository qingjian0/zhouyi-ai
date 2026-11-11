# XRA-1d: Task Manifest, Evidence Provenance, and Active Challenge Selection

Date: 2026-11-11  
Status: reference implementation added; execution pending  
Branch: research/triadic-representation-arbitration-2026-11-11

## Scope

XRA-1d freezes the public experiment contract and adds a learner-side
challenge selector. It does not train a representation selector and does
not consume the exact partition oracle.

## Public task manifest

The manifest contains opaque task and episode identifiers, public actions,
learner-visible observation schema and representation versions, data split,
per-action measurement costs, episode horizon, challenge protocol, and
missingness semantics. Validation rejects unknown or missing fields,
duplicate actions, incomplete cost maps, invalid costs, unsupported protocol
or split values, and non-positive horizons. Learner payloads are rebuilt from
validated fields rather than forwarding arbitrary input.

## Evaluator-only separation

Latent states, true partitions, generator family/seed, true K, hidden
transition tables, and hidden outcome tables belong in evaluator fixtures
only. They are not representable as TaskManifest fields and are rejected
recursively by the learner-payload leakage guard. This is defense-in-depth,
not a security boundary against aliases or malicious serializers; separate
storage/process permissions and allow-listed serialization remain required.

## Evidence provenance

Each evidence record binds task, episode, trial, action, representation
version, observation-schema version, split, status, and measurement cost.
Mismatched versions are rejected. Missing/censored evidence is explicitly
not a matching observation and must not count toward MERGE coverage.

The reference validator does not yet enforce global trial uniqueness across
a dataset, train/dev/test task disjointness across a corpus, or cryptographic
tamper evidence. Those belong in a dataset manifest/index layer.

## Active challenge scheduler

The selector computes mutual information between learner-owned competing
hypotheses and each candidate action's predicted learner-visible outcome
distribution, then divides by declared measurement cost. It requires every
hypothesis to predict every action, respects remaining budget, supports a
minimum information-gain-per-cost threshold and abstention, and uses lexical
tie-breaking for deterministic runs.

The scheduler API has no parameter for evaluator partitions, latent state
IDs, generator labels, or oracle output. This is a one-step myopic heuristic,
not a globally optimal POMDP policy, and assumes supplied predictive
distributions are sufficiently calibrated.

## E12-A8 integration gate

The E12-A8 synthetic preliminary numbers (20 seeds) remain exploratory and
are not independently validated evidence of generalization. Integration
requires identical task manifests and action vocabularies; matched
observation budgets; charging selector computation and scheduling overhead;
identical train/development/locked-test splits; evaluator-label isolation
until after action selection; and multiple mechanism families with
uncertainty intervals.

No adaptive K or representation-selector training is authorized by this
implementation alone.

## Files and validation

- prototype/xra_task_manifest.py
- tests/test_xra_task_manifest.py
- prototype/xra_challenge_scheduler.py
- tests/test_xra_challenge_scheduler.py

Tests are authored but have not been executed in this environment. CI
execution remains required before treating these protocols as validated.
