# CPG-EI 架构设计 v0.3

## 总体结构

系统采用反馈闭环，不是单向流水线：

1. 多模态输入适配器：文本、图像、音频、表格、传感器与 API 数据。
2. 语义/事件解析器：抽取概念、属性、事件、角色、时空信息和来源。
3. 动态语义存储：维护节点、证据、记忆与版本。
4. 动态超图组合器：生成跨位置、高阶、稀疏组合。
5. 易象状态模块：提供可学习的状态编码、关系先验和状态转换候选。
6. 并行推演器：对不同候选路径、假设和约束并行求解。
7. 全局协调器：证据去重、冲突检测、置信度校准、预算分配。
8. 自组织控制器：依据长期收益决定 CREATE/MERGE/SPLIT/PRUNE/RETYPE。
9. 输出适配器：文本、结构化 JSON、代码、动作或多模态输出。

## 数据流

`Input -> Parse -> Semantic Units -> Candidate Hyperedges -> Parallel Reasoning -> Evidence Arbitration -> Output`

反馈：
- 推演失败可触发解析器重看输入；
- 证据冲突可触发超边拆分或关系重分类；
- 新任务反馈可更新组合策略；
- 预算不足时协调器减少候选路径；
- 结构更新只在验证门控通过后持久化。

## 模块接口草案

### SemanticUnit
`id, embedding, type, attributes, provenance, confidence, created_at`

### Hyperedge
`id, member_ids, relation_type, roles, score, evidence_ids, uncertainty, cost`

### ReasoningCandidate
`path_id, assumptions, derived_claims, evidence_ids, contradictions, confidence, compute_cost`

### YixiangState
现有易象模块的固定二值字段只作为兼容性表示，不应成为全系统状态空间的上限。新增表示无关的接口：

`StateRepresentation(id, family, cardinality, encoder_version, decoder_version, parameters, provenance)`

`RepresentationCandidate(representation_id, task_context, expected_gain, uncertainty, compute_cost, evidence_ids)`

`RepresentationDecision(selected_id, rejected_ids, defer_reason, validation_snapshot, policy_version)`

候选 family 至少包括 BINARY、TERNARY、HYBRID、LEARNED、ONE_HOT、PERMUTED；cardinality 可为任意整数 K>=2。编码器必须声明有效码、无效码、未知状态和解码失败策略。

### EvidenceRecord
`id, source, span, timestamp, reliability, supports, contradicts`

所有 ID 应稳定；任何结论都应能回溯到产生它的单元、超边和证据记录。表示决策也必须记录版本、证据和成本，以便重放与审计。

## 多状态表示选择闭环（TX-02）

1. **Propose**：并行提出二值、三值、混合、可学习和无先验表示。
2. **Encode**：将同一批语义单元编码到候选表示中，保留来源和版本。
3. **Evaluate**：在独立验证任务上测量预测质量、校准、泛化和资源成本。
4. **Arbitrate**：全局协调器按任务选择表示；证据不足时返回 DEFER，而不是强制选择。
5. **Monitor**：监测分布漂移、错误自信和负迁移。
6. **Revise**：若选择失败，回退到安全基线并重新评估候选。
7. **Audit**：记录候选、被拒绝选项、选择理由、验证快照和策略版本。

禁止使用测试集标签进行表示选择。任何表示先验都可被拒绝；不允许把《周易》或《太玄经》中的象数映射写成不可修改的硬规则。

## 运行模式

- **解析模式**：将原始输入转换为语义单元。
- **探索模式**：产生多个候选组合，扩大召回。
- **验证模式**：检查证据、反例和逻辑冲突。
- **收敛模式**：在预算内选择最有支持的候选。
- **学习模式**：离线或受控在线更新结构与参数。

## 关键工程约束

- 候选生成和路径评估需支持批处理与并行执行。
- 证据来源去重，避免同源重复证据虚增置信度。
- 图结构更新必须原子化并保留版本。
- 记忆需区分短期工作状态、长期知识和待验证假设。
- 推理过程记录可审计摘要，不要求保存模型隐藏思维链。
- 输入/输出可使用现有语言模型，但应单独测量外部 LLM 对结果的贡献，避免将其能力误算为 CPG-EI 的能力。
