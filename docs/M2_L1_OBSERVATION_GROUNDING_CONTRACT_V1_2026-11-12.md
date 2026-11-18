# M2 L1 观测与语义 grounding 契约 v1

日期：2026-11-12  
状态：设计规格 / R0；不是运行时实现，不代表 M2 已完成。  
依赖：M0 内存测量、M1 原始证据流式摄取；统一架构 v1、模块契约 v1。  
目标：定义从不可变原始证据到可修订语义候选的唯一、可追溯数据边界。

## 0. 决策摘要

M2 不直接把文本摘要写成“记忆事实”。数据必须经过明确的层次：

`RawEvidence → Observation → SemanticUnitCandidate → GroundedAssertion → Relation/Hyperedge`

每一层都保留对上一层的引用和派生版本。派生结果可以新增、修订、冲突或撤回，但不得覆盖原始证据。

本规格只定义 L0/L1 的数据契约与向 L2 的输出边界；不实现语义模型、向量库、类象映射或认知推理内核。

## 1. 分层与权威所有权

| 层 | 对象 | 权威来源 | 写入规则 |
|---|---|---|---|
| L0 | RawEvidence / EvidenceChunk | M1 持久化摄取 | 原文不可变；更换输入版本产生新 document_id |
| L1a | Observation | Observation Store（待实现） | 追加式；记录解析器、模态、来源跨度与状态 |
| L1b | SemanticUnitCandidate | Grounding Pipeline（待实现） | 仅候选；可被支持、反驳、合并、拆分或拒绝 |
| L1c | GroundedAssertion / Relation | 由证据治理协议授权的语义投影 | 派生断言，不得伪装成原始观察 |
| L2 | TRLW / ZNCA 工作集 | 认知状态所有者 | 只消费有预算、有来源的结构化引用 |

约束：
- M1 继续拥有原始字节、Chunk ID、哈希和 byte span；M2 不复制原文账本。
- E09 继续拥有证据授权、预测提交/揭示和评估切分；M2 不另建证据真值状态机。
- E12-A6 继续拥有候选结构生命周期；L1 只报告解析/grounding 状态，不复制生命周期状态。
- ZPCM 继续拥有持久事件历史与可重建投影；Observation Store 若落地，必须作为 ZPCM 的受控投影/命名空间，不得成为第二个事件账本。
- 向量索引、摘要、缓存均为可重建派生视图，不拥有事实权威。

## 2. 统一事件包络

所有 L1 持久对象必须带有以下公共字段：

| 字段 | 类型/约束 | 含义 |
|---|---|---|
| schema_version | 非空版本字符串 | DTO 版本；不可依赖隐式字段顺序 |
| record_id | 稳定 ID | 对象身份；重试必须幂等 |
| record_kind | 枚举 | Observation、SemanticUnitCandidate、Assertion、Relation 等 |
| producer | 模块/模型标识 | 实际产生者 |
| producer_version | 版本 | 解析器、模型、规则或算子版本 |
| recorded_at | UTC 时间 | 系统记录时间 |
| valid_time | 可选区间 | 现实世界中声称有效的时间 |
| scope | 明确作用域 | 用户、任务、数据集、权限域或世界线 |
| source_refs | 非空引用列表 | 回到 L0 的证据定位；纯派生记录还需 derivation_refs |
| derivation_refs | 引用列表 | 产生当前记录的上游对象和版本 |
| integrity | 摘要/校验信息 | 对象内容完整性，不代表语义正确 |
| status | 类型化状态 | 不同对象使用不同状态枚举 |

时间必须区分 recorded time 与 valid time。不得用单一 timestamp 同时表示“系统何时知道”与“事实何时成立”。

## 3. L0：原始证据引用

L1 只允许引用 M1 的证据块，不把原文重新复制到语义对象中。

EvidenceRef 至少包含：
- document_id；
- chunk_id；
- content_sha256；
- byte_start、byte_end（半开区间）；
- source_version 或不可变输入版本标识；
- 可选页码、时间戳、图像区域或音视频片段定位。

引用校验必须能够确认：document_id、chunk_id、哈希和跨度均对应 M1 当前持久记录。引用失效时返回 STALE/NOT_FOUND，不得静默改绑到相似文本。

多模态证据使用 modality-specific locator：
- 文本：UTF-8 byte span；
- PDF：页号 + 页面坐标/文本跨度；
- 图像：图像版本 + 区域坐标；
- 音频：媒体版本 + 起止时间；
- 视频：媒体版本 + 时间区间 + 可选帧/区域；
- 表格：工作表、单元格或范围。

所有 locator 必须绑定原始载荷版本和完整性摘要。

## 4. L1a：Observation

Observation 表示“某个解析器从某个来源观察/提取到了什么”，不是世界事实。

必需字段：
- observation_id；
- modality；
- payload_ref（L0 EvidenceRef）；
- source_locator；
- observed_content_ref（指向原文跨度或规范化载荷，不重复持有全文）；
- extractor_id、extractor_version；
- extraction_method（规则、模型、人工、工具或融合）；
- parse_status：PARSED / PARTIAL / UNPARSEABLE / REJECTED；
- extraction_score（可选，且声明分数语义）；
- language、timestamp、speaker 等模态属性（可选）；
- source_refs 与 derivation_refs。

Observation 只能表达“检测到文本/对象/事件候选”。例如 OCR 识别出“温度 38”，只能先形成 OCR Observation；不能直接创建“某人发烧”的确认事实。

同一来源可以产生多个互相冲突的 Observation；不得为了去重而丢弃原始差异。

## 5. L1b：SemanticUnitCandidate

SemanticUnitCandidate 是对观测进行类型化解释的候选结构。

`kind` 至少区分：
- ENTITY：实体；
- CONCEPT：概念；
- EVENT：事件；
- ATTRIBUTE：属性值；
- STATE：状态；
- MEASUREMENT：测量；
- ACTION：动作；
- TIME / PLACE：时间或地点；
- UNKNOWN：无法可靠分类。

必需字段：
- candidate_id；
- kind；
- canonical_key（可空；仅在身份判定可靠时填写）；
- surface_forms（来源中的原始表达及定位）；
- typed_attributes（带值类型、单位和证据引用）；
- role_bindings（事件/关系角色，不得退化为无角色节点集合）；
- temporal_scope；
- scope；
- grounding_status；
- extractor_confidence；
- source_refs、derivation_refs。

身份合并不能只靠 embedding 相似度。合并必须报告身份依据、冲突属性、适用范围和可逆操作；无法确定时保留多个候选或标记 AMBIGUOUS。

## 6. Grounding 与断言语义

Grounding 状态与事实真值必须分离。

Grounding 状态：
- UNRESOLVED：尚未定位到足够证据；
- PARTIALLY_GROUNDED：部分字段有来源，仍有缺口；
- GROUNDED：所有必需字段均可回溯到证据；
- CONFLICTED：存在无法消解的来源冲突；
- REJECTED：候选被证据/约束否决；
- STALE：依赖来源或解析版本已变化。

Assertion 的 epistemic_status：
- ASSERTED：来源明确作出该陈述；
- INFERRED：由其他断言/关系推导；
- HYPOTHETICAL：假设或待检验候选；
- NEGATED：来源明确否定；
- UNKNOWN：当前证据无法确定。

禁止把 GROUNDED 等同于 TRUE。GROUNDED 只表示“来源定位和派生链完整”，不表示来源本身可靠或断言在现实世界中为真。

必须分别保存：
- extractor_confidence：解析器对抽取正确性的估计；
- source_reliability：来源可靠性评估（若存在）；
- truth_status：有证据支持的真值/未知/冲突状态；
- calibrated_probability：仅在经过独立校准时存在；
- ranking_score / energy：模型内部排序或能量，必须保留原始语义。

任何一个 score 不得兼任上述多个含义。

## 7. Relation / Hyperedge

关系必须保留关系类型、方向、极性和有序角色绑定。

必需字段：
- relation_id；
- relation_type；
- arity；
- role_bindings：role_name → SemanticUnit/Assertion 引用；
- direction / polarity；
- qualifiers（条件、方式、程度等）；
- valid_time 与 scope；
- grounding_status 与 epistemic_status；
- supporting_evidence_refs；
- contradicting_evidence_refs；
- derivation_refs；
- operator_id/version（若由类象/易象算子产生）。

高阶关系不得被压平成普通无序集合。角色顺序是语义的一部分。例如“主体使用工具处理对象”与“工具使用主体处理对象”不能因节点相同而被视为同一超边。

## 8. 类象 / 易象映射的边界

Yixiang/XSL 只能产生带类型的 MappingProposal，不得直接写成事实等价。

MappingProposal 必需字段：
- source_domain、target_domain；
- source_pattern、target_pattern；
- preserved_relations（明确保持哪些关系/角色）；
- broken_or_unmapped_relations；
- preconditions、applicability_scope；
- supporting_refs、counterexample_refs；
- operator_id/version；
- score_semantics、uncertainty；
- validation_status。

映射至少区分：
- STRUCTURAL_ANALOGY：结构类比；
- FUNCTIONAL_ANALOGY：功能类比；
- ROLE_ANALOGY：角色类比；
- TEMPORAL_ANALOGY：时序类比；
- CAUSAL_HYPOTHESIS：因果假设（必须另有干预/因果证据）；
- IDENTITY_CLAIM：同一性主张（最高门槛，不能从相似度直接产生）。

“象似”或“相似”只能提出候选，不等于身份相同、因果相同或规律可迁移。必须保留不适用条件和反例。

## 9. 修订、撤回和来源变化

原始证据不可变；派生记录采用追加式修订：
- 新版本引用 supersedes / corrects / retracts；
- 保留旧版本和产生修订的证据；
- 修订不覆盖原对象，也不重写历史；
- 上游 EvidenceRef 变化时，将依赖对象标记 STALE 并进入 CSL dirty-set；
- 重新解析产生新 Observation 版本，不得原地修改旧解析；
- 冲突必须保留双方来源，不能以最新写入自动覆盖。

删除/隐私擦除由上层授权策略处理；逻辑撤回和物理删除是不同操作。

## 10. 有界内存与检索包

L1 不允许在每次任务中加载全量 Observation 或 SemanticUnit 历史。

所有查询必须带：
- required_types；
- query_goal；
- scope / authorization；
- temporal_filter；
- max_records 或 byte_budget；
- ranking_policy；
- completeness marker。

返回 MemoryPacket：
- 最小充分对象引用；
- 来源跨度和哈希；
- 支持与反驳证据；
- 时间与作用域；
- 冲突/未知/STALE 标记；
- 被截断或预算耗尽的明确状态。

检索结果为空必须区分 NOT_FOUND 与 BUDGET_EXHAUSTED。摘要只作为压缩视图，必须保留回到原始证据的引用。

## 11. 事件和持久化边界

M2 不创建第二个事件账本。Observation、SemanticUnitCandidate、Assertion、Relation 的新增、修订、撤回和失效，最终应作为 ZPCM 事件/投影的一部分管理。

落地前必须确定：
1. ZPCM 的稳定 event envelope 和幂等键；
2. 对象版本与事件序号的映射；
3. SQLite 事务内事件写入和物化投影的原子性；
4. 崩溃恢复与重复投递语义；
5. schema migration 与旧版本兼容策略；
6. 物化索引可删除、可重建；
7. source_refs 不因重建丢失。

禁止在 Observation Store、ZPCM、DCMF、向量数据库中各自维护互不一致的“最新事实”。

## 12. 验收门槛（实现前必须可测试）

- Schema：缺失必需字段、未知版本、错误类型、非法角色绑定均拒绝。
- Provenance：每个 Observation/Assertion/Relation 能追溯到至少一个原始来源或显式标记为无来源的假设。
- Span：所有 byte span 与 M1 EvidenceChunk 精确对齐；不得越界或错绑版本。
- Grounding：GROUNDED 不自动变成 TRUE；冲突和未知保留。
- Confidence：不同 score 语义不能互相赋值或混用。
- Revision：更正/撤回保留历史版本，旧证据不被覆盖。
- Idempotency：相同输入和 producer version 重放不产生重复对象。
- Fault injection：在对象写入、事件提交、投影更新、索引更新各边界崩溃，重启后无丢失/重复/半提交。
- Budget：在受限 byte_budget 下保持有界返回；报告峰值 RSS、延迟、磁盘与检索完整性。
- OOD：跨模态、跨来源、跨领域评估 grounding 与类象迁移；包含反例和 abstain。
- Ablation：无 grounding、无 provenance、无关系角色、仅 embedding 相似度的对照必须运行。

## 13. 与 M1 的关系和实施顺序

M1 只证明原始字节分块、持久化和恢复；不证明 Observation 或语义 grounding。

推荐顺序：
1. M1 exact-head CI 与故障注入通过；
2. 为 M1 EvidenceRef 增加只读分页读取契约（不改变原文存储）；
3. 定义并测试 Observation DTO 和来源定位；
4. 建立 append-only ZPCM 事件适配，不新建平行事件账本；
5. 增加 SemanticUnitCandidate 和显式 grounding 状态；
6. 增加关系/超边角色绑定；
7. 最后接入 Yixiang/XSL MappingProposal 与 TRLW 工作集。

本规格通过文档审查不等于任何一步实现完成；每一步必须单独提交代码、测试、CI 与资源测量。
