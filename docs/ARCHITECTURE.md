# Zhouyi-AI 类象认知架构 v0.4

## 总体结构

系统采用类象认知闭环，计算后端和领域知识均可替换：

1. 多模态输入适配器：文本、图像、音频、表格、传感器与 API 数据。
2. 观测/事件解析器：抽取对象、属性、事件、角色、时空信息和来源。
3. **类象认知核心**：任务条件取象、立类与边界识别、比类映射、推类迁移、证据验证和反例修订。
4. 动态语义存储：维护对象、类别假设、证据、记忆与版本。
5. 动态超图/CPG-EI/SROK 组合器：按预算生成跨位置、高阶候选结构，作为可替换计算后端。
6. 易象状态知识插件：提供阴阳、卦爻、五行及时位势变等领域状态表示和结构先验，不定义通用类象边界。
7. 并行推演器：对不同候选路径、假设和约束并行求解。
8. 全局协调器：证据去重、冲突检测、置信度校准、预算分配和拒绝控制。
9. 自组织修订控制器：依据新证据和验证结果执行 CREATE/MERGE/SPLIT/PRUNE/RETYPE，并保留版本与回滚。
10. 输出适配器：文本、结构化 JSON、代码、动作或多模态输出。

## 数据流

`Input -> Observe/Parse -> Task-conditioned Aspects -> Class Hypotheses -> Compare/Transfer -> Evidence & Counterexample Gate -> Revise -> Output`

动态超图、CPG-EI/SROK 和易象知识插件在类象闭环的相应阶段提供候选或先验；它们不是独立于类象目标的最终输出。

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
`bits[6], trigram_lower, trigram_upper, transition, learned_embedding, prior_version`

### EvidenceRecord
`id, source, span, timestamp, reliability, supports, contradicts`

所有 ID 应稳定；任何结论都应能回溯到产生它的单元、超边和证据记录。

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
