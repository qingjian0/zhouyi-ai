# Zhouyi-AI 模块契约 v1

日期：2026-11-11  
状态：规范草案；所有权先于实现，跨模块传递不可变 DTO。

## 1. 统一基础对象

所有跨模块对象均须带 schema_version、稳定 ID、scope、created_at/recorded_at、source_refs 和 producer_version。时间字段使用明确时区或 UTC。未知字段不得被静默丢弃。

### Observation
原始观测引用、模态、来源、时间、原始跨度/区域、解析状态、权限/作用域、完整性摘要。Observation 不等于事实。

### SemanticUnit
实体/概念/事件/属性槽位，包含 type、attributes、embedding_ref（可选）、source_spans、temporal_scope、confidence 和 status。解析置信度与事实真值分开。

### Relation / Hyperedge
relation_type、ordered role bindings、polarity/direction、valid_time、scope、constraints、evidence_refs、structure_version、uncertainty。多元关系必须保留角色，不得退化成无角色的节点集合。

### CandidateProposal
proposal_id、candidate_kind、payload_ref、parent_refs、grammar_version、scope、cost_estimate、assumptions、source_refs。Proposal 只是提议，不拥有生命周期状态。

### InferenceResult
status、candidate_refs、native_result_ref、score_semantics、uncertainty、resource_counters、evidence_refs、completeness。status 至少区分 IDENTIFIED、AMBIGUOUS、INCONSISTENT、BUDGET_EXHAUSTED、ABSTAINED。分数必须声明是能量、排序分数、边际概率或校准概率，禁止混用。

### PredictionCommit / EvidenceReveal
严格绑定 episode、query、learner_track、scope、split、context_digest、commit_digest、event_digest 和 schema_version。先提交预测，后揭示标签。学习者只能接收授权 SUPPORT；GATE_DEV 和 LOCKED_TEST 只供授权评估器使用。

### StructureVersion
structure_id、version、parent_version_refs、proposal_ref、evidence_refs、lifecycle_ref、dependency_refs、content_digest。状态和状态迁移由 E12-A6 唯一拥有。

### CognitiveQuery / MemoryPacket
query_goal、required_types、time_scope、scope、budget、retrieval_policy。MemoryPacket 必须是最小充分证据包，包含引用、来源、时间、冲突和完整性标记；不得用无来源摘要替代证据。

### OperatorSpec
operator_id/version、input_signature、output_signature、preconditions、postconditions、invariants、parameters、cost_model、domain_scope、support_refs、counterexample_refs、validation_status。算子可以拒绝不适用输入。

## 2. 唯一所有权矩阵

| 领域 | 唯一权威 | 其他模块可以做什么 | 禁止 |
|---|---|---|---|
| 持久事件和认知投影 | ZPCM | 读取、请求物化 | 复制事件账本、静默覆盖事实 |
| 预测提交/证据揭示/切分可见性 | E09 | 通过协议请求提交或授权证据 | learner 自行读取 locked truth |
| 候选生命周期 | E12-A6 | 只读投影、引用版本 | 自建平行状态机 |
| 原生推理算法 | E12-A20 及各原生引擎 | 通过 adapter 输出统一结果 | 伪造 joint MAP、把 energy 当概率 |
| 结构依赖与失效传播 | CSL | 登记依赖、消费 dirty set | 管理候选生命周期 |
| 计算策略 | MCRL | 给出预算、停止和信息获取建议 | 直接执行高权限操作 |
| DAG 执行和资源调度 | Hyper-Speed | 按获准计划执行、回执 | 绕过策略授权、隐式获得 shell/GitHub 权限 |
| 关系组合 | SROK | 提议组合和评分 | 越权提交结构版本 |
| 候选全局协调 | CSG-GCR | 去重、冲突检测、约束收敛 | 更改证据原文或标签 |
| 算子定义与编码 | Yixiang | 提供有类型的算子及先验 | 把传统解释当作真值 |
| 跨域类象映射 | XSL | 提议映射、报告保持关系与反例 | 将表面相似提升为事实/因果 |
| 关系动力学 | RSDN | 提议状态差分与参数更新 | 越过证据/生命周期门控 |
| 认知状态语义 | ZNCA / TRLW | 定义统一状态与工作空间 | 再建一套持久记忆/证据账本 |

## 3. 依赖方向

推荐依赖图：

`Observation → Grounding → TRLW State → SROK Proposal → CSG-GCR → Inference Adapter → E09 Commit/Reveal → E12-A6 Lifecycle → ZPCM Projection`

横切服务：
- CSL 订阅结构版本依赖，计算失效范围；
- MCRL 决定是否继续搜索、提问或调用工具；
- Hyper-Speed 执行获准的任务 DAG；
- Yixiang/XSL 提供算子和映射候选；
- RSDN 产生带来源的状态更新候选；
- Context Compiler 只读取经授权的 MemoryPacket。

模块可以并行，但数据所有权不能并行复制。

## 4. 错误与拒绝语义

任何接口都必须区分：
- NOT_FOUND：检索完整但未找到；
- UNKNOWN：证据不足或状态未知；
- AMBIGUOUS：存在多个未能区分的候选；
- INCONSISTENT：约束或证据冲突；
- BUDGET_EXHAUSTED：预算耗尽，结果不完整；
- STALE：依赖版本已变化；
- REJECTED：输入不满足算子/策略前置条件；
- LOCKED：调用方无权访问；
- ERROR：执行失败。

不允许将 NOT_FOUND、UNKNOWN 和 BUDGET_EXHAUSTED 混为一谈。

## 5. 提交规则

1. DTO 变更必须有 schema version 和兼容策略。
2. 每个持久写入必须由唯一所有者执行。
3. 适配器保留原生结果语义，不丢弃边际分布、能量、资源计数等关键信息。
4. 任何跨模块异步交付须有幂等键、回执和恢复语义。
5. 证据、预测和测试切分必须可审计。
6. 新模块必须有契约测试、故障注入和预算耗尽测试。
