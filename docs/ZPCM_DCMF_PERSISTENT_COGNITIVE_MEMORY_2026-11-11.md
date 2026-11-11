# ZPCM / DCMF：周易原生持久认知记忆与动态记忆织构

日期：2026-11-11
状态：研究规格 / 架构提案；不是已完成的持久化引擎、训练模型或手机性能结论。
上游基线：MCRL PR #166，commit 6bb479182b916b96a4c8fca0cefc809e3027cb3f
建议 PR：Draft；不得自动合并到 main。

## 0. 摘要与核心决策

本设计提出 ZPCM（Zhouyi Persistent Cognitive Memory）作为 ZNCA 的持久认知记忆层，以 DCMF（Dynamic Cognitive Memory Fabric）作为状态组织模型。

核心命题：记忆不是历史文本的累积，也不是一个向量库；记忆是由不可静默覆盖的事件证据驱动、可增量物化、可修订、可撤回、可追溯的动态认知状态。

决策：
1. 追加式事件账本作为事实来源；观察、推断、假设、纠错、撤回均是有来源的事件。
2. 多种记忆视图从同一事件流物化，不把事件日志、关系图、语义摘要和程序经验混成一个无类型文本块。
3. 断言采用双时间语义：现实有效时间 Valid Time 与系统记录时间 Transaction Time。
4. 检索是受目标约束的多通道检索与证据裁决，不是单纯向量相似度排序。
5. 巩固、摘要、索引回收只改变派生视图，不静默删除原始证据。
6. 记忆冲突作为一等状态保存；新信息不自动覆盖旧信息。
7. 类象记忆保存结构映射、适用范围、保持关系、反例和拒绝记录，不把类比直接升级成事实。
8. 手机端采用磁盘为主、RAM 活动工作集为辅；百万事件可检索不得表述为百万 Token 原生上下文。

## 1. 问题定义

简单记忆方案的典型失效模式：
- 摘要覆盖原始事实，细节和来源丢失；
- 新事实覆盖旧事实，无法还原时间变化；
- 向量近邻将语义相似误判为事实相关；
- 记忆增长导致每轮全量扫描或全量重建；
- 关系图缺少事件来源、时间有效性和撤回传播；
- 经验只存成功案例，不保存失败条件；
- 类比只记录相似点，不记录反例与作用范围；
- 遗忘策略直接删除内容，造成不可审计；
- 检索把过多内容塞入上下文，重新引入上下文膨胀。

ZPCM 要解决的不是把所有内容放进模型，而是让模型在有限活动预算下，按目标读取可验证的必要认知状态。

## 2. DCMF：动态认知记忆织构

DCMF 不是六个互相复制的数据库，而是同一事件账本上的六种类型化投影。

| 视图 | 保存内容 | 主要问题 |
|---|---|---|
| Episodic / 事件记忆 | 原始事件、会话、观察、行动、结果 | 发生过什么？ |
| Relational / 关系记忆 | 实体、角色、关系、超边、依赖 | 谁与什么存在何种关系？ |
| Semantic / 语义记忆 | 有证据支持的稳定概念、规律、边界 | 哪些规律可跨任务复用？ |
| Procedural / 程序记忆 | 操作序列、前置条件、检查点、失败模式 | 如何完成任务？ |
| Analogical / 类象记忆 | 源域—目标域结构映射、保持项、反例、范围 | 哪些结构可以迁移？ |
| Working / 工作记忆 | 当前任务活动子图、临时假设、候选、预算 | 当前需要哪些状态？ |

工作记忆是短期活动集，不是长期存储；其内容可以由持久视图重新构建。

### 2.1 统一事件账本

建议事件类型：
- OBSERVATION_ADDED
- CLAIM_PROPOSED / CLAIM_SUPPORTED / CLAIM_DISPUTED / CLAIM_REFUTED / CLAIM_RETRACTED
- ENTITY_RESOLVED
- RELATION_ADDED / RELATION_QUALIFIED / RELATION_RETRACTED
- PROCEDURE_RECORDED / PROCEDURE_VERIFIED / PROCEDURE_FAILED
- ANALOGY_PROPOSED / ANALOGY_VALIDATED / ANALOGY_REJECTED
- MEMORY_CONSOLIDATED
- INDEX_BUILT / INDEX_INVALIDATED
- USER_CORRECTION
- POLICY_OR_CONSENT_CHANGED

事件最小字段：
- event_id、event_type、schema_version；
- subject_refs、payload_ref、source_refs；
- observed_at、recorded_at、valid_time；
- parent_event_ids、causation_id、correlation_id；
- actor、epistemic_status、integrity_hash。

约束：
- event_id 全局唯一且不可复用；
- 事件追加，不原地修改；
- 更正通过新事件表达；
- 大对象 payload 外置为内容寻址对象；
- 原始观察与模型推断必须区分；
- 来源缺失时不得伪造来源；
- 完整性哈希用于检测损坏，不用于证明内容真实。

### 2.2 双时间与断言模型

每个可变事实应表达：
- claim_id 与 proposition；
- subject / predicate / object；
- qualifiers；
- valid_from / valid_to；
- recorded_from / superseded_at；
- evidence_refs / derivation_refs；
- epistemic_status；
- confidence_calibration_ref；
- scope_conditions / counterexample_refs。

Valid Time 表示命题在现实世界适用的时间范围；Transaction Time 表示系统何时记录、修订或停止采用该断言。

置信度字段不是天然校准概率。未校准时只允许作为内部排序特征，不能直接向用户表达为概率。

### 2.3 认知状态物化

MemoryState_v = Materialize(EventLog[0..n], ProjectionVersion, PolicyVersion)。

每次事件应用产生确定性状态变更记录：
- 新增、更新、失效的断言；
- 受影响的实体、关系、超边；
- 依赖图中受影响的派生项；
- 待重建索引；
- 冲突集变化；
- 可复用的版本快照。

不允许每次事件到达都重建全库。使用依赖索引定位受影响子图，只对受影响投影增量更新。快照只是加速恢复的派生物，不能取代事件账本。

## 3. 记忆检索：目标驱动、多通道、证据裁决

### 3.1 查询输入

MemoryQuery 包含 task_goal、entity_refs、relation_patterns、time_scope、required_evidence_level、allowed_epistemic_status、source_constraints、freshness_policy、latency_budget、memory_budget 和 privacy_scope。

检索通道：
1. 精确实体/ID；
2. 词法全文；
3. 向量语义召回；
4. 关系角色与超边匹配；
5. 时间区间；
6. 因果/派生依赖反向追踪；
7. 程序结构签名；
8. 类象结构匹配；
9. 失败经验与反例。

多通道负责召回，后续统一执行证据、时间、权限、冲突和目标相关性裁决。

### 3.2 两阶段检索

阶段 A：高召回候选生成。多索引按预算执行；每条候选携带命中通道、索引版本和来源引用；每个通道有独立候选上限。

阶段 B：约束裁决与上下文编译。检查时间有效性、来源独立性、撤回/争议/过期状态、推断依赖、冲突断言；选择最小充分证据子图；生成带引用的 Memory Packet。

Memory Packet 不是任意摘要，而是有上限、可追溯、包含状态标签的任务输入包。

### 3.3 排序与完整性

候选排序可考虑目标相关性、实体/关系匹配、时间适配、证据强度、来源独立性、当前有效性、依赖完整性、反例覆盖、访问成本和冗余度。

不得将这些维度无条件压成未经校准的万能分数。采用硬约束过滤 + 多目标排序 / Pareto 选择；关键冲突保留并列候选。

查询必须返回以下之一：
- COMPLETE
- RESULT_LIMIT_REACHED
- BUDGET_EXHAUSTED
- INDEX_STALE
- PARTIAL_WITH_CONFLICTS
- NOT_FOUND_COMPLETE

NOT_FOUND_COMPLETE 只有在相关索引范围完整、预算足够、过滤条件已执行时才能返回。预算耗尽不等于不存在。

## 4. 记忆巩固、压缩与遗忘

### 4.1 巩固对象

巩固不是让模型写一段更短的摘要，而是从事件流中产生可审计派生记忆：
- 事件去重（保留所有来源指针）；
- 稳定实体解析；
- 重复关系合并为多来源支持的断言；
- 高频共现形成待验证关系假设；
- 多次程序轨迹抽象为条件化程序；
- 提取成功条件与失败边界；
- 汇总类象结构的保持关系与反例；
- 生成分层摘要作为可重建视图。

任何巩固输出都必须有 derivation_refs 指向输入事件，且带算法版本。重复出现不自动等于独立证据；同一来源的复制或转述不能伪装成多个独立来源。

### 4.2 记忆成熟度

- RAW：刚记录的事件；
- CANDIDATE：候选归纳，尚未充分验证；
- SUPPORTED：多源或重复证据支持；
- STABLE：在明确范围内经持续验证；
- DISPUTED：存在冲突；
- STALE：可能过期，需要时间检查；
- RETRACTED：已撤回，但历史保留。

### 4.3 遗忘分层

可回收：缓存、可重建向量索引、过期候选排序、冗余物化视图、低收益临时工作集、可重建中间张量。

默认不物理删除：原始证据、事件账本、纠错/撤回/冲突历史、关键程序执行记录、影响结论的类象反例。

隐私删除请求、数据保留政策和法定义务优先于一般不可变账本原则。实现必须支持受控加密销毁/删除与可审计墓碑，不能以事件不可变为理由拒绝合法删除。

巩固触发条件可包括新事件数量、实体/关系活动、任务结束、索引维护窗口、设备空闲/充电/温度，以及 MCRL 的预期价值判断。巩固必须可中断、可恢复、幂等，并使用版本化输入快照。

## 5. 易象与类象：成为记忆组织和检索机制

本节不把卦象当成分类标签，也不把古典解释直接视为事实。

### 5.1 结构记忆而非标签记忆

AnalogyMemory 至少包含：
- source_structure_ref、target_structure_ref；
- partial_mapping、role_mapping；
- relation_preservation、relation_breaks；
- scope_conditions、temporal_conditions；
- counterexamples、evidence_refs；
- operator_trace、status。

类象价值在于发现关系结构在何种条件下保持，不是把两个对象贴上同一个象征标签。

### 5.2 象、数、理的计算分工（研究假设）

- 象：结构化感知与关系模式候选；对应实体、角色、关系、形态和状态配置。
- 数：数量、次序、比例、阈值、组合约束、状态变化量；必须落到可计算变量。
- 理：约束、不变量、因果假设、适用条件、推演规则与反例检验。

只有象而没有数，容易停留在主观相似；只有数而没有理，容易拟合相关性而缺少机制；只有理而没有象，难以从复杂观察中提出候选结构。

### 5.3 阴阳、时位、变应等作为可检验结构

把传统概念转成候选算子/状态变量，而非固定真理：
- 阴阳：互补状态、资源/约束两极、显隐状态；语义由领域任务定义；
- 时：状态在时间窗口中的位置和阶段；
- 位：实体/关系在当前结构中的角色位置；
- 变：状态编辑及其触发条件；
- 应：跨节点、跨角色或跨时间的响应关系；
- 互/错/综/变：不同结构变换族，分别定义输入输出、保持不变量和失败条件。

每个易象算子均需与无先验、随机先验、通用可学习算子做消融。不能先验宣称易象算子更优。

### 5.4 类象拒绝机制

必须允许 NO_ANALOGY、INSUFFICIENT_EVIDENCE、ROLE_MISMATCH、TEMPORAL_SCOPE_MISMATCH、COUNTEREXAMPLE_FOUND、STRUCTURE_NOT_PRESERVED、BUDGET_EXHAUSTED。拒绝类象是有效认知结果。

## 6. 程序记忆：从轨迹到可验证技能

程序记忆不能只存一段成功经验文本。建议结构包含：
- procedure_id、abstract_operation_graph；
- preconditions、required_capabilities；
- input_artifact_schema、output_artifact_schema；
- checkpoints、verification_predicate；
- known_failure_modes、environment_constraints；
- success_evidence_refs、failure_evidence_refs；
- version。

重用时比较当前任务结构与程序签名，检查前置条件和环境差异，生成执行计划，验证关键步骤产物；失败则停止或回滚，不盲目重放；新轨迹更新适用范围。程序记忆应学习什么条件下可复用，而不是只学习操作序列相似度。

## 7. 手机端持久化与资源架构

### 7.1 指标必须分开

分别报告原始事件总量、可检索事件规模、关系/断言总量、索引磁盘占用、活动工作集 RAM、Memory Packet 大小、模型原生上下文窗口、单次检索延迟和能耗。

不得把磁盘上百万条事件描述成模型拥有百万 Token 原生上下文。

### 7.2 首个工程基线

优先采用成熟可嵌入、可离线运行的存储方案进行基准，不先发明数据库：
- SQLite WAL：事务、事件表、快照元数据、关系与断言索引；
- FTS5：词法全文检索；
- B-tree / partial index：实体、关系类型、角色、时间和证据索引；
- 可选向量索引：单独评估内存、磁盘、召回和延迟，不能成为唯一检索路径；
- 内容寻址 Blob：长文本、附件、图像等大对象外置；
- 小型 manifest：投影版本、索引版本、快照水位和恢复点。

这只是首个可比较基线，不是最终技术锁定。比较纯 SQLite、SQLite + 向量索引、图专用存储或紧凑自研索引。

### 7.3 热温冷分层

- HOT：当前任务活动子图、少量高频实体和短期状态，严格 RAM 上限；
- WARM：最近任务、活跃关系和近期程序经验，磁盘索引；
- COLD：完整事件账本、历史快照和低频证据，压缩存储；
- DERIVED：可重建摘要、向量、统计和候选结构，随时可失效重建。

热点提升依据近期访问、任务相关性和 MCRL 价值估计；降温依据访问衰减和内存压力。不能只按时间淘汰仍有关键依赖的证据。

### 7.4 内存约束

活动工作集采用硬预算：最大实体数、关系/超边数、候选记忆数、路径深度、Memory Packet Token 数、临时张量、检索并发和最终验证预留预算。

内存不足时依次丢弃可重建缓存、释放未选候选、持久化并卸载冷分支、缩小活动子图，最后返回部分结果或预算耗尽。不得悄悄降低证据完整性要求。

### 7.5 增量恢复

启动时读取最近一致快照，再重放其后的事件。快照记录 event_seq、水位、projection_version、schema_version、索引版本和校验值。

恢复后执行快照完整性检查、事件序列连续性检查、投影水位检查、索引陈旧检测和受影响投影增量修复。账本损坏时不得把部分状态标记为 COMPLETE。

## 8. 与 ZNCA / RSDN / CSG-GCR / MCRL 的接口

- ZNCA 提供实体、关系角色、证据、事件和类象审计基础类型；ZPCM 提供磁盘持久化、版本化状态和多视图物化。N1 内存核心不能被视为持久化实现。
- RSDN 提出状态编辑与关系状态变化候选；ZPCM 保存被接受的事件与推断依赖。训练标签区分观察变化与模型推断变化。
- CSG-GCR 从 ZPCM 获取相关子图和候选记忆；候选结构不得直接写成事实，经证据验证后才产生可提交的状态编辑事件。
- MCRL 决定何时检索、检索哪条通道、是否巩固、何时压缩或停止；ZPCM 返回检索成本、索引完整性、冲突数和证据覆盖。MCRL 不得将 BUDGET_EXHAUSTED 误判为 NOT_FOUND。

核心数据流：
Observation / Tool Result / User Correction
→ Event Ingestion
→ Append-only Event Ledger
→ Incremental Materializer
→ Episodic / Relational / Claim-Temporal projections
→ Semantic / Procedural / Analogical projections
→ Indexed Retrieval
→ Evidence & Conflict Gate
→ Memory Packet Builder
→ ZNCA / RSDN / CSG-GCR
↔ MCRL

## 9. 最小接口草案

- append_event(event) -> AppendReceipt
- materialize(from_seq, to_seq, projection_set, budget) -> MaterializeReport
- open_snapshot(snapshot_id) -> MemoryStateHandle
- query_memory(query, budget) -> MemoryQueryResult
- get_evidence(evidence_ref) -> EvidenceRecord
- trace_derivation(claim_or_memory_id) -> ProvenanceTrace
- retract_claim(claim_id, reason, evidence_refs) -> AppendReceipt
- consolidate(scope, policy, budget) -> ConsolidationReport
- evict_derived(scope, policy) -> EvictionReport
- compact_snapshot(watermark, budget) -> SnapshotReport

每个接口返回状态、实际扫描/读取数量、预算消耗、索引/投影版本、完整性标记、continuation cursor（适用时）、错误和冲突列表。

## 10. 研究假设与可证伪命题

H1：事件账本 + 增量物化在持续更新场景下，比全量重建更节省总 CPU 和 IO，同时保持相同状态语义。

H2：目标、关系、时间、证据联合检索，在长程任务上比单纯向量检索更能减少错误记忆引用。

H3：保留反例和适用范围的类象记忆，比只存正向映射更能提升跨域组合泛化与拒绝错误类比能力。

H4：分层工作集 + 按需 Memory Packet，可在固定 RAM 上限下扩大可检索历史规模，而不要求扩大模型原生上下文。

H5：事件级巩固与派生视图回收，可以降低存储开销，同时不损害来源追溯和历史查询能力。

H6：程序记忆若带前置条件、验证步骤和失败模式，比纯文本成功案例更能提高重复任务成功率。

以上均为待验证假设，不是已证实结论。

## 11. 实验计划

### E1：事件追加与恢复
生成 10K / 100K / 1M 事件；比较全量重建、增量物化、快照 + 重放；测追加吞吐、恢复耗时、CPU、IO、峰值 RAM、磁盘占用；注入中断、重复事件、乱序事件和损坏快照。

### E2：记忆检索质量
对照最近 N 条、纯关键词、纯向量、关键词 + 向量、关系/时间/证据联合检索、多通道召回 + 约束裁决。
指标：Recall@K、Evidence Precision、Temporal Accuracy、Conflict Detection、Provenance Completeness、Unsupported Memory Use、Latency / RAM / IO。

### E3：长期记忆治理
覆盖增量事实更新、矛盾陈述、用户纠错、过期事实、来源复制与伪独立证据、遗忘/回收后历史恢复、记忆删除与墓碑政策。

### E4：类象记忆
对照无类象、正向映射、正向映射 + 反例、正向映射 + 反例 + 时位条件、通用结构匹配、易象算子族。
指标：Analogy Precision、False Transfer Rate、NO_ANALOGY Precision/Recall、Scope Violation、Counterexample Recall、OOD Composition Accuracy。

### E5：移动端真实评测
报告设备型号、系统版本、存储介质、数据集、数据库版本、索引配置、模型上下文限制、冷热缓存条件。测峰值 PSS/RSS、CPU、wall-clock、IO、电量或能耗代理、过热降频、进程被杀后的恢复、1M 事件查询 p50/p95/p99。不得只用桌面模拟结果声称手机性能达标。

## 12. 失败判据

出现以下任一情况，必须判定相应设计失败或降级：
- 断言更正后无法追溯旧值；
- 撤回后仍将派生结论标记为有效；
- 不完整扫描返回 NOT_FOUND_COMPLETE；
- 巩固丢失来源或伪造来源独立性；
- 索引重建后结果与账本物化状态不一致；
- 类象映射不能保留反例和适用范围；
- 压缩后无法恢复必要证据；
- RAM 超预算且没有显式降级状态；
- 仅凭相似度把假设写成观察事实；
- 用户纠错未能传播到依赖结论。

## 13. 分阶段工程路线

- ZPCM-0：类型、事件 schema、双时间、状态标签、确定性物化协议。
- ZPCM-1：SQLite WAL 事件账本、快照、崩溃恢复和完整性测试。
- ZPCM-2：关系/时间/证据索引、游标、查询完整性语义。
- ZPCM-3：多视图增量物化与依赖失效传播。
- ZPCM-4：多通道检索和证据裁决，输出受限 Memory Packet。
- ZPCM-5：巩固、成熟度、可恢复遗忘和程序记忆。
- ZPCM-6：类象记忆、反例治理、易象算子消融。
- ZPCM-7：手机真机 10K → 100K → 1M 事件分级基准。

在 ZPCM-0 至 ZPCM-4 未完成之前，不进入“百万级手机长期记忆已实现”的宣传口径。

## 14. 本轮结论

本设计将持久记忆定义为动态认知状态基础设施，而非上下文扩容技巧。

架构边界：
- 事件账本是历史来源；
- 断言是可修订的知识；
- 视图是可重建的派生状态；
- 索引是可丢弃的加速结构；
- 工作集是受限的当前活动状态；
- Memory Packet 是送入模型的最小充分证据包；
- 类象是带范围和反例的结构假设；
- 巩固不是事实创造；
- 遗忘不是证据销毁；
- 检索不完整必须显式报告。

下一步先实现 ZPCM-0 / ZPCM-1 的确定性事件与持久化基线，再逐步接入 N1、RSDN、CSG-GCR 和 MCRL。
