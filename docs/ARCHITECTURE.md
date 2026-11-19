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


## 百万输入 / 百万连续输出扩展架构（研究规格）

本项目新增独立的超长序列研究目标，详细训练协议见 [ONE_MILLION_SEQUENCE_TRAINING.md](ONE_MILLION_SEQUENCE_TRAINING.md)。

### 目标与边界

- 输入端：完整处理最多 1,000,000 tokenizer tokens。
- 输出端：完整连续生成最多 1,000,000 tokenizer tokens。
- 两者独立验收；输入窗口支持不等于输出稳定，输出长度达标也不等于长程理解。
- 非 Transformer 序列主干优先；Tokenizer/Decoder 可保留为接口或对照，但必须单独计量。
- 普通消费级电脑与普通手机分别验收，报告真实设备、内存、吞吐、延迟和功耗。

### 逻辑组件

1. **流式循环主干**：比较 selective SSM、门控 RNN/线性递归与多尺度状态空间更新；支持分块状态续接。
2. **稀疏情景记忆**：原文/生成内容持久化，选择性写入带 token span、来源和校验摘要的记忆条目；检索证据经主干计算路径重放或融合。
3. **层级证据索引**：文档、段落、事件、概念、关系多级索引；索引不可替代原始证据。
4. **CPG-EI 认知层**：类象、关系超边、组合候选、冲突证据和可验证结构修订。
5. **持续生成控制器**：维护生成位置、全局约束、实体一致性、未解决事项、输出日志和可恢复 checkpoint。

### 数据与训练

训练必须以 tokenizer token 数而不是 JSONL 行数作为长度口径。长度课程 4K→16K→64K→256K→1M 仅用于稳定训练；最终输入和连续输出均必须在 1M 完整长度上端到端验收。训练、验证和 locked-test 按来源/文档/世界/规则族隔离。

### 主要风险

固定维度循环状态可能压缩掉精确历史；稀疏记忆的检索能力不能误算成主干内部记忆；线性复杂度不能代替长程任务评测。评估必须包含多跳联合检索、跨文档关系、矛盾识别、类象修订、组合 OOD 和百万 token 连续生成，不以单一 passkey 测试作为成功标准。
