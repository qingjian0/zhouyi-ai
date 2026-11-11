# Zhouyi-AI 全项目收敛基线审计 v2

审计日期：2026-11-12  
审计类型：只读仓库拓扑、分支关系、PR 堆叠与架构治理审计  
工作基线：`architecture/production-trust-boundary-v1-2026-11-12` @ `7416cea5a4dc1b83ae85154e782bbf965aea76ce`  
稳定基线：`main` @ `ec77dcb3ef56f80b2a68dc23a6f1bdcbb381574f`  
E09 集成祖先：`integration/e09-v03-evidence-binding-2026-11-11` @ `e90f7eb210db456a541eb9f45ec39f64ebb934a5`

> 本文件记录审计事实和集成决策，不代表任何分支已经合并，也不代表系统达到生产级安全或 R4/R5 成熟度。

## 1. 审计结论

当前最主要的工程风险不是缺少模块，而是多个长分支、堆叠 PR 和独立研究线并存，造成代码基线、架构文档和验证状态不易区分。

本轮确认：

1. `main` 仍是早期稳定研究基线；不应以整体合并长分支的方式收敛。
2. `architecture/production-trust-boundary-v1-2026-11-12` 是从 E09 集成祖先连续推进的架构/集成候选线。
3. 安全 PR 堆叠链继续建立在该架构工作之上；最新 PR #245 head 为 `dc221a7d0b1c4e08ae0a812998464ea335a32918`。
4. `integration/zhouyi-unified-convergence-2026-11-11` 是较早的统一收敛分支，不应与新架构线直接合并；需按文件和能力选择性迁移。
5. main 上的 E13-B3 与 YJ 对称性研究增量必须保留，但不应因此把研究支线变成认知内核的强制依赖。

## 2. 已核实的 Git 拓扑

| 比较 | GitHub compare 结果 | 含义 |
|---|---|---|
| E09 集成祖先 → 架构分支 | ahead 115 / behind 0 | 架构分支从 E09 祖先连续演进 |
| main → 架构分支 | ahead 234 / behind 12 | 与 main 已分叉；不能直接整体合并 |
| main → 旧统一收敛分支 | ahead 159 / behind 12 | 旧线同样与 main 分叉 |
| 架构分支 → PR #245 head | ahead 79 / behind 0 | 安全 PR 堆叠 head 是架构分支的后继 |
| main → PR #245 head | ahead 313 / behind 13 | 最新安全堆叠 head 尚未包含 main 的全部后续提交 |

上述 ahead/behind 是 Git 提交图关系，不是 PR 数量，也不等于可无冲突合并。

## 3. 稳定主线独有的 13 个提交

共同祖先之后，main 有以下 13 个提交未包含在 PR #245 head 的共同历史中：

| 短 SHA | 提交主题 | 收敛处理 |
|---|---|---|
| `92e31361e7` | E13-B3 disagreement-driven query selection | 保留为主动查询/证据选择研究能力，评估后选择性迁移 |
| `2137900c51` | active discriminating query 与 version-space filtering 测试 | 与 E13-B3 一起迁移 |
| `0806ae2bc2` | E13-B3 独立 brute-force oracle | 与 E13-B3 一起迁移，保留独立 oracle |
| `bc6b476bb9` | E13-B3 文档 | 同步迁移 |
| `168e2d0d54` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `dffcc89684` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `7932697c1e` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `6983791646` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `b8b43926e6` | 明确目标关系对称策略 | 纳入 YJ 对称性研究契约审查 |
| `8805bbd7ff` | 有界精确群验证测试 | 纳入 YJ-10.4 验证线 |
| `d4f01fc72b` | 时间元数据传播测试 | 纳入 YJ-10.4/10.5 兼容性审查 |
| `ec77dcb3ef` | 有界群验证与持久化语义文档 | 纳入 YJ 研究文档审查 |
| `778bb7ef75` | 保留逐观测时间元数据与全局上下文 | 纳入 YJ-10.5 研究线 |

处理原则：不要把 13 个提交作为一个整体 merge 到长分支。E13-B3 是独立主动查询研究能力；YJ-10.4/10.5 是结构对称性与时间演化研究能力；四个 revert 是历史清理。分别验证、分别迁移。

## 4. 安全 PR 堆叠关系

当前可见链路：

```
PR #242  E09 signed verification receipt
  └─ PR #243  atomic receipt/nonce consumption
       └─ PR #244  E12-A6 receipt-authorized single writer
            └─ PR #245  persist authenticated writer identity
```

已核实状态：

- #242：Draft，exact-head workflow run 43076140738 成功。
- #243：Draft，exact-head workflow run 43078795252 成功。
- #244：Draft，exact-head workflow run 43080177000 成功；PR 描述报告 336 项单元测试及 E01–E02-D 流程通过。
- #245：Draft，exact-head workflow run 43085647834 已完成且成功；job 为 unit-tests。
- 这些 PR 仍然是堆叠关系；不得把子 PR 当成独立于父 PR 的可合并增量。

#245 的成功 CI 不等于生产安全验收。PR 文档仍明确保留 OS/进程隔离、认证 IPC、专用数据库写权限、HSM/KMS、外部 anti-rollback checkpoint、崩溃/负载测试等未完成项。

## 5. 独立研究线

### YJ-10.4 / YJ-10.5

- PR #247 是 YJ-10.5 Draft，堆叠于 YJ-10.4 PR #238。
- PR #246 标记为 validation-only，描述明确要求不要合并。
- YJ 研究线应作为可选结构算子研究域；精确群/自同构结果不能自动解释成语义或因果。
- 时间演化的 CONFIRMED 仅表示确定性快照持续性，不是统计置信或因果确认。
- 不自动写入永久记忆、不自动晋升算子、不绕过 E09/E12-A6。

### E13-B3

主动区分性查询属于元认知/主动学习研究能力。它应通过明确接口向 MCRL 提供信息价值候选，不应在未经契约审查时直接成为 MCRL 的第二套策略实现。

## 6. 统一架构所有权（不变）

| 责任 | 唯一权威 |
|---|---|
| 研究总纲/实验范式 | CPG-EI |
| 认知组织与状态 | ZNCA |
| 类型化工作空间 | TRLW |
| 稀疏局部组合 | SROK |
| 候选生成与全局协调 | CSG-GCR |
| 关系状态动力学 | RSDN |
| 易象算子/类象映射 | Yixiang / XSL |
| 证据提交、揭示与可见性 | E09 |
| 候选生命周期状态机 | E12-A6 |
| 持久事件源及其投影 | ZPCM / DCMF（一个权威事件源，多个派生视图） |
| 依赖失效传播 | CSL |
| 计算价值、继续/停止策略 | MCRL |
| 获准任务的 DAG 执行 | Hyper-Speed |
| 语言输入/输出 | 可插拔适配器 |

不得新建第二套证据账本、生命周期状态机、权威事件源或全局调度器。

## 7. 推荐的集成顺序

1. **冻结 main 的稳定角色**：不移动 main，不重写历史。
2. **以架构分支作为架构审查基线**：所有模块按单一所有权和契约检查。
3. **按 #242 → #243 → #244 → #245 的依赖顺序审查安全链**：保持 Draft，逐个验证 exact head；不能只看最终 PR 描述。
4. **将 main 的 E13-B3 作为独立切片迁移**：保留 oracle、测试和数据隔离。
5. **将 YJ-10.4/10.5 作为独立研究切片迁移**：不与核心运行时强耦合。
6. **逐项审计旧 unified 分支**：只迁移有唯一所有者、无重复账本/状态机、且测试可复现的能力。
7. **建立单一可运行闭环**：Observation → Grounding → TRLW → SROK → CSG-GCR → E09 → E12-A6 → ZPCM → 输出；RSDN/Yixiang 通过可插拔算子契约接入。
8. **完整验证**：全量单元测试、exact-head CI、跨模块端到端、失败/崩溃/恢复、OOD、消融和资源测量。

## 8. 本次审计的非目标

- 不批量合并 PR。
- 不把 Draft PR 转为 Ready。
- 不把架构文档完成视为运行时完成。
- 不开始全模型联合训练。
- 不宣称非 Transformer 架构已经优于 Transformer。
- 不宣称当前参考服务已达到生产级安全隔离。

## 9. 下一项工程任务

下一步不是再写一份总架构文档，而是建立**逐文件、逐测试、逐依赖的集成映射表**，重点核验：

- CSG-GCR 的 typed hyperedge / branch delta / E12-A6 adapter 是否在同一 exact head 上。
- E09 receipt / atomic consume / writer identity 是否在同一 PR 链上完整可重放。
- ZPCM 的事件源、投影、恢复与生命周期是否仍只有一个权威。
- E13-B3、YJ-10.4/10.5 是否能作为独立插件/算子域接入而不复制核心职责。
- 每个迁移项的源 SHA、目标 SHA、文件冲突、测试命令、测试结果、成熟度和回滚方式。

只有逐项完成以上映射，才允许建立最终集成 PR；最终 PR 的目标必须是经过审计的集成分支，而不是直接改写 main。


## 10. 第二轮代码级审计增量

本节基于架构分支 `7416cea5a4dc1b83ae85154e782bbf965aea76ce` 的源码与测试文件检查。

### 10.1 CSG-GCR typed partial pruning 已实现，旧文档状态滞后

源码 `prototype/typed_csg_gcr.py` 已实现：

- `_partial_typed_feasible`：只拒绝不可由后续扩展修复的单调矛盾；
- `TypedCandidateCoordinator(enable_partial_pruning=True)`：默认启用 typed partial pruning；
- 将 typed feasibility 与 branch-delta merge 检查作为有界协调器的 `partial_feasibility` 回调；
- 保留完整集合上的 typed unifier 作为最终可行性权威；
- 搜索预算耗尽仍显式返回 `BUDGET_EXHAUSTED`。

`tests/test_typed_csg_gcr.py` 已包含两类关键验证：

1. 对小型 proposal 集合穷举子集/超集，验证被剪枝的前缀不会在增加 proposal 后变成可行集合；
2. 对比启用/关闭剪枝的候选、状态完全一致，并验证剪枝减少 expanded states。

因此，旧文档 `CSG_GCR_TYPED_HYPEREDGE_BRIDGE_V0_1` 中“typed infeasible partial sets 尚未在 DFS 中剪枝”的限制已经被后续实现关闭；`CSG_GCR_MONOTONIC_PRUNING_V0_1` 的“exact-head CI pending”状态也需要按当前 PR #244 的 exact-head workflow 重新标记。PR #244 workflow run 43080177000 已完成且成功，job 为 unit-tests；PR 描述报告 336 项单元测试和 E01–E02-D 流程通过。该结论只覆盖该 exact head，不等于 R4 科学验证。

### 10.2 当前端到端闭环的准确边界

`tests/test_csg_gcr_e12a6_lifecycle_e2e.py` 与配套文档验证的是**单分支** typed candidate 路径：

`Typed CSG-GCR → E09 reveal/commit/observation 验证 → E12-A6 lifecycle bundle → ZPCM 持久化 → 新实例 replay/recovery`

该测试不能被表述为已验证多分支授权合并的完整生产闭环。跨分支结构合并、E09 授权、receipt 消费和 writer identity 是后续安全 PR #242–#245 的独立增量。

### 10.3 E09 evidence 的 world-family 来源仍需收敛

当前参考桥接函数 `resolve_e09_reveal` 接收调用方提供的 `world_family`；`ingest_typed_candidate` 也要求调用方传入 `world_family_by_evidence`，随后将其写入 E12-A6 Evidence DTO。当前 E09 reveal/commit/observation 链验证了 scope、learner track、split、query、commit digest 和事件谱系，但该 world-family 值本身并未从签名的 E09 事件字段或受信任服务端注册表中派生。

这不应被误报为标签泄漏；它是**证据域归属的来源完整性缺口**。生产接口必须改为以下二者之一：

- E09 authority 在受信任边界内从已验证的 episode/scope registry 派生 world-family；或
- 将 world-family 纳入严格 schema 的已签名 observation/reveal envelope，并在 verifier 中逐事件校验一致性。

禁止把 learner/candidate submitter 自报的 world-family 当作可信来源。measurement cost 也应明确其来源和授权边界。

### 10.4 旧 in-process authorization resolver 的部署边界

`resolve_branch_merge_authorization` 仍接收可调用的 `signature_verifier` 和可选 `now` 参数，适合作为参考实现/测试 seam，不应被部署成生产授权边界。生产路径必须走 E09 verifier service 的可信时钟、固定 issuer trust bundle、签名 receipt、audience/scope/expiry/nonce 验证，再由 E12-A6 writer 独立消费 receipt。

### 10.5 更新后的工程优先级

1. 修正上述两份 CSG-GCR 文档的成熟度/限制描述，避免文档落后于代码。
2. 将 world-family 归属移入可信 E09 服务端元数据，增加伪造/错配负向测试。
3. 对单分支端到端、跨分支授权合并、receipt 一次性消费、writer identity 持久化分别定义验收，禁止合并成一个模糊的“E2E passed”。
4. 在同一 exact head 上运行全部 CSG-GCR、E09、E12-A6、ZPCM 测试和故障恢复测试。
5. 然后再进行逐文件集成映射，不提前宣布生产级或联合训练就绪。


### 10.6 安全 receipt 链仍继承 world-family 自报问题

对 PR #245 head 的 `prototype/e09_authority_services.py` 进一步检查发现：

- `E09VerifierService.issue_verification_receipt` 从 request 读取 `candidate_evidence_world_family_by_ref`（兼容旧字段 `world_family_by_evidence`）。
- 它只验证该 mapping 的键集合与候选 evidence refs 完全相等，以及值是由下游校验的非空字符串。
- 随后将每个调用方提供的 world-family 直接传给 `resolve_e09_reveal`。
- 该值被放进 redacted evidence DTO，并由 E09 verifier 签名进入 receipt。
- E12-A6 writer 会正确验证 receipt 签名和 evidence DTO，但无法证明签名前的 world-family 来源真实。

因此，上一节所述问题**没有被 PR #242–#245 自动解决**。签名能证明 verifier 签过这份 receipt，不能证明 verifier 所依据的调用方自报 world-family 正确。这属于可信元数据来源问题，不是签名算法问题。

必须在 E09 verifier 内部完成来源绑定，优先顺序：

1. 在严格 E09 observation/reveal schema 中加入 world-family/domain ID，并让其处于事件完整性摘要及授权签名覆盖范围内；
2. 或由 E09 authority 从受信任、版本化的 episode/scope registry 派生 world-family；
3. verifier 对 observation、prediction commit、reveal 三者的 domain ID 做一致性检查；
4. receipt 只携带 verifier 派生的 domain ID；拒绝请求体覆盖该字段；
5. 增加跨 scope、跨 world-family、伪造 domain、旧 registry version、缺失 domain 的负向测试。

在此修复之前，receipt 的 cryptographic authenticity 不应被描述为所有 evidence metadata 都具有来源真实性。

### 10.7 PR #245 身份字段的成熟度边界

PR #245 将 workload ID、identity provider、authentication method 和 credential fingerprint 持久化到 authorization-consumed 事件，改善了可追责性和 replay 审计。它仍依赖部署时配置的 authenticator 真正从 mTLS peer certificate、Unix peer credentials 或等效 OS/workload 身份中派生 principal。若 authenticator 只是根据调用方可控字符串返回 principal，则身份仍只是应用层声明。

部署验收必须验证真实 transport credential → authenticated principal → method/scope authorization → durable audit event 的端到端链路，并证明 learner worker 无法直接打开 E09/ZPCM 数据库文件。


### 10.8 跟踪项

已建立 [Issue #251](https://github.com/qingjian0/zhouyi-ai/issues/251)，专门修复 world-family/domain ID 的可信来源绑定。该 issue 的验收要求包含事件 schema/registry 来源、跨 observation/commit/reveal 一致性、拒绝调用方覆盖及负向测试。此 issue 尚未实现或关闭。


### 10.9 E09 严格事件 schema 与 authority 写入边界的进一步核验

对 PR #245 exact head 的 `prototype/shared_evidence_protocol.py`、`prototype/e09_authority_services.py`、`prototype/e09_e12a6_evidence_bridge.py` 及对应测试进行逐段检查后，确认还有三个相互关联的契约缺口：

1. **v0.3 当前是必填字段校验，不是严格字段闭集。** `_validate_semantics` 对 observation、prediction_commit、evidence_reveal 主要使用 `required.issubset(payload)`，没有按事件类型拒绝未知字段；`append_event` 在 strict v0.3 下也没有强制要求与事件类型匹配的版本化 `payload_schema`。因此不能把“strict v0.3”理解为完整的 allowlist schema。新增 domain 字段必须配套 schema 版本与显式字段集合，不能只加一个可选键。

2. **Observation 尚无与 evaluator reveal 对等的窄 authority facade。** `E09AuthorityService.append_evidence_reveal` 会从 transport credential 认证 evaluator 身份并派生 actor_role，但 observation 测试和现有写入模式仍直接调用 `SQLiteEvidenceStore.append_event`（通常 actor_role 为 runner）。`SQLiteEvidenceStore` 的文档明确说明它是单进程 reference store，不是分布式 broker 或进程安全边界；其通用 append API 本身不会认证调用方。故 observation 的 domain provenance 不能仅靠“字段已进入 event digest”来证明来源可信。

3. **Prediction Commit / Reveal 的 domain 绑定尚不存在。** 当前 v0.3 只强制 observation/commit/reveal 的 `query_id`、`scope`、`split` 一致；桥接解析器也只对这三项进行跨事件比较。现有 authority 测试没有尝试通过篡改 receipt request 的 world-family 来 relabel 一个已提交的 evidence ref。

#### 推荐的最小可信数据流

以 observation 作为证据域归属的唯一锚点，不让 learner 或 receipt caller 决定 domain：

```
authenticated observation producer
    → E09 observation authority
    → trusted, versioned scope/episode registry lookup
    → immutable observation(domain_id, registry_id, registry_version)
    → learner prediction_commit (domain_id must equal observation)
    → evaluator evidence_reveal (domain_id must equal commit and observation)
    → E09 verifier derives domain from replayed events only
    → signed receipt(domain_id + provenance version)
    → E12-A6 writer verifies receipt and consumes nonce
```

实现约束：

- 新增窄的 observation authority 写入方法；domain 由服务端 registry 根据已认证 principal、episode、scope/query context 派生，不接受 learner/candidate submitter 的 domain override。
- 若 registry 暂不可用，必须 fail closed；不得从调用方请求、模型预测、branch label 或旧 DTO 静默推断。
- 为 observation、prediction_commit、evidence_reveal 定义明确的 v0.4 payload schema allowlist；domain 采用稳定 ID，而不是自由文本 world-family label。事件中同时记录 registry identity/version，保证 replay 可复现。
- prediction_commit 和 evidence_reveal 只能携带与上游 observation 相同的 domain ID；store semantic validator 与 bridge resolver 双重校验。
- receipt builder 从 E09 replay 的 observation event 派生 domain，拒绝 `world_family_by_evidence`、`candidate_evidence_world_family_by_ref` 等兼容输入；receipt 签入 domain ID、registry ID/version 和对应 observation/reveal digest。
- 保留旧 v0.3 数据的显式迁移策略：旧事件无 domain 时只能标记为 `UNATTRIBUTED_LEGACY` 并禁止跨域授权/训练晋升，除非经受信任迁移任务重新归属；不得伪造历史字段或默认归到某一 family。
- 生产部署还必须保证只有 E09 authority 能写 E09 数据库；通用 SQLite store 不得暴露给 learner/runner 进程。否则任何应用层 actor_role 或 registry 约束都可被绕过。

#### 新增负向测试矩阵

| 测试 | 预期 |
|---|---|
| learner 在 prediction_commit 中提交不同 domain_id | append 拒绝 |
| evaluator reveal domain 与 commit 不一致 | append 拒绝 |
| receipt 请求携带候选 world-family override | verifier 拒绝未知字段 |
| receipt builder 遇到缺失 observation domain | fail closed |
| observation domain 与 registry version 不匹配 | fail closed |
| registry 不可用或版本已撤销 | fail closed / 明确迁移路径 |
| 同 scope 下跨 episode / query 错绑 domain | 拒绝 |
| strict v0.4 事件出现未知 payload 字段 | 拒绝 |
| 旧 v0.3 事件尝试跨域授权 | 拒绝或显式 legacy quarantine |
| 非 authority workload 直接写 observation | transport/service boundary 拒绝 |

#### 当前成熟度判断

这是**服务契约与可信来源设计缺口**，不是已证明的远程可利用漏洞。当前本地 reference store 明确不提供跨进程安全隔离；PR #242–#245 的签名、nonce 和 writer identity 改进不能代替 observation authority、domain provenance 或 OS/IPC 隔离。该设计应作为 #251 的实现前置审查，不应在没有 registry 数据模型和兼容策略的情况下直接对现有事件追加一个 `world_family` 字段。
