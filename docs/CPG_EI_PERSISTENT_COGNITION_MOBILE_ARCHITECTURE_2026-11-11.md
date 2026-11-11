# Beyond RAG: CPG-EI Mobile Persistent Cognition Architecture

日期：2026-11-11  
优先级：P0 架构补充  
状态：研究设计，待原型与基准验证  
关联：MOBILE_1M_EFFECTIVE_CONTEXT_ARCHITECTURE_2026-11-11.md

## 1. 为什么六层记忆仍然不够

六层存储与检索架构解决的是“材料存在哪里、如何找到”，但它没有充分解决：
- 如何跨越多次检索保持连续的任务状态；
- 如何把多个历史片段的关系保存在可计算结构中；
- 如何避免每次都把同一批历史重新编码；
- 如何在新证据到来时局部更新而非全量重算；
- 如何判断记忆缺失、过期、冲突和错误；
- 如何在有限内存下保持长程因果与约束。

仅仅将文本切块、摘要、embedding，再做 RAG，仍然是“外部搜索 + 短上下文模型”，不是完整的持续认知架构。

## 2. 必须区分四种容量

产品与研究报告必须同时报告：
1. Archive Capacity：可持久保存的原始材料规模；
2. Indexed Effective Context：可检索并带来源的历史材料规模；
3. Active Context：本轮实际装入模型/推演器的 token 数；
4. Native Attention Window：底层模型一次推理原生支持的注意力长度。

“1M+ 上下文”默认指 Indexed Effective Context，除非明确标注 Native Attention。不能用 archive 文件大小或 token 总量冒充模型原生窗口。

## 3. 新增认知状态层：Persistent Cognitive State (PCS)

在存储层与推理层之间增加 PCS，不是单一摘要，而是一个有版本、可追溯、可局部更新的状态系统。

PCS 包含六类对象：
- **Entity State**：实体及其属性的时间版本；
- **Relation State**：二元/高阶关系、方向、条件和有效期；
- **Event State**：事件、先后、因果候选和参与者；
- **Goal State**：目标、子目标、约束、进度、阻塞；
- **Belief State**：支持证据、反证、来源可信度、置信状态；
- **Procedure State**：已验证步骤、失败经验、前置条件与适用范围。

每个状态对象都必须保留：
- immutable object id、version、parent version；
- source refs 与原文 span；
- observed_at、valid_from、valid_until；
- confidence/status（observed / inferred / disputed / stale / retracted）；
- extractor / model / policy version；
- update reason 与 event id。

PCS 是“当前认知状态的可重建投影”，不是原始事实的唯一副本。原始事件日志始终是审计依据。

## 4. 从 RAG 升级为 Retrieval + State + Reasoning

每轮推理采用四步：

A. **State Read**：读取当前任务相关的 PCS 子图、goal state、未决事项和约束。  
B. **Evidence Retrieval**：按查询计划从 archive 找精确原文、反例、时间版本和相关片段。  
C. **Reasoning**：在有限工作集内进行组合、关系推演、因果候选比较和反事实检验。  
D. **State Write**：只提交带证据的新候选；经过验证后更新状态投影。

这样可以避免每轮重复扫描所有历史，同时仍可回到原文检查。

## 5. 事件驱动增量更新

禁止每轮重建整个记忆索引和全部知识图谱。

定义 append-only CognitiveEvent：
- ObservationAdded
- EntityProposed / EntityConfirmed / EntityMerged
- RelationProposed / RelationConfirmed / RelationRetracted
- GoalCreated / GoalProgressed / GoalBlocked / GoalClosed
- EvidenceAdded / EvidenceChallenged
- BeliefRevised / BeliefRetracted
- SummarySuperseded
- MemoryCompacted

每个事件只使其依赖的索引、实体、关系和摘要进入 dirty set。更新器按依赖 DAG 局部重算；定期进行完整校验和 checkpoint。事件重复投递必须幂等，事件乱序必须可检测，失败后可从 checkpoint + event log 恢复。

## 6. 多时间尺度记忆，而非单一固定摘要

- 即时状态：当前 token/动作级工作区；
- 短期状态：当前会话和任务；
- 中期状态：跨会话项目、阶段性目标、近期模式；
- 长期状态：稳定实体、知识、程序、关系与偏好；
- 潜在神经记忆：模型运行中学习的连续表示，作为补充而非唯一证据源。

遗忘/衰减只影响检索优先级，不应静默删除原始事件。用户明确纠错、撤回或删除时，必须沿来源链更新派生对象。

## 7. 神经记忆与符号/关系记忆双轨

研究双轨而不是单押一个方案：

### Neural Memory Track
评估 Titans、MIRAS、ATLAS 类测试时记忆机制，以及 SSM/线性递归模型。研究惊讶度/新颖性驱动写入、门控遗忘、分层记忆容量、可并行训练和移动推理成本。

### Structured Memory Track
采用 CPG-EI 原语、关系、高阶结构、事件、目标、证据图与版本化状态。强调可解释、可审计、精确引用和局部更新。

### Cross-Track Arbitration
神经记忆提供快速模式召回与压缩状态；结构记忆提供可追溯关系和约束；原始 archive 提供最终核验。三者冲突时，不允许神经记忆自动覆盖证据账本。

## 8. 记忆写入策略：价值、惊讶、可恢复性

候选写入分数可考虑：
- novelty / prediction error；
- future utility；
- task relevance；
- causal / relational centrality；
- source reliability；
- recurrence / reinforcement；
- storage and update cost；
- privacy sensitivity。

但分数只决定候选优先级，不决定事实真假。重要用户指令、关键决策、明确纠错和待办事项可使用确定性保留规则；神经写入策略不能自行覆盖用户显式约束。

## 9. 让成本不随历史总量线性增长：可实现边界

不能承诺对任意查询都 O(1) 或严格次线性。精确扫描全部历史、输出全部历史或全局重建都必然随数据量增长。

可实现的工程目标：
- append 新事件：摊销接近 O(1) 或 O(log N) 的索引维护，取决于索引；
- 精确 ID / 时间范围查询：B-tree/LSM 等索引路径；
- 向量召回：近似 ANN，实测 recall/latency 随 N 的曲线；
- 结构查询：限制局部子图深度/宽度，采用分区与摘要节点；
- 状态更新：依赖 DAG 的局部失效与重算；
- 单轮推理：以检索候选数 K、子图预算 G、active token budget T 为主要成本，而不是把 N 条历史全部送入模型。

目标表达为：在固定查询预算下，随着历史 N 增大，延迟和 RAM 增长尽可能缓慢，同时维持召回质量；不能只报告平均值，必须报告 P95 和退化曲线。

## 10. 记忆压缩必须可验证

摘要和压缩要有专门的 fidelity benchmark：
- 实体/数值/单位保真；
- 否定、条件、例外保真；
- 时间顺序与有效期保真；
- 因果关系不被摘要臆造；
- 多来源冲突保留；
- 罕见但关键细节可回溯；
- 压缩前后 query answer consistency；
- 删除/纠错传播到所有派生索引。

高风险事实不允许只保留摘要，必须保留可寻址原文 span。

## 11. 设备端双预算调度器

每次推理同时控制：
- RAM budget：权重、KV、activations、检索索引、临时 buffers；
- IO budget：闪存读取、索引页、压缩块解码；
- compute budget：embedding、reranking、reasoning；
- thermal/power budget：持续负载与温控；
- token budget：active prompt、检索片段和输出预留。

根据 Android memory pressure、可用内存、温度、电量、后台状态动态调整。调度优先级：当前生成 > 当前任务证据 > 关键 PCS 状态 > 后台索引/embedding/压缩。低内存时先暂停后台任务、释放可重建缓存，再缩小检索批次，不能先丢掉当前用户输入。

## 12. 必须新增的对照研究

至少比较：
A. 全历史拼接（仅小规模基线）；
B. 滑动窗口；
C. 摘要记忆；
D. 向量 RAG；
E. 混合 RAG；
F. RAG + PCS；
G. RAG + PCS + CPG-EI 推演；
H. RAG + PCS + neural test-time memory；
I. 双轨神经 + 结构记忆。

在相同设备、模型、总存储、查询预算和测试集下报告：
- exact / semantic / multi-hop recall；
- temporal consistency、contradiction handling；
- provenance correctness；
- compression fidelity；
- answer quality 与 abstention；
- P50/P95 latency、peak PSS/RSS、disk IO、energy、thermal；
- 历史规模 N 从 10K 到 10M 的扩展曲线。

测试必须包括随机位置的早期事实、多个会话跨域关系、旧事实更新、同名实体、否定、反事实、恶意 prompt injection、来源冲突和删除传播。

## 13. 具体研发里程碑

### M0：可测量
上下文拼接路径、token/KV/RSS/IO/延迟全链路 profiling；建立固定数据集与设备测试矩阵。

### M1：PCS + Event Log
实现原始事件、版本化实体/关系/目标/信念状态、来源 span、增量投影与崩溃恢复。

### M2：Budgeted Context Compiler
输入当前问题与 PCS，生成 RetrievalPlan、检索证据集和 token/byte 预算，输出可审计的 prompt manifest。

### M3：CPG-EI Cognitive Operator
对候选原语、关系、高阶结构进行受预算约束的推演，输出 evidence-linked inference，不直接写入已确认事实。

### M4：Neural Memory Adapter
接入一种神经长期记忆原型，与 PCS 做消融和冲突仲裁；未有移动内核前先在桌面验证，再迁移。

### M5：Mobile Runtime
Android 内存压力、磁盘分页、KV tiering、动态卸载/恢复、后台调度和温控。

### M6：百万到千万规模验收
在 4GB/6GB/8GB 手机上验证 1M、5M、10M source tokens 的索引、检索、跨会话推理和恢复。报告真实数据，失败设备如实记录。

## 14. 冻结原则

- 不能宣称无限上下文；存储仍受设备空间限制。
- 不能宣称任意问题都次线性；全局查询可能需要全局成本。
- 不能把 RAG 的历史检索称作原生 1M attention。
- 不能把 neural memory 状态当作无损原文。
- 不能把向量相似度当事实置信度。
- 不能把压缩摘要当来源。
- 不能把测试时更新当作自动安全学习。
- 不能让任何单一记忆通道成为无法审计的唯一真相。

## 15. 结论

最终目标不是简单的“超长 prompt”，而是手机上的 Persistent Cognition：

**原始历史可回溯、认知状态可持续、关系结构可计算、神经记忆可辅助、推理工作集有界、更新局部化、证据全程可审计。**

这才是能支撑 1M、10M 乃至更大历史规模的架构方向。其核心创新点应落在 CPG-EI 对长期记忆的结构化组织、动态关系更新和多路径认知操作，而不是重复实现一个 RAG 系统。
