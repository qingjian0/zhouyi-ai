# ZPCM N0.2：双时间、版本化认知断言与 as-of 查询

日期：2026-11-11  
状态：研究设计 / 以 N0.1 SQLite 事件账本为基线；本文件不声称已实现或通过测试。  
基线：PR #169，head `c565bef865870e01a8b11b039e35da705e682e87`

## 1. 本阶段要解决的问题

N0.1 已区分事件记录时间与声明有效时间的基础字段，但尚不能完整回答：

- 在现实时间 (t_v)，某个事实是否有效？
- 在系统认知时间 (t_k)，系统当时持有哪些断言？
- 后来发生纠正时，能否还原纠正前系统的认知，而不覆盖历史？
- 两条互相冲突的断言是否能并存，等待证据裁决，而不是被“最后写入者获胜”吞掉？

N0.2 的目标是建立可重建的双时间断言投影（bitemporal claim projection），不是把自然语言对话变成一个单一、永远正确的事实表。

## 2. 两条时间轴必须分离

### 2.1 Valid time：对象世界中的有效时间

表示断言描述的事实在现实世界何时成立，区间采用左闭右开：

`[valid_from, valid_until)`

例如：某用户在 2024-01-01 至 2025-03-01 居住于地点 A。若 2025-03-01 搬离，旧断言的 valid_until 为 2025-03-01。

### 2.2 Transaction / knowledge time：系统何时知道

不要直接把客户端时间戳作为唯一顺序依据。N0.2 以不可变事件账本的单调 `event_seq` 作为规范知识时间：

`[tx_from_seq, tx_until_seq)`

- `tx_from_seq`：系统首次把该断言版本纳入认知投影的事件序号。
- `tx_until_seq`：系统通过后续事件停止把该版本视为当前知识版本的序号；空值表示当前仍在知识投影中。
- `recorded_at` 继续用于人类可读审计，但不承担并发情况下的唯一排序职责。
- 如果 API 接收自然时间 `known_at`，必须先按确定规则解析为事件序号；核心查询 API 应允许直接传 `known_at_seq`。

这能避免设备时钟回拨、时区转换、相同毫秒时间戳等问题破坏重放顺序。

## 3. 数据身份模型

区分四种身份，禁止混为一个 ID：

1. `claim_id`：逻辑断言槽位，例如“用户居住地”。
2. `claim_version_id`：某次具体断言版本，不可变。
3. `event_id / event_seq`：导致断言状态变化的账本事件身份。
4. `evidence_id`：支持、反驳或限定断言的证据身份。

一个 claim 可以有多个版本，也可以在同一 valid-time 区间存在多个互相冲突的版本。冲突不是数据库唯一键错误，而是需要保留的认知状态。

建议的最小字段：

### claim_versions（可重建投影）

- `claim_version_id`：主键。
- `claim_id`：逻辑断言身份。
- `subject_ref`、`predicate`、`object_json`：类型化断言内容。
- `valid_from`、`valid_until`：现实有效区间。
- `tx_from_seq`、`tx_until_seq`：知识有效区间。
- `assertion_event_seq`：创建该版本的事件序号。
- `epistemic_status`：ASSERTED / DISPUTED / RETRACTED / SUPERSEDED 等投影状态。
- `confidence_payload`：可选、带模型与校准版本的置信信息；不可把一个裸浮点数当作事实真值。
- `schema_version`：断言结构版本。

### claim_version_links（可重建投影）

记录版本关系，例如 `supersedes`、`contradicts`、`qualifies`、`derived_from`。关系本身应带创建事件序号和来源，避免后续改写关系历史。

### claim_evidence_links（可重建投影）

记录 claim_version 与 evidence 的支持、反驳、限定关系；证据被撤销或来源更新时，保留原链接和变更事件，不删除旧证据。

注意：以上表是投影结构，不是第二份事实源。唯一事实源仍是 append-only 事件账本。

## 4. 事件协议

N0.2 建议扩展事件类型：

- `CLAIM_ASSERTED`：创建新的逻辑断言或新版本。
- `CLAIM_SUPERSEDED`：声明一个新版本取代某个知识版本；必须引用旧版本和新版本。
- `CLAIM_RETRACTED`：撤回某个断言版本；保留撤回原因和证据。
- `CLAIM_DISPUTED`：记录冲突或反证，不自动删除被质疑断言。
- `EVIDENCE_REVOKED`：标记证据不可继续作为有效支持；不抹去它曾经被系统使用的历史。
- `SOURCE_REVISION_RECORDED`：记录来源内容发生修订或版本替换。

每个事件必须携带稳定 `event_id`、严格 `schema_version`、规范化 payload、来源引用和事件序号。相同 ID 相同内容幂等；相同 ID 不同内容拒绝。

### 4.1 修订不是原位 UPDATE

例如系统先记录：

- seq 10：claim-version V1，用户住在 A。
- seq 30：收到新证据，系统记录 V2，用户从某日期起住在 B。
- seq 30：同一事务内结束 V1 的知识有效区间，并建立 V2 的知识有效区间。

事件账本中只追加 seq 30 的修订事件。投影可以重建，所以投影中的 `tx_until_seq` 更新不违反账本不可变原则。

若新证据只证明“现在住在 B”，不能擅自推断过去从未住在 A；V1 的 valid-time 区间必须按证据明确的时间范围处理。

## 5. as-of 查询契约

核心接口建议：

`query_claims(subject?, predicate?, valid_at, known_at_seq, include_disputed=false, include_retracted=false)`

投影选择条件：

`valid_from <= valid_at AND (valid_until IS NULL OR valid_at < valid_until)`

并且：

`tx_from_seq <= known_at_seq AND (tx_until_seq IS NULL OR known_at_seq < tx_until_seq)`

返回结果至少包含：

- 匹配的 claim_version；
- valid-time 与 knowledge-time 区间；
- epistemic status；
- evidence_refs；
- version links；
- 产生该版本的 event_seq；
- 当前 projection watermark；
- 是否存在同槽位冲突。

### 5.1 两种不同问题

- “2024 年 6 月现实中用户住在哪里？”：指定 `valid_at=2024-06`，并指定当前知识水位。
- “系统在 2024 年 6 月 1 日当时认为用户住在哪里？”：指定 `known_at_seq` 对应当时的知识快照，再指定需要查询的 `valid_at`。

二者不可合并成一个模糊的“历史查询”。

### 5.2 一致性水位

事件账本的最新序号与投影物化序号可能不同。若请求的 `known_at_seq` 大于 projection cursor：

- 返回明确的 NOT_MATERIALIZED / retryable 状态；
- 或由调用方等待物化完成；
- 不允许静默使用旧投影冒充完整结果。

投影必须暴露 `materialized_seq` 和 `projection_version`。

## 6. 冲突裁决原则

N0.2 不采用“最新断言覆盖旧断言”的 last-write-wins 逻辑。

当两个版本在同一 valid-time、同一 subject/predicate 下不兼容时：

1. 两个版本都保留。
2. 标记冲突关系，记录双方证据。
3. 区分“现实世界可能互斥”与“描述粒度不同、可同时成立”。
4. 由后续证据评估/裁决层提出 DISPUTED、QUALIFIED、RETRACTED 或 SUPERSEDED 事件。
5. 语言生成层必须能表达不确定与冲突，不得只挑置信分最高的一条伪装成确定事实。

冲突检测可以使用类型化谓词的互斥约束，但必须版本化规则集，并保存触发冲突的规则与输入版本。

## 7. N0.1 到 N0.2 的迁移策略

- 原始 events 表保持 append-only，不改写旧 payload。
- 旧事件按旧 schema_version 解释。
- 新 projection schema 以独立 `projection_version` 标识。
- migration 是确定性投影构建器，不是批量 UPDATE 原始事件。
- 无法安全推断的旧字段必须保持 UNKNOWN，不得补造 valid-time 或 transaction-time。
- 每次迁移记录源账本水位、目标 projection_version、构建器版本和输出 digest。
- 新旧投影可短期并行构建，对比 claim 数、版本关系、冲突数和 digest；不一致时停止切换。

## 8. SQLite 索引与移动端预算

初始索引建议：

- `(claim_id, tx_from_seq, tx_until_seq)`
- `(subject_ref, predicate, valid_from, valid_until)`
- `(subject_ref, predicate, tx_from_seq, tx_until_seq)`
- `(assertion_event_seq)`
- evidence 反向索引 `(evidence_id, claim_version_id)`

不要一开始把所有 JSON payload 全部展开成宽表，也不要为每一种查询组合建立大量索引。通过真实 workload 测量索引空间、写放大和查询延迟后再增补。

移动端原则：

- 原始事件、完整版本历史、冷证据保存在磁盘。
- RAM 只保留当前任务涉及的 claim 子图、必要版本和证据摘要。
- as-of 查询走索引和有界分页，不把整个历史装入上下文。
- 投影缓存可丢弃并重建；事件账本不可被摘要覆盖。
- 历史条数不等于模型 Token 上下文长度。

## 9. 与 CSL 依赖图研究线的边界

仓库现有 CSL 图研究面向 E12 候选结构、learner_track 和 CandidateState 生命周期；ZPCM 面向持久化断言、现实有效时间和系统知识时间。两者不是同一个领域模型，不能直接把 CSL 的 StructureRef / E12 状态映射成 ZPCM Claim。

可以复用的只是经过抽象验证的基础机制，例如不可变事件重放、DAG 无环检查、反向依赖索引和确定性工作队列。任何复用都必须经过独立契约和测试，不得把 E12 的 ACTIVE / RETIRED 状态当成事实可信度。

## 10. N0.2 验收测试

必须覆盖：

1. 旧版本在新知识到达后仍可按旧 `known_at_seq` 查询。
2. 新版本在新水位可见，旧版本的 transaction interval 正确闭合。
3. valid-time 与 knowledge-time 交叉查询四象限正确。
4. valid-time 重叠的冲突断言并存，不触发 last-write-wins。
5. 撤回后当前查询默认隐藏，但历史 as-of 查询仍能还原撤回前认知。
6. 证据撤销不删除历史 claim-evidence link。
7. 同毫秒 recorded_at 的多个事件仍由 event_seq 确定顺序。
8. 设备时钟回拨不改变 event_seq 查询语义。
9. projection cursor 落后时拒绝超水位查询。
10. 从事件账本全量重建后，查询结果、版本关系和 digest 一致。
11. 旧 schema 事件迁移不补造未知时间。
12. 随机事件序列 property test：增量物化结果必须等于全量重建结果。

## 11. N0.3 的接口预留

N0.2 只建立版本化断言与证据关系，不在本阶段实现自动失效传播。为下一阶段预留：

- derivation_id；
- derived_claim_version_id；
- input_claim_version_ids；
- input_evidence_ids；
- rule_or_operator_version；
- derivation_event_seq；
- dependency edge role；
- invalidation trigger event_seq。

N0.3 将依据这些版本级依赖，计算哪些派生断言需要重新评估。失效传播必须是可审计的投影工作队列，不得直接改写原始推断历史。

## 12. 非目标与当前状态

本设计尚未实现：
- 双时间查询代码；
- claim revision/retraction 新事件执行器；
- schema migration；
- N0.3 依赖失效传播；
- 并发与崩溃压力测试；
- Android/Kotlin 适配；
- 百万事件、RAM、延迟、能耗基准。

本文件是 N0.2 的可审查设计基线，不是已完成实现或实验结果。
