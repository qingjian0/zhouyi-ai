# Zhouyi-AI 统一路线图

本路线图与 [统一认知架构 v1](docs/MASTER_ARCHITECTURE_V1_2026-11-11.md) 配套。研究分支状态见 [集成登记册](docs/INTEGRATION_REGISTRY_V1_2026-11-11.md)。

| 阶段 | 目标 | 主要交付 | 退出门槛 |
|---|---|---|---|
| P0 | 统一架构与权威所有权 | 架构、DTO、模块登记册、ADR | 不再有重复账本/状态机/调度器定义 |
| P1 | 可运行认知闭环 | E09/E12-A6/E12-A20 适配、ZPCM 最小持久化、SROK、CSG-GCR | 端到端预测提交—证据揭示—修订—持久化测试通过 |
| P2 | 可学习结构认知 | 角色绑定、高阶评分、RSDN 状态更新 | 独立 OOD、消融、预算匹配基线 |
| P3 | 易象/类象算子学习 | Yixiang、XSL、E10/E13 | 关系保持、反例拒绝、随机先验消融 |
| P4 | 记忆与自主调度 | ZPCM/DCMF、CSL、MCRL、Hyper-Speed | 增量更新、恢复、预算/安全门控 |
| P5 | 非 Transformer 后端比较 | SSM/RWKV/xLSTM/图超图/EBM 等 | 统一任务、参数/FLOPs/延迟/RAM 对照 |
| P6 | 语言与多模态接口 | 解析、表达、工具、多模态 grounding | 分开报告内核、解析器、解码器贡献 |
| P7 | 移动端部署 | 磁盘优先记忆、有限工作集、量化和调度 | 目标设备长时压力测试与恢复验证 |

## 当前执行状态（2026-11-11）

- 主路线：非 Transformer 原生认知；Transformer 保留为可选语言接口和对照基线。
- P0 架构规范已合入 E09 集成分支，main 保持不变。
- P1 已集成 SROK-0 确定性组合内核与 N0.10 可学习评分器；候选池截断已作为独立不完整状态报告。
- SROK-0、N0.10 可学习评分器、候选池截断报告、SROK→E12-A6 生命周期投影、SROK→E09 prequential loop 已进入 E09 集成分支；相关完整 CI 均通过。
- 当前已打通可信单进程参考闭环：SROK 预测 → E09 durable commit → SUPPORT reveal → batch refit → 版本事件持久化；LOCKED_TEST 不进入学习更新。
- P1 仍未完成：ZPCM/工作集的认知记忆投影、CSG-GCR 全局协调接入、进程级 evaluator/learner 隔离、崩溃恢复与事务 outbox 尚未完成。
- N0.10 当前训练数据有 unary 捷径，不能宣称三阶/高阶能力已验证；先完成 pairwise-preserving 高阶必要性基准。
- PR #202 已合入本 E09 集成分支：增加 digest-verified observation payload vault、SROK/E09 learner checkpoint、可信单进程 episode resume；这补齐了单进程崩溃恢复切片，但不等于 evaluator/learner 进程隔离或事务 outbox 已完成。
- ZPCM 已有 E09 生命周期投影与通用检索标签脱敏；内部 learner snapshot / ledger checkpoint 不进入通用记忆包。尚需验证重放一致性、投影重建、事务 outbox 与移动设备资源。
- P1 当前剩余硬门槛：CSG-GCR 全局协调接入；evaluator/learner 独立进程与认证 IPC；原子提交/投递 outbox；故障注入和跨进程恢复。
- P2 当前科学门槛：N0.10 现有 unary 任务捷径仍未被排除。E02 parity probe 证明特定三变量 parity 任务对线性 unary/pairwise 假设有表示必要性，但不是学习收敛或普遍高阶优势证明；仍需 pairwise-preserving candidate-set benchmark 与匹配预算 MLP/Set/Graph 对照。
- YJ-01/YJ-04 易象算子研究保持独立研究分支；YJ-04 临时 CI PR 不代表正式集成或算子有效性。
- E09 集成分支最新 head `8b0aa2a` 的 Actions run `43001802066` 于 2026-11-11 10:13 UTC 完成，全部步骤成功；PR #149 仍为 Draft 堆叠集成 PR，未进入 main。

- 不立即启动大规模语言模型预训练。下一阶段仍以 P1 为主线。

## 执行纪律

每个阶段独立开分支、独立 CI、独立实验报告。未通过门槛不升级成熟度；失败实验保留，不通过修改指标制造成功。


## Baseline reference correction (2026-11-11)

The single source of truth for branch/commit identities is [BASELINE_MANIFEST](docs/BASELINE_MANIFEST_V1_2026-11-11.md). The E09 convergence source baseline is `e90f7eb210db456a541eb9f45ec39f64ebb934a5`. The recorded `8b0aa2a` Actions snapshot is historical and does not establish CI status for the current convergence branch HEAD. PR #202's crash-resume support is trusted single-process recovery only; process isolation, authenticated IPC, atomic cross-process outbox and end-to-end fault injection remain open P1 gates.


## CSG-GCR and typed-unification status correction (2026-11-11)

PR #208 now provides a bounded R1 coordinator candidate, but its declared gaps remain semantic deduplication, typed unification, branch-delta merge, Pareto/diversity selection, E09 integration, E12-A6 lifecycle adaptation and ZPCM persistence. PR #212 adds a standalone typed hyperedge unifier; its own specification explicitly says the coordinator is not wired to call it. Treat these as separate prototypes, not a completed integrated CSG-GCR subsystem. See [BASELINE_MANIFEST](docs/BASELINE_MANIFEST_V1_2026-11-11.md) for the live PR dependency snapshot.


## P1 lifecycle persistence progress (2026-11-11)

- PR #223 exact-head workflow `43034178683` passed: typed CSG-GCR candidates can be projected read-only into E12-A6 as OBSERVED candidates.
- PR #226 exact-head workflow `43036878778` passed: E12-A6 lifecycle events now have a scoped append-only ZPCM persistence/replay adapter. Mutations validate on a staged E12-A6 ledger, persist first, then swap; restart replays and revalidates the event stream.
- Evidence outcome/provenance strings are replaced with opaque references in lifecycle persistence. E09 remains the authority for evidence payloads and split visibility.
- Both PRs remain Draft and unmerged. This does not yet complete P1.
- Next: bind E09-verified evidence into E12-A6 without exposing LOCKED_TEST labels, connect the CSG-GCR projection to the persistent ledger, and test the full end-to-end restart path. Process isolation, authenticated IPC, and transactional outbox remain outstanding.


## P1 E09 evidence binding progress (2026-11-11)

- PR #226 exact head f4406ab9e9a8eb89329d767bfe5e11cef10964ee passed full workflow 43037972184.
- PR #227 exact head bc5114f846464c366469f08da82b1fd37c1479ef passed full workflow 43038201790.
- E09 evidence references are now checked against strict observation → prediction commit → reveal event chains, including envelope digests, scope/track/split binding, event order, and causation.
- SUPPORT maps to E12-A6 TRAIN; GATE_DEV, GATE_FINAL, and LOCKED_TEST remain isolated. Raw labels are not copied into lifecycle persistence.
- Both PRs remain Draft. Next: atomically ingest a typed CSG-GCR candidate and its verified E09 evidence into PersistentLifecycleLedger/ZPCM; reject cross-branch merges until authorization issuer verification exists.


## P1 atomic ingestion milestone (2026-11-11)

- PR #227 exact head 6a4b0dce8dd1255daaa613a2649796a07e37de85 passed workflow 43038677702.
- PR #228 exact head d68819c34275a6b69482b28a33dbeeaec8c7659e passed full workflow 43039470802.
- Single-branch typed CSG-GCR candidate evidence references can now be resolved against strict E09 reveal chains, projected into E12-A6, and atomically persisted with the candidate in ZPCM.
- Batch failure rollback, idempotent retry, and crash-after-commit replay are covered by tests. Raw labels remain in E09; ZPCM lifecycle events contain only opaque references.
- Cross-branch ingestion remains fail-closed until E09 authorization issuer verification exists. Process isolation, authenticated IPC, and cross-process transactional outbox remain separate P1 gates.


## P1 single-branch end-to-end lifecycle closure (2026-11-11)

- PR #228 exact head 8edf52c3ee83bc8063d14d249a2edc7676f1e9d8 passed full workflow 43040120573.
- PR #229 exact head 561ecc4e51c5d2af39139cb367ec0d430571ec38 passed full workflow 43040339295.
- The tested path now spans typed CSG-GCR candidate creation, strict E09 evidence-chain verification, atomic candidate/evidence persistence, E12-A6 lifecycle actions, ZPCM append-only event history, and restart/replay.
- The full tested transition path is OBSERVED → PROPOSED → DISCRIMINATION_PENDING → TRAIN_SUPPORTED → GATE_VALIDATED → CHALLENGED.
- SUPPORT-derived TRAIN, GATE_FINAL, and LOCKED_TEST evidence remain distinct; GATE_DEV cannot satisfy GATE_FINAL.
- Remaining gates: authenticated cross-branch authorization, OS-level evaluator/learner isolation, authenticated IPC, cross-process transactional outbox, and broader scientific/generalization validation. All integration PRs remain Draft and unmerged.


## Lifecycle closure and cross-branch trust boundary (2026-11-11)

- PR #229 exact head `561ecc4e51c5d2af39139cb367ec0d430571ec38`, workflow `43040339295`: success. End-to-end test covers candidate lifecycle transitions, split-role separation, raw-label redaction, and ZPCM restart/replay.
- PR #230 exact head `541ba18d790fc2b713051d5489a7543e2205c3e1`, workflow `43050136136`: success. Cross-branch composition now requires a signed E09 authorization event verified through an injected trusted issuer keyring. Unsigned scope receipts fail closed.
- Production security remains open: concrete public-key verifier deployment, key rotation/revocation, process isolation, authenticated IPC, and remote tamper-evident replication.
- No large-scale language or joint cognition training yet. Next research gate is production-grade trust/process boundaries plus measurement of native composition quality, not parameter scaling.


## Concrete E09 issuer authentication milestone (2026-11-11)

- PR #231 exact head `99249112754fb747a791c75205309313820501ed`, workflow `43050925777`: success.
- Concrete Ed25519 public-key verification now backs E09 branch-merge grants. Unknown/revoked issuers and signatures from a previous rotated key fail closed.
- An end-to-end test proves signed grant → two-branch typed composition → atomic E12-A6/ZPCM ingestion, with raw E09 labels excluded from lifecycle persistence.
- Remaining P1 production gates: trusted public-key provisioning, immutable configuration delivery and rollback control, rotation overlap/key IDs, revocation distribution, evaluator process isolation, authenticated IPC, and remote anti-rollback/tamper-evident replication.
