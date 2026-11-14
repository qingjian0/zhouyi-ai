# E17-P0：CandidateBundle 统一契约、诊断假设与验证事务（2026-11-11）

> 状态：[研究设计与工程契约草案]。本文将 E17 的 CandidateBundle 从字段清单推进为可实现的协议。本文提交不代表 runtime、诊断器或训练系统已经实现。

## 0. 决策摘要

E17 的联合结构发现涉及 Measurement Operator、Primitive、Relation/Mechanism、Cognitive Program 四个空间。它们不能由四套互不兼容的候选 API 管理，也不能允许提议器直接修改已接受结构。

本设计采用五个相互隔离的阶段：

1. Proposal：提议器生成不可变候选包；
2. Static Validation：Schema、类型、单位、作用域、效果和依赖检查；
3. Evaluation：候选筛选、反例挑战和成本评估；
4. Independent Gate：冻结候选后，由隔离评估器作独立门控；
5. Commit：通过门控后，以事务方式发布新结构版本。

任何阶段都允许 REJECTED、DEFERRED、UNRESOLVED、BUDGET_EXHAUSTED。候选包不是知识事实，也不是可执行授权。

## 1. 统一数据模型

### 1.1 CandidateBundle

建议最小协议字段：

- bundle_id：全局唯一且稳定；
- schema_version：契约版本；
- bundle_kind：MEASUREMENT_ONLY / PRIMITIVE_ONLY / RELATION_ONLY / PROGRAM_ONLY / CROSS_LAYER；
- created_at：创建时间；
- proposer：提议器标识、版本和模型/规则版本；
- generation_method：搜索算法、种子、提示/模板版本及配置摘要；
- parent_version_refs：候选所依据的结构、算子、语法和环境版本；
- evidence_snapshot_refs：创建时可见的证据快照；
- proposed_scope：领域、对象、时间范围、环境及适用条件；
- changes：类型化变更项集合；
- dependency_delta：新增、删除、替换的依赖边；
- predicted_effects：候选预期改善及可能退化的指标；
- required_observations：验证所需数据、测量或干预；
- validation_plan：预注册指标、数据分区、预算、停止规则；
- resource_estimate：CPU/GPU 时间、峰值内存、算子调用、搜索节点和存储估计；
- risk_assessment：不确定性、影响范围、可逆性和潜在副作用；
- provenance：来源组、生成器、批次、对象、场景等谱系；
- lifecycle：状态与状态迁移事件；
- content_digest：规范化内容摘要，用于完整性和去重，不用作真实性证明。

### 1.2 ChangeItem

每个 changes 元素必须有统一外壳：

- change_id；
- target_layer：MEASUREMENT / PRIMITIVE / RELATION / MECHANISM / PROGRAM；
- operation：CREATE / REVISE / SPLIT / MERGE / RETYPE / REWIRE / SUSPEND / REPLACE；
- target_refs；
- before_version_refs；
- proposed_definition_ref；
- input_output_contract；
- preconditions；
- effects；
- scope_delta；
- dependency_delta；
- expected_metrics；
- evidence_refs；
- rollback_strategy。

不得将自由文本说明当作 executable definition。真正定义必须指向受限 DSL、声明式表达式或经审核的算子实现。

### 1.3 EvidenceSnapshot 与 Provenance

EvidenceSnapshot 需要记录不可变数据集/样本清单的版本摘要，以及样本分组规则。每条 EvidenceProvenance 至少包含：

- evidence_id；
- source_id、source_group_id；
- acquisition_batch、generator_id；
- object_id、scenario_id、environment_id；
- time_window；
- raw_observation_ref；
- annotation_protocol；
- independence_assumptions；
- known_dependencies；
- supports_or_contradicts；
- reliability、uncertainty。

独立证据量不能等于 evidence_id 数量。至少应按 source_group、generator、object 或 scenario 的依赖层级进行分组评估；当独立性假设不明确时，标记 UNKNOWN，不得默认独立。

### 1.4 ValidationReceipt

验证结果必须是独立对象，且与候选内容绑定：

- receipt_id、bundle_id、bundle_digest；
- evaluator_id、evaluator_version；
- evaluation_partition_id；
- partition_access_policy；
- metrics；
- confidence_intervals 或 uncertainty_summary；
- counterexample_refs；
- resource_actuals；
- protocol_deviations；
- decision：PASS / FAIL / INCONCLUSIVE；
- limitations；
- signed_at 或可信运行记录引用。

验证收据不得由提议器自我签发。若候选内容摘要与收据绑定的摘要不一致，收据失效。

## 2. 类型与效果系统

### 2.1 类型检查

类型检查至少包含：

- 输入/输出数据类型；
- 连续量的单位和量纲；
- 离散域、连续域和概率分布的区分；
- 时间尺度、时区和时间窗；
- 参与者角色及其基数约束；
- 适用域和前置条件；
- 不确定性表达；
- 缺失值和异常值语义；
- 资源上界或可估计成本。

类型兼容不代表语义正确。TypeCheckReceipt 只能证明声明满足静态契约，不能证明机制真实或泛化有效。

### 2.2 Effect System

程序操作必须标注效果：

- PURE：纯计算；
- READ：读取已存在结构或证据；
- MEASURE：执行测量算子；
- INFER：产生推断结果；
- PROPOSE：产生候选，不改变共享状态；
- WRITE_MEMORY：写入记忆；
- UPDATE_MODEL：更新模型参数；
- EXTERNAL_ACTION：外部世界动作。

CandidateBundle 的静态评估阶段默认只允许 PURE、READ、MEASURE、INFER、PROPOSE。WRITE_MEMORY、UPDATE_MODEL 和 EXTERNAL_ACTION 不得通过候选包隐式触发；必须由独立授权和专用执行路径控制。

## 3. 生命周期状态机

建议状态：

- DRAFT：提议器内部构造；
- PROPOSED：候选包已冻结；
- STATIC_REJECTED：静态契约失败；
- STATIC_VALID：静态检查通过；
- SCREENED：低成本筛选完成；
- CHALLENGED：反例/区分性测试完成；
- GATE_PENDING：等待独立门控；
- GATE_PASSED：独立门控通过；
- GATE_FAILED：独立门控失败；
- INCONCLUSIVE：证据不足；
- DEFERRED：预算或依赖条件不足；
- COMMITTED：新结构版本已发布；
- SUPERSEDED：被后续候选替代；
- ROLLED_BACK：当前投影已回退，但历史事件仍保留。

状态迁移必须追加事件，不允许直接覆盖历史状态。候选被拒绝不等于删除候选记录；候选通过也不等于自动激活全部子结构。

## 4. 跨层变更的归因与分阶段提交

跨层候选最容易发生归因混淆。建议将 CandidateBundle 表示为依赖 DAG：

- 每个 ChangeItem 是一个节点；
- 依赖、先决条件和验证依赖是有向边；
- 可独立验证的子集形成 change group；
- 互相依赖的变更形成不可拆分的 atomic group。

必须区分三种结论：

1. Individual effect：单个变更在其他条件固定时的独立效果；
2. Interaction effect：两个或多个变更组合后才出现的交互效果；
3. Bundle effect：整个包的总体效果。

默认验证顺序：

A. 建立原始基线；
B. 验证单项变更；
C. 对存在依赖的变更验证最小组合；
D. 验证完整 bundle；
E. 对关键交互执行消融或析因实验。

如果无法拆分归因，允许以 atomic group 整体提交，但知识记录必须标注“组合效果已验证、单项贡献未知”。不能把 bundle 的整体提升平均分配给每个变更项。

## 5. 事务提交协议

CandidateBundle 的提交采用类似乐观并发控制的流程：

1. Snapshot：固定 parent_version_refs、证据快照和当前结构版本；
2. Validate：检查所有父版本仍然是预期版本；
3. Stage：在隔离工作区应用变更，构造候选结构投影；
4. Check：运行类型、依赖、约束和资源检查；
5. Gate：读取独立 ValidationReceipt；
6. ConflictCheck：检查期间是否有父结构更新、证据撤回或依赖失效；
7. Commit：追加 CommitEvent，发布新的不可变 StructureVersion；
8. Invalidate：只标记受影响的派生结果；
9. Recompute：按依赖优先级重算；
10. Monitor：观察新版本的在线表现和资源成本。

任何冲突都必须中止提交并重新基于新快照评估。不能把旧快照的验证收据直接用于新父版本。

Rollback 不删除 CommitEvent。回退是发布一个新的结构投影版本，引用此前的已验证版本，并记录回退原因。

## 6. 独立评估与防泄漏

数据分区角色：

- Train：提议器参数和搜索策略学习；
- Discovery Validation：候选筛选和超参数选择；
- Independent Gate：候选冻结后独立门控；
- Locked Test：最终报告，learner 和候选选择器不可访问。

按 world、object、environment、mechanism、source_group 等可能相关的生成单元分组切分。仅按 observation_id 排序或随机拆分不能保证独立性。

候选数量本身也是实验自由度。必须记录：

- 本轮生成候选总数；
- 进入筛选候选数；
- 每个候选使用过的验证数据；
- 调参和筛选次数；
- 预算和停止原因；
- 独立门控是否曾用于修改候选。

一旦 Independent Gate 的结果被用于修改候选，该数据集对修改后的候选不再是独立门控集；必须更换新的独立门控数据，或明确降低证据等级。

## 7. 跨层故障定位器：竞争假设而非单标签分类

### 7.1 DiagnosisCase

输入至少包括：

- failure_id；
- failed_program_ref；
- observed_input_refs；
- expected_output_contract；
- actual_output_summary；
- residual_signature；
- affected_dependency_subgraph；
- execution_trace_ref；
- resource_trace；
- distribution_context；
- available_measurements；
- evidence_snapshot_ref。

输出为 DiagnosisHypothesis 集合，而不是一个强制标签。

### 7.2 DiagnosisHypothesis

每个假设包含：

- hypothesis_id；
- failure_layer；
- causal_story：可检验的故障解释；
- predicted_observations；
- discriminating_queries；
- supporting_evidence_refs；
- contradicting_evidence_refs；
- source_group_summary；
- posterior_or_score；
- calibration_status；
- uncertainty；
- estimated_test_cost；
- status：ACTIVE / WEAKENED / REJECTED / UNRESOLVED。

候选层级包括 Observation、Measurement、Primitive、Relation、Mechanism、Program、DistributionShift、Resource、Unknown。

注意：概率分数仅表示当前候选假设集合内的相对支持，不是现实世界真相概率。若假设集合遗漏真实故障，系统仍可能给错误假设高分。因此必须保留 Unknown，并监测诊断集合覆盖率。

### 7.3 诊断算法

1. 从失败轨迹和残差定位最小受影响依赖子图；
2. 根据依赖类型召回多个可能故障层；
3. 对每个假设生成可区分的预测；
4. 估计查询的信息价值和成本；
5. 选择最有区分力且预算可承受的测量；
6. 收集新证据并更新假设；
7. 若关键假设仍无法区分，返回 UNRESOLVED；
8. 仅将已被证据支持的最小修复写成 CandidateBundle。

可使用期望信息增益：

IG(q)=H(Hypotheses)-E_o[H(Hypotheses|o,q)]

也可使用成本敏感价值：

VOC(q)=E[ΔU|q]-λ_t C_time-λ_m C_memory-λ_r Risk

不得仅因某个假设概率最高就自动提交修复。

### 7.4 最小修复原则

若多个故障假设可以解释同一失败，优先选择：
- 影响范围最小；
- 修改层级最少；
- 预测差异最明确；
- 可逆性最高；
- 验证成本最低；
- 不会绕过其他层级的安全约束。

但最小修改不是绝对原则：若证据表明存在跨层共同原因，允许提出多层修复，并按第 4 节执行归因。

## 8. 与 E13、E16、GPOI、CGL、DCC 的接口

- E13：提供 Observation、AnalogyMap、DiscriminatingQuery、EvidenceLedger 引用；
- E16/DCH：提供 StructureVersion、Hyperedge、Dependency 和 Invalidation API；
- GPOI：提供 MeasurementOperatorCandidate、PrimitiveCandidate；
- CGL：提供 ProgramCandidate、AST、GrammarVersion、EffectSet；
- DCC：为候选生成、查询、筛选和重算分配预算；
- WSG：只激活当前诊断和候选相关的证据与结构工作集。

所有跨模块传递均使用不可变引用和版本号，不传递可被另一模块静默修改的共享对象。

## 9. 资源治理

每个 bundle 需要同时记录估算和实际成本：

- wall_clock_ms；
- cpu_time_ms；
- gpu_time_ms；
- peak_memory_bytes；
- candidate_count；
- search_node_count；
- operator_invocations；
- evidence_reads；
- graph_nodes_touched；
- recompute_count；
- storage_delta_bytes。

预算耗尽返回 BUDGET_EXHAUSTED，并保留已完成阶段和未完成阶段。部分候选结果不能标记为完整搜索结果。候选过多时优先做类型剪枝、共享子结构、等价规范化和目标相关召回，而不是无限增加搜索预算。

## 10. E17-P0 实施与验收计划

### P0-A：Schema 与序列化

- 定义 CandidateBundle、ChangeItem、EvidenceSnapshot、ValidationReceipt；
- JSON Schema 或等价强类型定义；
- schema_version 迁移策略；
- 规范化序列化与 digest 一致性测试；
- 未知字段、缺失字段、无效引用和版本冲突测试。

### P0-B：状态机与事务

- 实现合法状态迁移表；
- 状态事件 append-only；
- Snapshot / Stage / Gate / Commit / Conflict / Rollback 测试；
- 验证收据绑定候选摘要和父版本；
- 中途失败不得污染 accepted projection。

### P0-C：证据谱系

- source_group、generator、batch、object、scenario 关联；
- 相关来源攻击测试；
- 重复 evidence_id 与重复原始来源测试；
- 未知独立性不得按独立计数。

### P0-D：故障诊断最小原型

- 合成注入八类故障；
- 竞争假设生成；
- 区分性查询；
- Unknown/Unresolved；
- 诊断后只产生候选包，不直接提交。

### P0-E：安全与资源

- NaN / Inf / 负成本 / 超预算；
- 递归依赖和循环依赖；
- 超大 bundle 和恶意深度 AST；
- 预算耗尽语义；
- 效果系统拒绝未授权写入。

### 验收门槛

1. 所有候选包可规范化序列化并稳定复现 digest；
2. 不存在未经 Gate 的 accepted structure 写入路径；
3. 父版本变化时旧 receipt 无法提交；
4. 来源相关证据不会被简单计为独立支持；
5. 未知故障可以返回 UNRESOLVED；
6. 预算耗尽不会伪装成完整搜索；
7. rollback 保留全部历史事件；
8. Locked Test 不可被提议器、筛选器和诊断器读取。

## 11. 研究假设与证伪

H17-P0-1：统一 CandidateBundle 可降低跨模块接口不一致和错误提交率。

H17-P0-2：来源谱系与独立门控可降低相关证据导致的错误接受率。

H17-P0-3：竞争诊断假设加区分性查询，比单标签规则诊断具有更低的错误修复率。

H17-P0-4：跨层事务和最小变更归因可降低结构污染与错误收益归因。

证伪条件：
- 协议治理成本高于其减少的错误成本；
- 统一包导致模块耦合和序列化开销显著增加；
- 竞争假设诊断并未降低错误修复；
- 独立门控在现实数据量下无法执行或导致严重延迟；
- 事务机制无法保证失败原子性；
- 相比简单、分层的单项候选，跨层 bundle 没有可测收益。

## 12. 本文状态

本文是 E17-P0 的工程协议设计。当前未实现 CandidateBundle runtime、诊断器、事务提交器或独立评估器；未运行 P0 测试、E17 训练或真实数据实验。本文定义的验收门槛均为待实现、待验证项目。

推荐研发顺序：先 Schema/状态机/收据绑定，再证据谱系和事务提交，然后做合成故障诊断；暂不接神经提议器，也暂不进行基础模型训练。
