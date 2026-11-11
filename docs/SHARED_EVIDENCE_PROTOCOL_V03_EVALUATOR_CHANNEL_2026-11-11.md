# v0.3 Evaluator Channel: Freeze / Commit / Reveal

Status: implementation contract for the next protocol slice.

## Threat boundary

The SQLite event log is append-only and replayable, but it is not an authorization boundary. A learner process that can open the database can read evaluator payloads. The API projection defined here is defense-in-depth only; production isolation requires a trusted service to retain the database handle and expose a narrow learner interface.

## Required causal order

1. Persist the candidate structures and their immutable payload digests.
2. Append `candidate_set_freeze` with a sorted, unique candidate version list, learner track, evaluation role, and a digest derived by the store from the referenced durable structure digests.
3. Append `prediction_commit` referencing the freeze ID and repeating the track, role, and candidate-set digest.
4. Append `evaluation_reveal` only after the matching commit. It references the same freeze, track, role, and digest.

## Evaluation roles

- `GATE_DEV`: development feedback for evaluator-side analysis; never implicitly trainable.
- `GATE_FINAL`: final gate result; evaluator-only by default.
- `LOCKED_TEST`: sealed evaluation; candidate set must already be frozen and prediction committed.
- `POST_DEPLOY_AUDIT`: post-deployment audit; evaluator-only by default.

## Channel separation

- `evidence_ingest`: pre-visible TRAIN/SUPPORT; may be projected to the learner.
- `evidence_reveal`: explicitly authorized post-commit learner feedback; may be projected to the learner.
- `evaluation_reveal`: evaluator-only label; must never be represented as `evidence_reveal`, E12 support evidence, or E09 `reveal_feedback` input.
- `evaluation_attestation`: future minimal evaluator verdict, separate from the raw label.
- `challenge_release`: future policy-approved minimal challenge; never copies the raw evaluator label.

## Replay invariants

- A freeze references existing candidate structures only.
- Candidate IDs are sorted and unique; the digest binds track, role, version IDs, and immutable structure payload digests.
- A commit that participates in evaluation must reference a prior freeze and match its track, role, and digest.
- An evaluator reveal must reference that exact freeze and commit.
- A reveal cannot be used as learner support unless a separate, explicit challenge-release policy creates a new learner-visible record.
- Replay independently revalidates every link and digest.

## Projection contract

`replay_learner_projection(episode_id, learner_track)` returns only that track's observations, predictions, evidence, structures, candidates, and lifecycle actions. It does not include evaluation payloads, evaluator provenance, or other tracks' private records.

`replay_evaluator_projection(episode_id)` returns the freeze and evaluation records, including labels, for trusted evaluator use.

These projections do not protect against direct SQL access. Never mount the raw SQLite database or pass its connection to an untrusted learner. A trusted runner/service must own the connection and serialize only the learner projection.

## Acceptance tests

- Reject freeze with missing candidate, wrong track, duplicate/unsorted versions, or incorrect digest.
- Reject commit without prior freeze or with mismatched track/role/digest.
- Reject evaluation reveal without prior freeze and commit.
- Reject evaluation reveal with mismatched track/role/digest or duplicate prediction reveal.
- Confirm evaluator labels are absent from learner projection JSON and learner feedback APIs.
- Tamper with event payload and recompute the event digest; evaluator replay must still reject broken causal links.
- Preserve v0.1/v0.2 replay behavior and existing `evidence_reveal` semantics.

## Explicit non-claims

This protocol slice does not provide authenticated principals, database-level access control, process isolation, distributed transactions, or a complete challenge-release policy. `learner_track` is a namespace, not an identity credential.