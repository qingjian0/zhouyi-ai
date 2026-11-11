# Provider Adapter Contract

## Boundary
`AgentProvider.generate(ProviderRequest) -> ProviderResponse` is the only model-call
boundary. Implementations may target hosted APIs or local inference servers. The
orchestrator and agent-role protocol do not depend on a vendor SDK.

## Enforced by the shared wrapper
- Prompt character ceiling before a provider call.
- Positive output-token ceiling passed to adapters and checked against reported usage.
- Per-call timeout.
- Request ID correlation and typed response validation.
- Explicit model name and string-only non-secret metadata.

The character ceiling is a defensive payload limit, not a tokenizer-accurate token
count. Concrete adapters must translate `max_output_tokens` into the provider's
native parameter and must report usage honestly. A provider that cannot report token
usage should use a documented adapter-specific convention rather than inventing counts.

## Deliberately not implemented here
- Network transport, vendor SDKs, credential discovery, and secret storage.
- Automatic retries. Retries belong to the task scheduler because timeout does not
  prove the remote request was not billed or completed.
- Cost estimation. Cost needs provider/model-specific pricing metadata and should be
  recorded separately from token usage.
- Tool execution or repository write permissions.

Credentials must be injected by the runtime adapter from an environment/secret store;
never place them in manifests, prompts, metadata, artifacts, logs, or checkpoints.
Use mock providers for deterministic tests. A real adapter must add contract tests
for timeout, malformed responses, usage mapping, rate limits, and secret redaction.

## Acceptance
1. The same contract tests pass for mock and each concrete adapter.
2. Request IDs remain correlated end-to-end.
3. Output limits are enforced locally and mapped to native provider parameters.
4. Timeouts and provider errors surface to the scheduler without silent retries.
5. Logs contain request/model/latency/usage metadata, never credentials or hidden
   chain-of-thought.
