## E02-I2-C Multi-Identity Event Design

### Why a separate event contract is required

The current I2-C adjudicator returns one event for one candidate and at most one prior identity. That shape is sufficient for KEEP, MODIFY, CREATE, ABSTAIN, SUSPEND, REACTIVATE and RETIRE. It cannot safely represent REPLACE, SPLIT or MERGE.

Do not add these events as branches that merely emit a label. They are graph transactions involving multiple identities, candidate relations, evidence projections and lineage edges.

### Proposed input boundary

A future multi-identity adjudicator should receive only observable data:

- CandidateObservation: opaque candidate reference, candidate signature, member/role projection, window, environment and evidence references.
- IdentitySnapshot[]: visible historical identity IDs, statuses and immutable version IDs.
- EvidencePacket[]: observable sample/window/environment/polarity/source-version/provenance.
- ObservationOpportunity[]: coverage and sampling opportunity.

The evaluator alone owns hidden identity mappings and the true transition graph. Candidate references must not encode latent identity IDs or event types.

### Event-specific proof obligations

#### REPLACE

A replacement is not simply “old identity matched poorly, new candidate matched well”. Required:
1. The old identity has sufficient, repeated negative evidence to justify termination.
2. The new candidate independently satisfies its creation criterion.
3. The old and new identities are distinguishable by continuity evidence, not merely by a similarity-score gap.
4. The new candidate's evidence does not reuse or inherit the old identity's support by default.
5. The ledger records old REPLACED, new ACTIVE, and one REPLACED_BY lineage edge atomically.

If the new candidate is supported but the old identity's termination is uncertain, propose CREATE plus ABSTAIN about the old identity; do not force REPLACE.

#### SPLIT

A split is one parent becoming at least two independently validated child relations. Required:
1. At least two distinct child candidate references.
2. Each child independently passes its own evidence threshold and Gate criterion.
3. Each child's member/role projection is explicitly derived from observations.
4. Parent evidence is projected to a child only when provenance supports the exact member/role/rule projection. No blanket inheritance.
5. The parent transitions to SPLIT, all children are created, and all SPLIT_FROM edges are written in one transaction.

If any required child fails validation, do not partially terminate the parent or create a subset of children as a SPLIT. Return ABSTAIN for the split proposal. A child that independently qualifies may later be considered as a separate CREATE.

#### MERGE

A merge is not the union of two member sets and not an average of two parent confidence scores. Required:
1. At least two distinct active parent identities.
2. Direct joint evidence that the proposed combined relation exists; independent evidence that each parent exists is insufficient.
3. The combined candidate independently passes Gate.
4. Conflicting parent evidence remains visible and cannot be averaged away.
5. All parents transition to MERGED, the child is created, and one MERGED_FROM edge records the complete parent set atomically.

If only one parent participates in the joint evidence, abstain rather than infer a merge.

### Transaction contract

Introduce a proposal object distinct from the ledger command:
- EventProposal: event type, parent identity IDs, candidate refs, evidence refs, expected prior statuses/version IDs, and an auditable rationale.
- LedgerTransaction: fully preflighted operations for identity status changes, version creation, and lineage edges.
- TransactionResult: committed event IDs or a typed rejection reason.

Preflight must validate every parent, child identity/version ID, evidence reference, role projection, and edge before any mutation. Apply must be all-or-nothing. A failed SPLIT or MERGE must leave identities, versions, edges, transitions and event ledger byte-for-byte unchanged.

### Anti-shortcut tests

- Similar members alone cannot trigger REPLACE.
- A strong new candidate cannot silently retire an old identity.
- A split child cannot inherit unrelated parent support.
- One invalid child prevents partial SPLIT writes.
- MERGE requires direct joint samples, not the concatenation of independent parent samples.
- Conflicting parent evidence forces ABSTAIN.
- Duplicate parents, duplicate child IDs, cycles and invalid version references are rejected before mutation.
- A terminal identity cannot re-enter a multi-identity transaction.
- Hidden evaluator IDs and event truth are absent from every adjudicator input type.

### Evaluation plan

The multi-identity benchmark must add hidden event episodes for REPLACE, SPLIT and MERGE, plus adversarial near-misses: replacement with near-identical members but different semantics; apparent split where only one child is independently supported; apparent merge where parent relations exist independently but no joint relation exists; partial and conflicting child/parent evidence; and insufficient sampling for one parent or child.

Report event macro-F1 and per-event precision/recall; lineage-edge precision/recall/F1; false parent termination and false child creation; evidence-provenance completeness and evidence-inheritance violations; partial-write count and graph-consistency failures; and abstention coverage/risk.

### Sequencing

1. Complete the single-identity hidden-event Train/Gate development benchmark.
2. Freeze the single-identity event rules and thresholds.
3. Implement transaction contracts and adversarial ledger tests.
4. Implement the multi-identity observation generator and evaluator-owned truth map.
5. Run Train/Gate development experiments.
6. Freeze the complete protocol before preparing a separate one-time locked Test.

Do not integrate multi-identity inference into E03 until its transaction tests and hidden-event evaluation pass.
