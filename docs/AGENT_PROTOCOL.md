# P1 Agent Collaboration Protocol

## Goal
Define a provider-neutral contract for specialist agents that can be scheduled by the P0 orchestrator. P1 separates agent collaboration from CPG-EI's internal reasoning architecture.

## Roles
- research: literature, prior art, hypothesis and evidence collection
- architecture: system decomposition, interfaces, trade-off analysis
- implementation: scoped code changes and implementation artifacts
- experiment: reproducible experiment plans, execution outputs and metrics
- review: independent correctness, safety, reproducibility and regression review

Roles are contracts, not separate model instances. Multiple roles may initially be backed by one provider, and one role may later use several providers.

## Request contract
Every request carries a stable request_id, role, objective, structured context, acceptance criteria and explicit integer budgets. The request must not contain credentials or private chain-of-thought requests.

## Result contract
Every result carries the matching request_id, status, concise summary, typed artifacts, evidence references, metrics and blockers. A completed result is not automatically accepted: artifacts must pass role-specific acceptance checks and independent review.

The protocol intentionally stores deliverables and evidence, not hidden chain-of-thought. Summaries should explain conclusions and decision-relevant rationale without exposing private internal reasoning traces.

## Authority and security
The initial registry is explicit and in-process. It does not dynamically import providers, execute shell commands, write Git refs, merge pull requests, or grant repository permissions. Implementation agents should initially produce patch artifacts in isolated workspaces; a separate policy gate should validate and apply approved patches to a task branch.

No secrets in request context, artifacts, metrics, or checkpoints. Provider credentials belong in a secret manager / runtime environment, never in manifests.

## Scheduling model
Agent requests become ordinary DAG tasks. Independent specialist work can run concurrently; synthesis depends on required upstream artifacts; review runs after synthesis or implementation. Retry policy is bounded and handler side effects must be idempotent.

## Acceptance pipeline
1. Schema validation and request/result correlation.
2. Artifact completeness against acceptance criteria.
3. Evidence traceability and source quality review.
4. Automated tests / experiment reproduction where applicable.
5. Independent review agent.
6. Human approval for repository writes or merge.

## Limitations and next steps
This is a protocol and registry, not a connected LLM provider or autonomous coding agent. Next: provider adapter interface, structured artifact store, isolated workspace runner, budget enforcement, cancellation/timeouts, and integration tests. Measure actual wall-clock throughput against the same serial task plan before claiming speedup.
