# ZPCM N0.5：结构化认知计算与语言生成分离

日期：2026-11-11  
状态：研究设计 / 叠加于 N0.4；文档交付，不代表实现、训练、CI 或设备验证。  
上游：PR #174，N0.4。

## 0. 核心决策

本阶段定义 ZPCM 与语言模型之间的认知运行时边界。

核心命题：

**持久认知状态由结构化认知系统维护；任务计算直接作用于可追溯的状态、关系、证据和候选结构；语言模型只接收当前任务所需的受限认知包，负责表达、局部解释或提出待验证候选。**

语言模型不再是唯一的长期记忆载体，也不必在每轮调用时重新接收全部历史。它仍然可以参与推理，但它的上下文只是一次受预算控制的计算视图，不是系统的全部认知状态。

N0.5 不是“更长 prompt”、摘要压缩器或向量数据库包装层。它定义：
- 结构化认知查询；
- 任务驱动的认知计算计划；
- 证据与关系的最小充分工作集；
- 带来源和状态的上下文编译；
- 语言模型调用契约；
- 输出回译、验证和事件提交；
- 预算、缓存、快照和增量重算。

## 1. 必须严格区分的四种容量

| 容量 | 定义 | 主要存储/运行位置 | 是否等于模型上下文 |
|---|---|---|---|
| 持久历史容量 | 原始事件、原文、附件、操作记录可保存规模 | 磁盘/归档 | 否 |
| 有效认知容量 | 可检索、可追溯、状态有效的事实、关系、推导、程序和类象 | 持久投影与索引 | 否 |
| 活动工作集容量 | 当前任务正在计算的候选子图、证据和临时假设 | RAM/分页缓存 | 否 |
| 模型活动上下文 | 某次模型调用实际接收的 token 序列 | 模型运行时/KV cache | 是 |

产品和实验报告必须同时给出四种容量。禁止把“索引了 1M source tokens”表述为“模型一次注意力看到了 1M tokens”。

活动上下文预算也不能只看 token 数。相同 token 数可能包含不同长度的证据链、不同数量的关系和不同的多模态载荷。应同时记录 token、字节、候选数、证据数和推导复杂度。

## 2. 认知系统与语言生成器的职责分离

### 2.1 结构化认知系统负责

- 持久状态与事件历史；
- 事实、假设、冲突、未知和过期状态区分；
- 实体、关系、超边、时间和角色约束；
- 证据谱系与推导版本；
- 检索规划、候选组合和全局约束求解；
- 主动恢复、反证、反事实；
- 任务状态、程序经验和长期目标；
- 资源预算、停止条件和可恢复 checkpoint；
- 输出主张的证据验证与事件提交。

### 2.2 语言模型负责

- 将自然语言请求解析为候选任务意图；
- 对难以手工枚举的语义结构提出候选；
- 在受限上下文中解释已验证结构；
- 生成自然语言、代码、工具参数或面向用户的表达；
- 在被明确要求时提出反问或补充观察建议。

语言模型可以提议认知编辑，但不能绕过验证器直接改写持久状态。它生成的内容默认是 PROPOSAL，不是 OBSERVATION，也不是 VERIFIED_CLAIM。

### 2.3 分离不是禁止语言模型推理

允许模型在一次调用中进行局部多步推理；但系统不能把模型隐藏的内部过程当作持久事实，也不能把完整会话 transcript 当作唯一状态数据库。跨轮连续性必须来自 ZPCM 中可审计的状态与事件。

## 3. 总体运行架构

```text
User / Tool / Environment Event
            |
            v
   Intent & Task Parser
            |
            v
    Cognitive Query Builder
            |
            v
   MCRL Resource / Value Planner
            |
            v
   Cognitive Query Planner
            |
     +------+------------------+
     |                         |
     v                         v
 Memory / Evidence       Structure / Relation
 Retrieval                Computation
     |                         |
     +------------+------------+
                  v
        Constraint & Provenance
              Resolver
                  |
                  v
        Minimal Sufficient
          Cognitive Packet
                  |
                  v
        Language / Specialist
             Model Call
                  |
                  v
        Output Claim / Edit
             Extraction
                  |
                  v
       Deterministic Validator
                  |
          +-------+-------+
          |               |
          v               v
      Event Ledger     Reject / Ask /
       Append          Partial / Retry
          |
          v
   Incremental Projection
          |
          v
   New Cognitive Snapshot
```

这里的关键变化：模型调用发生在结构计算之后，而不是由模型独自决定需要回忆什么、历史是什么、哪些关系成立。

## 4. Cognitive Query：把问题编译成结构化任务

自然语言问题先转换为 CognitiveQuery 候选，不直接转换为“把相关记忆拼进 prompt”。

建议字段：
- `query_id`
- `task_id`
- `goal`
- `requested_output_contract`
- `entity_refs[]`
- `relation_patterns[]`
- `time_scope`
- `spatial_scope`
- `task_scope`
- `required_epistemic_states[]`
- `required_provenance_level`
- `need_counterevidence`
- `need_original_source`
- `risk_class`
- `latency_budget`
- `token_budget`
- `byte_budget`
- `compute_budget`
- `privacy_scope`
- `snapshot_seq`

Query Parser 可以由规则、轻量模型和主模型协作完成。解析不确定时必须保留多个 query hypothesis，或向用户澄清；不能默默把歧义压成唯一意图。

Query 必须有显式输出契约，例如：
- 只回答一个事实；
- 比较两个历史版本；
- 给出有证据支持的解释；
- 输出一个候选计划；
- 生成工具调用参数；
- 对冲突材料进行审计。

不同输出契约决定不同检索与验证路径。

## 5. Cognitive Query Plan：计划的是认知动作，不是 prompt 模板

Query Planner 输出有向无环的任务计划（首版不允许循环依赖），节点是有类型的认知动作：

- RETRIEVE_EXACT：精确实体/事件/版本查询；
- RETRIEVE_LEXICAL：关键词/FTS；
- RETRIEVE_SEMANTIC：向量候选召回；
- RETRIEVE_RELATIONAL：关系角色、超边和路径检索；
- RETRIEVE_TEMPORAL：时间范围与版本查询；
- TRACE_PROVENANCE：回溯来源与共享祖先；
- EXPAND_NEIGHBORHOOD：局部关系扩展；
- GENERATE_CANDIDATES：CSG-GCR/XSL 候选提出；
- TEST_CONSTRAINTS：硬约束与作用域验证；
- FIND_COUNTEREVIDENCE：反证检索；
- RECONSTRUCT_DERIVATION：重建必要推导谱系；
- ASK_OBSERVATION：请求用户或外部环境补充信息；
- CALL_LANGUAGE_MODEL：生成解释或输出；
- VALIDATE_OUTPUT：检查输出主张；
- COMMIT_EVENTS：追加经过授权和验证的事件。

每个计划节点声明：
- 输入引用与输出类型；
- 依赖节点；
- 预期信息收益；
- 估计 CPU/RAM/IO/token 成本；
- 访问权限与隐私约束；
- 超时和失败语义；
- 可否缓存；
- 可否安全重试；
- 结果是否可部分交付。

计划可以由 MCRL 调整优先级，但不得删除任务硬约束或安全验证步骤。

## 6. 认知计算：不必把所有操作都交给语言模型

N0.5 定义四种计算执行器：

### 6.1 确定性执行器

处理 ID 查询、时间区间、版本选择、依赖传播、类型检查、约束校验、哈希、权限和事件提交。

优势：可复现、成本低、易测试。限制：不能独自解决开放语义问题。

### 6.2 结构学习执行器

由 RSDN/XSL/CSG-GCR 提出关系、角色、变换和候选结构。输出结构化候选及模型版本、分数向量和证据引用。

优势：可在非相邻节点间组合，不必生成长篇自然语言。限制：候选仍需验证。

### 6.3 检索与索引执行器

通过 FTS、向量、实体、关系、时间、程序签名、类象结构和 provenance 索引召回候选。索引负责召回，不负责事实裁决。

### 6.4 语言模型执行器

处理歧义、复杂语义解释、自然语言生成和难以规则化的候选提出。只接收 Memory Packet，不直接接收整个持久事件账本。

执行器之间通过类型化中间表示通信，不通过彼此自由文本 prompt 串联作为唯一接口。

## 7. Memory Packet：最小充分认知包

Memory Packet 是一次模型调用的受限输入视图，包含完成任务所需的最小充分材料，而不是把全部检索结果拼接。

建议结构：

```text
MemoryPacket {
  packet_id
  query_id
  snapshot_seq
  packet_schema_version
  task_contract
  verified_facts[]
  relevant_relations[]
  derivation_summaries[]
  evidence_spans[]
  counterevidence[]
  unresolved_questions[]
  assumptions[]
  provenance_map[]
  temporal_scope
  confidence_and_status
  excluded_candidate_summary
  token_budget
  byte_budget
  packet_digest
}
```

必须保留四类状态标签：
- VERIFIED / OBSERVED；
- INFERRED；
- HYPOTHESIS；
- UNKNOWN / DISPUTED / STALE。

这些状态不可在上下文编译时被摘要抹平。

### 7.1 最小充分不是最短摘要

最小充分包需要同时满足：
1. 覆盖用户任务的必要实体、关系和时间条件；
2. 每个重要事实可回溯到证据；
3. 保留会改变结论的反证和冲突；
4. 保留适用范围、否定、例外和版本；
5. 不装入与任务无关的重复历史；
6. 不超过 token、byte、RAM 和延迟预算。

不能只按语义相似度取 Top-K，也不能只按最短文本压缩。

### 7.2 证据包选择

将证据选择视为带约束的集合覆盖/预算优化问题。每个证据片段 e 有：
- 覆盖的必要约束集合；
- 来源与版本；
- 支持/反对角色；
- 时间与作用域；
- 可信状态；
- token/byte/IO 成本；
- 与其他片段的来源相关性。

选择目标是覆盖关键约束、保持冲突可见、控制来源重复，并降低成本。可先用贪心近似与硬约束过滤，再对高风险问题使用更精细的多目标优化。

禁止把同源证据的复制件当作多个独立支持来源。

### 7.3 证据包可解释性

Packet 必须能回答：
- 为什么选入这条材料？
- 它支持还是反对哪个主张？
- 它来自哪个原始记录的哪个范围？
- 为什么排除了另一个候选？
- 当前是否仍有未解决证据？
- 是否因预算截断而遗漏了某个检索通道？

若预算不足，Packet 要标记 coverage_gap，不得伪装为完整证据集。

## 8. Context Compiler：上下文编译器

把结构化认知状态转成模型输入，应像编译器一样有明确阶段，而不是一段不可解释的 prompt 拼接代码。

### C0：规范化
将 query、任务、时间范围和输出契约规范化；绑定 snapshot_seq。

### C1：检索计划
生成多通道检索 DAG，按成本和价值排序。

### C2：候选召回
取回事实、关系、原始片段、反证、程序和类象候选。

### C3：证据裁决
执行版本、时间、权限、来源、冲突、推导完整性检查。

### C4：结构计算
必要时调用 XSL/RSDN/CSG-GCR 做关系扩展、候选组合和约束求解。

### C5：最小充分选择
选择必要证据子图；保留关键反例、未知和范围条件。

### C6：语言适配
根据模型能力与输出契约，选择结构化 JSON、短文本、表格化证据或多模态输入格式。

### C7：预算装配
执行 token/byte/多模态/延迟硬预算。优先移除冗余解释和低价值上下文，不得静默删除硬约束、反证或安全要求。

### C8：Digest 与调用
保存 packet digest、编译器版本、索引版本、模型版本和实际输入 token 计数。

### C9：输出回译
把模型输出解析为 ClaimProposal / EditProposal / ResponseDraft，不直接写入事实账本。

### C10：验证与提交
确定性验证输出主张，按权限和证据级别追加事件；未验证内容明确标记。

每阶段都要可观测、可重放、可单独测试。

## 9. 输出回译：语言不是最终认知状态

语言模型输出不能直接作为新的长期记忆。应先解析为类型化结果：

- `ResponseDraft`：面向用户的自然语言草稿；
- `ClaimProposal`：候选断言；
- `RelationProposal`：候选关系；
- `PlanProposal`：任务步骤；
- `ToolCallProposal`：候选工具参数；
- `QuestionProposal`：待澄清问题；
- `UncertaintyReport`：未知、冲突和证据缺口。

每个 Proposal 需要：
- 来源 packet_id；
- 依赖的输入引用；
- 模型和提示适配器版本；
- 输出解析版本；
- 声明的置信与不确定维度；
- 验证状态；
- 是否允许提交。

验证器至少检查：
- 主张是否有对应证据；
- 证据是否仍有效；
- 时间/范围是否一致；
- 是否存在反证或冲突；
- 是否出现 packet 中不存在的新事实；
- 是否存在 prompt injection 或不可信数据指令；
- 是否越过工具权限；
- 是否将假设误标为事实。

语言生成器可以流畅表达未知，但不能用语言流畅度替代证据。

## 10. 双通路：快速回答与深度认知

不是所有问题都需要完整的结构推演。

### 快速通路
适用：简单事实、明确指令、低风险、局部上下文足够。
- 读取当前任务状态；
- 精确检索少量记忆；
- 进行最小证据检查；
- 编译小型 Packet；
- 生成并验证输出。

### 深度通路
适用：复杂、多跳、历史冲突、长期任务、需要类象或因果解释、高风险问题。
- 多通道检索；
- provenance 与时间重建；
- 多候选结构生成；
- 反证与反事实；
- 全局约束求解；
- 预算调度；
- 分阶段验证。

MCRL 决定路由和预算。快速通路不能跳过安全、权限和必要证据检查；深度通路也不能无限运行。

## 11. Snapshot Isolation 与增量认知计算

一次查询必须绑定一致的 `snapshot_seq`，防止检索到一半时不同模块看到互相矛盾的状态版本。

规则：
- QueryPlan 创建时记录 snapshot_seq；
- 所有检索结果带 projection/index version；
- 中途到达的新事件不静默混入当前 Packet；
- 新事件可创建 follow-up delta query；
- 输出提交时检查输入版本是否仍有效；
- 若关键输入已被撤回或 superseded，必须重新验证或拒绝提交。

缓存键必须包含：
`(query_fingerprint, snapshot_seq, projection_version, index_version, policy_version, compiler_version)`

不能只按自然语言问题缓存，否则同一句问题在事实更新后可能返回旧答案。

增量重算原则：
- 仅重算受新事件影响的检索/结构子图；
- 复用未受影响的候选与 Packet 片段；
- 对受影响的来源、关系和 claim 重新验证；
- 缓存失效必须沿依赖关系传播；
- 所有缓存都可丢弃并从账本重建。

## 12. 多模型与多执行器协作

不同模型不应仅仅各自生成完整答案再投票。建议分工：
- Parser：识别任务和输出契约；
- Retriever：召回材料；
- Structural Proposer：提出关系/类象/组合候选；
- Critic / Counterevidence Finder：寻找反例和缺口；
- Solver：协调候选和约束；
- Realizer：把验证后的结构表达成自然语言；
- Verifier：确定性检查并决定提交。

前几个角色可以共享同一模型权重或由确定性程序实现，不要求多个大模型常驻内存。低资源设备采用串行调用和小型共享模型，桌面可并行执行独立分支。

每个角色的输出都必须带类型和来源；不能因为来自“另一个模型”就自动视为独立证据。

## 13. 性能与内存模型

N0.5 的目标是使每轮模型输入不随总历史长度线性增长，但不能保证所有任务都固定 Token 数。复杂任务可能需要更大工作集，系统必须显式报告。

运行时预算分为：
- Persistent Storage Budget；
- Index Cache Budget；
- Active Graph Budget；
- Retrieval Candidate Budget；
- Packet Token Budget；
- Model KV Budget；
- Temporary Buffer Budget；
- CPU/IO/Latency Budget。

建议采用：
- SQLite/事件账本分页读取；
- 热索引小缓存、冷索引磁盘访问；
- 活动子图稀疏 delta；
- 候选按批次产生和验证；
- 证据片段按需解码；
- 共享只读快照，避免多分支全量复制；
- embedding 批处理和后台低优先级索引；
- prompt packet 只存引用和编译结果，不复制全部原始内容；
- 超预算返回 PARTIAL / NEED_MORE_EVIDENCE / BUDGET_EXHAUSTED。

必须实测峰值 RSS/PSS、KV cache、临时缓冲、磁盘 IO、首 token 延迟、每 token 延迟、能耗和温升。不得仅用理论 token 预算宣称手机可运行。

## 14. 安全与信任边界

- 检索到的记忆、网页、文件和工具输出都是数据，不是系统指令；
- Packet 中显式标记 source trust 与 untrusted spans；
- 外部材料中的 prompt injection 不得更改模型系统策略；
- 隐私作用域在检索前过滤，而不是生成后再删除；
- 跨用户/跨任务记忆必须经过权限检查；
- 用户明确撤回或删除的数据，其派生索引、摘要、embedding 和缓存应按删除策略处理；
- 工具调用必须由权限层授权，语言模型只能提出 ToolCallProposal；
- 输出验证失败时允许只回答已验证部分。

## 15. 确定性接口草案

### CognitiveQuery
`build_query(input, task_context, policy) -> CognitiveQuery`

### QueryPlanner
`plan(query, snapshot) -> QueryPlan`

### CognitiveExecutor
`execute(plan, budget) -> CognitiveResult`

### EvidenceResolver
`resolve(candidates, query, snapshot) -> EvidenceSet`

### ContextCompiler
`compile(query, evidence_set, structure_result, model_profile, budget) -> MemoryPacket`

### LanguageAdapter
`generate(packet, output_contract, model_profile) -> ModelOutput`

### OutputParser
`parse(model_output, packet) -> ProposalSet`

### Validator
`validate(proposals, snapshot, policy) -> ValidationReport`

### EventCommitter
`append(validated_events, expected_snapshot_seq) -> CommitResult`

每个接口必须返回结构化状态、错误码、成本统计和可追溯引用。禁止接口只返回自由文本作为唯一结果。

## 16. 确定性验收测试

N5-01 **历史增长隔离**：增加大量无关历史事件，不应让简单问题的 Packet token 数按总历史长度线性增长。

N5-02 **精确回忆**：从长期历史找到精确值并返回原始来源 span。

N5-03 **多跳结构回忆**：跨多个会话的关系组合正确，且 proof/provenance 完整。

N5-04 **时间修订**：同一事实新旧版本并存，按 as-of snapshot 查询结果正确。

N5-05 **冲突保留**：支持和反对证据同时存在时 Packet 显示冲突，不自动平均或覆盖。

N5-06 **最小充分性**：移除冗余片段不影响正确性；移除关键证据会触发 coverage gap 或答案质量下降告警。

N5-07 **反证预算**：高风险/指定任务必须包含反证检索结果或明确的未执行原因。

N5-08 **快照隔离**：查询中途追加新事件，当前 Packet 不混入新版本；下一次查询可见新事件。

N5-09 **缓存正确性**：snapshot、policy、index 或 compiler 版本变化时，旧缓存不能错误命中。

N5-10 **模型幻觉隔离**：模型提出 Packet 外新事实，不得自动进入事实投影。

N5-11 **提示注入隔离**：检索内容中的恶意指令不能改变系统权限或系统策略。

N5-12 **预算硬限制**：token、byte、RAM、候选数、IO 和时限超限时返回准确的部分状态。

N5-13 **部分答案**：只验证部分主张时，只输出已验证部分并明确未决项。

N5-14 **增量重算**：一个来源变化只使相关 Packet 缓存失效，不清空无关缓存。

N5-15 **重放一致性**：相同账本快照、策略、索引和编译器版本可重放出一致 Packet digest。

N5-16 **低资源降级**：内存压力升高时减少并发、分页和活动候选，不丢失持久状态。

## 17. 基准与对照实验

至少比较：
1. Full Transcript：历史全量拼接（只作为小规模对照，不用于大规模部署）；
2. Rolling Summary：滚动摘要；
3. Vector RAG：单一向量召回；
4. Hybrid RAG：关键词+向量+元数据；
5. Structured Memory：实体/关系/时间/provenance 检索；
6. ZPCM + Context Compiler：结构检索、约束裁决、最小充分 Packet；
7. ZPCM + CPG-EI + MCRL：增加结构推演与价值调度。

任务集：
- 精确细节回忆；
- 跨会话多跳推理；
- 旧事实修订；
- 冲突证据；
- 非相邻关系组合；
- 类象迁移；
- 反事实与反证；
- 长期任务状态；
- prompt injection；
- 大量干扰历史；
- OOD 组合；
- 预算耗尽和部分交付。

指标：
- Answer Accuracy / Verified Claim Accuracy；
- Evidence Recall / Precision；
- Provenance Completeness；
- Conflict Detection；
- Temporal Correctness；
- Packet Sufficiency；
- Packet Redundancy；
- Input Tokens per Verified Claim；
- Peak RSS/PSS；
- KV Cache Bytes；
- Disk IO；
- P50/P95 latency；
- Energy per verified answer；
- False Memory / False Commit Rate；
- Incremental Recompute Ratio。

最关键指标不是“每轮 token 最少”，而是：
**在同等任务正确率和证据覆盖率下，最小化模型输入、峰值内存、延迟与能耗。**

## 18. 失败判据

出现以下情况不得宣称 N0.5 有效：
- Packet 变小但关键证据召回明显下降；
- 答案更快但未经验证主张增加；
- 历史总量增加仍导致每轮 prompt 线性增长；
- 缓存使用旧 snapshot 导致过期答案；
- 模型输出绕过验证器写入事实；
- 只用向量相似度决定事实状态；
- 反证和冲突在编译时被摘要丢失；
- 手机端峰值内存/IO/温升超预算；
- 复杂任务性能提升仅来自扩大 token budget；
- 同等预算下没有优于摘要或 Hybrid RAG 的可重复收益。

## 19. 分阶段工程实施

- N0.5-A：定义 CognitiveQuery、QueryPlan、MemoryPacket schema；
- N0.5-B：Context Compiler 确定性管线；
- N0.5-C：输出 Proposal Parser 与验证/事件提交隔离；
- N0.5-D：snapshot isolation、缓存键和增量失效；
- N0.5-E：快速/深度双通路与 MCRL 调度；
- N0.5-F：完整 benchmark、压力测试和移动端测量。

优先先做确定性最小闭环：查询 -> 计划 -> 检索 -> 证据裁决 -> Packet -> 假模型输出 -> 验证 -> 事件追加。不要一开始就训练新的大型语言模型。

## 20. 与上游模块的边界

- ZPCM N0.1：不可变事件账本和确定性投影；
- ZPCM N0.2：双时间 ClaimVersion；
- ZPCM N0.3：多重依据、增量真值维护；
- ZPCM N0.4：主动恢复、溯因与再推演；
- ZPCM N0.5：认知查询、结构计算运行时、上下文编译、语言接口；
- DCMF：多视图持久记忆；
- XSL/E13/YXO：类象发现与易象结构算子；
- RSDN：关系状态变化候选；
- CSG-GCR：候选组合和全局约束；
- MCRL：资源调度、动作价值与停止；
- Language Adapter：表达与局部语义候选；
- Validator：确定性裁决和事件提交。

任何语言模型、检索器或候选生成器都不得绕过 ZPCM 事件账本改变持久认知状态。

## 21. 完成边界

本文件是架构研究设计，不是已实现系统。

N0.5 原型完成至少需要：
1. 类型化 CognitiveQuery / QueryPlan / MemoryPacket；
2. 可重放 Context Compiler；
3. snapshot isolation；
4. 预算感知证据选择；
5. 输出提案解析；
6. 验证器和事件账本提交；
7. 增量缓存失效；
8. 16 项确定性测试；
9. 与摘要、向量 RAG、Hybrid RAG 的基线比较；
10. 普通计算机与目标手机的资源实测。

最终产品必须分别展示持久历史规模、有效认知容量、活动工作集规模和本次模型 token 数。N0.5 不宣称原生 1M Attention，也不以外部检索冒充模型原生上下文。

## 22. 核心结论

长期连续认知不应依赖无限增长的对话上下文，而应依赖一个可持久化、可修订、可追溯、可计算的认知状态系统。

语言模型是系统中的重要计算器和表达器，但不再等同于整个认知系统。ZPCM 负责保存状态，CPG-EI 负责结构认知，MCRL 负责选择计算，Context Compiler 负责把必要认知编译给模型，Validator 负责阻止未经证实的输出污染持久状态。

这才是“百万级有效历史、有限活动内存、持续认知”的工程路径。
