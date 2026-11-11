# ZPCM N0.3：多重依据、推断谱系与增量认知维护

日期：2026-11-11  
状态：研究设计 / 以 N0.2 为上游；未声称实现、测试通过或完成真机验证。  
上游：PR #171，head `0e297b5e919727a232dc84806d63b768eb2ab7a3`

## 1. 核心结论：依赖 DAG 不等于认知维护系统

简单依赖图通常表达：

`A -> B -> C`

若 A 失效，沿边把 B、C 标为失效。这在只有单条推导路径时可用，但对真实认知系统不正确。

同一结论可能拥有多条独立推导：

`J1: A AND B -> D`  
`J2: E AND F -> D`

这里：
- 一条 justification（推导依据组）内部是 AND：所有必要前提都要满足。
- 同一结论的多个 justification 之间是 OR：任一仍有效的充分推导可能继续支持结论。
- A 失效只使 J1 失效；如果 J2 仍有效，D 不应被级联撤回。
- 如果 J1、J2 都失效，D 才变为 UNSUPPORTED，之后还要区分是否需要重算、是否存在反证。

因此 N0.3 不把“依赖边”作为最终语义单位，而以版本化的推导依据组为核心。依赖图只是查询和增量调度索引。

## 2. 与经典 Truth Maintenance Systems 的关系

本设计借鉴 Truth Maintenance System（TMS）的核心思想：保存每个信念的理由，依据变化时重新评估受影响信念，而不是只维护一个最终真假字段。

参考：
- Jon Doyle, *Truth Maintenance Systems for Problem Solving*（MIT AI TR 419, 1978）：记录 belief justifications，支持增量更新与依赖定向回溯。
- Doyle, *A Truth Maintenance System*（Artificial Intelligence, 1979）：描述理由维护、信念修订和依赖定向回溯。
- Johnson & Shapiro, *Dependency-Directed Reconsideration*（AAAI 2005）：只检查被变化影响的子集，避免每次全量重算，并处理连续修订的顺序效应。

ZPCM 不直接照搬传统 TMS 的二值 IN/OUT：
- 现实事实可能未知、冲突、过期或只在某时间段有效；
- 一个推断可能有多个独立来源；
- 来源可信度和证据质量不是逻辑真值；
- 模型生成的推断必须与直接观察区分；
- 结论是否能用于当前任务还受 scope、时间、权限和资源策略约束。

因此 N0.3 采用多状态、版本化、证据可追溯的认知维护，而不是一个布尔 truth-maintenance 标志。

## 3. 数据模型：Claim / Derivation / Justification

### 3.1 ClaimVersion

表示一个具体认知断言版本，沿用 N0.2 的 bitemporal 约定：
- `claim_version_id`
- `claim_id`
- `valid_from` / `valid_until`
- `tx_from_seq` / `tx_until_seq`
- `epistemic_status`
- `schema_version`

ClaimVersion 不直接存储“依赖边列表”作为唯一依据。

### 3.2 Derivation

表示一次具体推导行为：
- `derivation_id`
- `output_claim_version_id`
- `operator_id` / `operator_version`
- `model_id` / `model_version`（如由学习模型提出）
- `input_snapshot_seq`
- `created_event_seq`
- `derivation_kind`：RULE / ANALOGY / CAUSAL / ABDUCTIVE / COUNTERFACTUAL / MEMORY / HUMAN / EXTERNAL
- `parameters_digest`
- `explanation_ref`（可选，指向可审计的结构化解释，不要求保存隐藏思维链）

Derivation 是历史记录，不因后续失效而删除或覆写。

### 3.3 Justification

表示一条输出结论可依赖的一组充分前提：
- `justification_id`
- `derivation_id`
- `output_claim_version_id`
- `support_policy`：ALL_REQUIRED / AT_LEAST_K / WEIGHTED_THRESHOLD（首版只实现 ALL_REQUIRED）
- `created_event_seq`
- `retired_event_seq`（投影字段，由追加事件物化）
- `evaluation_status`

一个 Derivation 可以包含一个或多个 Justification。首版建议一条推导路径一个 justification，避免把多个 OR 分支压在同一个 AND 组内。

### 3.4 JustificationInput

每条输入都指向具体版本，而不是模糊的逻辑 claim：
- `justification_id`
- `input_ref_type`：CLAIM_VERSION / EVIDENCE_VERSION / SOURCE_VERSION / ASSUMPTION_VERSION
- `input_ref_id`
- `input_role`：REQUIRED / QUALIFIER / DEFEATER / CONTEXT
- `validity_requirement`
- `created_event_seq`

同一个 claim 的新版本不能自动替换旧推导引用的版本。新版本到达后，旧推导仍明确依赖旧版本；是否重新推导由重评估器决定。

## 4. 认知状态不是单一真假

建议对派生 ClaimVersion 使用以下状态（状态含义必须在 API 和 UI 中固定）：

- `SUPPORTED`：至少一条 justification 满足其输入条件，且没有阻止使用的未解决冲突。
- `MULTI_SUPPORTED`：有两条或以上独立有效 justification；它们仍可能共享底层证据，不能误称统计独立。
- `UNSUPPORTED`：没有任何有效 justification。
- `STALE`：依赖版本发生变化，尚未完成重评估。
- `DISPUTED`：存在未解决的反证、冲突或互斥结论。
- `RETRACTED`：该断言版本被明确撤回。
- `SUPERSEDED`：有新版本替代当前知识版本；历史查询仍可见。
- `UNKNOWN`：尚无足够信息判断。

这些状态不是简单的线性等级。尤其：
- STALE 是处理状态，不是真假状态；
- DISPUTED 是证据/冲突状态，不等于 UNSUPPORTED；
- RETRACTED 与 SUPERSEDED 是版本生命周期状态；
- MULTI_SUPPORTED 不自动等于更高概率或更可信。

建议内部采用正交维度，而不是一个 enum 承载所有语义：
1. support_state：SUPPORTED / UNSUPPORTED / UNKNOWN；
2. review_state：CURRENT / STALE / REVIEWING；
3. conflict_state：CLEAR / DISPUTED；
4. lifecycle_state：ACTIVE / RETRACTED / SUPERSEDED。

面向 API 时可导出组合状态，但底层不要把维度压扁。

## 5. 增量失效与重新评估算法

### 5.1 输入变化事件

例如：
- `CLAIM_VERSION_RETRACTED`
- `CLAIM_VERSION_SUPERSEDED`
- `EVIDENCE_VERSION_REVOKED`
- `SOURCE_VERSION_REPLACED`
- `ASSUMPTION_INVALIDATED`
- `DERIVATION_RULE_DEPRECATED`

事件只追加，不直接级联修改派生结论。

### 5.2 反向索引

维护：
- `input_ref_id -> justification_ids`
- `justification_id -> output_claim_version_id`
- `output_claim_version_id -> justification_ids`
- `claim_version_id -> downstream_derivation_ids`

反向索引属于可重建投影，账本仍是唯一事实源。

### 5.3 失效工作队列

一个事件到来后：
1. 追加源变化事件并取得 event_seq。
2. 找出直接引用该输入版本的 justification。
3. 把对应 justification 标记为待评估，写入持久化工作队列。
4. 将其输出 claim 标记 STALE（不直接撤回）。
5. 对该输出的下游 justification 做有界传播，直到达到批次预算或稳定边界。
6. 按拓扑层次重新评估 justification，再重新计算输出 claim 的整体支持状态。
7. 只有当某 claim 的整体支持状态发生变化时，才继续向下游传播；若另有有效 justification，避免无意义级联。
8. 提交本批结果和传播水位。

### 5.4 AND / OR 评估

首版 ALL_REQUIRED 语义：

`valid(J) = AND(valid(input_i) for each required input_i)`

一个 claim 有多个独立 justification：

`supported(C) = OR(valid(J_j) for each justification_j)`

重要限制：
- qualifier 输入可限制适用范围，但不一定是逻辑前提；
- defeater 输入用于阻断或降低支持，需要显式策略，不能混入普通 AND；
- context 输入用于解释和重算，不应自动决定有效性；
- 证据权重不是 AND/OR 的替代物，概率聚合另行设计。

### 5.5 为什么不简单沿图 BFS 撤回

BFS 可以找到潜在受影响节点，但不能判断节点是否真的失去全部支持。正确流程是：
- BFS/队列只负责定位候选受影响区域；
- justification evaluator 负责判断每条路径；
- claim aggregator 负责汇总 OR 路径；
- 只有状态变化才继续传播。

这能避免多路径结论被错误撤回。

## 6. 多路径与共享祖先

考虑：

`J1: A AND B -> D`  
`J2: E AND F -> D`

撤回 A：
- J1 无效；
- J2 仍有效；
- D 仍为 SUPPORTED；
- D 的支持路径计数由 2 变为 1；
- 只有 D 的依赖解释发生变化时，才需要更新相关派生元数据。

如果 J1 和 J2 实际共享底层来源 S：
- 它们不是独立证据；
- 需要通过 evidence/source lineage 识别共同祖先；
- 不得把“两个推导路径”误报成“两份独立证据”；
- 对置信度的聚合必须考虑相关性，首版不做简单概率相乘或多数票。

## 7. 环、循环推导和强连通分量

N0.3 首版采取保守策略：
- 依赖 ClaimVersion 的推导谱系必须保持 DAG；
- 写入时检查新边是否形成环；
- 检测到环时拒绝自动物化该推导，进入 QUARANTINED / REVIEW；
- 允许未来单独研究带固定点语义的循环规则，但不得将其伪装成普通 DAG。

理由：循环推导可能产生“P 因 Q 成立，Q 又因 P 成立”的自我支撑。没有明确逻辑语义时，简单迭代会错误地把循环当作证据。

后续若支持递归规则，必须先定义：
- 单调性；
- 最小/最大固定点语义；
- 初始化边界；
- 终止条件；
- 资源上限；
- 循环中断与回滚。

## 8. 传播一致性、崩溃恢复与幂等

工作队列建议字段：
- `work_id`
- `trigger_event_seq`
- `target_justification_id`
- `target_claim_version_id`
- `reason_code`
- `status`：PENDING / CLAIMED / DONE / RETRY / QUARANTINED
- `attempt_count`
- `lease_owner` / `lease_until`（多进程版本）
- `created_at` / `completed_at`

幂等键建议：
`(trigger_event_seq, target_justification_id, evaluator_version)`

一致性水位必须分开：
- `ledger_seq`：事件账本已提交水位；
- `projection_seq`：claim/justification 基础投影水位；
- `invalidation_seq`：依赖失效队列已处理到的事件水位；
- `evaluation_seq`：重评估结果已提交水位。

不得在依赖工作尚未完成时，把 invalidation watermark 提前推进到 trigger event_seq。

事务建议：
- 源事件追加独立事务；
- 失效工作入队与相关投影标记在同一事务；
- 每个有界重评估批次内，状态更新、工作完成和水位推进原子提交；
- 崩溃后未完成任务由 lease 过期恢复；
- 重复处理同一 work_id 不得产生重复状态变化。

## 9. 资源控制与移动端执行

传播成本可能随高扇出节点急剧增长，因此必须是 anytime：
- 每批限制节点数、边数、时间片和临时 RAM；
- 高扇出节点拆分分页；
- 工作队列持久化，内存只保留当前批；
- 热节点保留反向索引缓存，冷节点走 SQLite 索引；
- 支持暂停、恢复、优先级和合并重复工作；
- 对正在被当前回答引用的结论提高优先级；
- 对低价值、远离当前目标的历史分支延迟重评估；
- 超预算时返回明确的部分状态，不得将 STALE 当作 CURRENT。

MCRL 可提供预算和优先级，但不能篡改事实状态。MCRL 选择“何时算”，ZPCM 维护“当前算到哪里、哪些结论尚未完成”。

## 10. 与易象/类象算子的结合

易象算子不能只作为推断名称。它们应产生可审计的结构变换和依赖引用：

- 取象：从观察中抽取对象、属性、关系和候选角色。
- 比类：提出结构相似候选，同时保留映射证据和不匹配项。
- 变：产生关系/状态变化假设，记录变换前后结构。
- 应：检查不同对象、条件或时间位置之间的关系约束。
- 互：从局部关系组合出中间结构，但每条新边必须引用具体输入版本。
- 错综：产生视角或角色变换候选，不自动把视角变换当作事实。
- 时位：把推断限定到适用时间、条件和关系位置。

每个算子输出一个 Derivation，输出 ClaimVersion 通过一个或多个 Justification 绑定其输入。算子版本和结构映射必须保存，便于新规则发布后选择性重评估。

算子提出的是候选结构，不是事实认证。证据验证与认知状态提交必须分离。

## 11. 确定性测试基线

### T1：单链失效

A -> B -> C -> D。撤回 A 后，B/C/D 进入 STALE，再依次重评估为 UNSUPPORTED；旧推断历史保留。

### T2：多路径保留

A AND B -> D；E AND F -> D。撤回 A 后 J1 失效，J2 有效，D 仍 SUPPORTED。

### T3：所有路径失效

撤回 A、E 后，D 的所有 justification 均失效，D 变为 UNSUPPORTED。

### T4：共享祖先相关性

A -> J1 -> D；A -> J2 -> D。两条推导不能被计为两份独立证据；撤回 A 后两条路径都失效。

### T5：无关分支隔离

A -> B -> C 与 X -> Y 两支并存。撤回 A 不改变 X/Y 的任何状态、版本或 digest。

### T6：反证与支持并存

一条 justification 支持 P，另一条 defeater 反驳 P。P 进入 DISPUTED，而不是简单地 SUPPORTED 或 UNSUPPORTED。

### T7：崩溃恢复

在工作队列处理到一半时模拟进程中止。重启后只重做未完成工作，最终投影与完整重建一致。

### T8：重复事件与重复工作

同一 trigger event 重复入队、同一 work 重复执行，不产生重复状态版本或错误水位。

### T9：环检测

插入 A -> B、B -> C、C -> A。最后一条必须被拒绝或隔离，不得让循环自我支撑。

### T10：有界传播

高扇出图中每批严格不超过配置预算，暂停后可恢复，未处理区域保持 STALE。

### T11：新依据恢复

A 被撤回使 D 暂时 UNSUPPORTED；后续新增独立依据 G -> D，D 可建立新的支持版本，但不得抹除曾经 UNSUPPORTED 的历史。

### T12：增量与全量一致

对随机生成的有向无环依赖图和事件序列，增量重评估结果必须等于从事件账本全量重建的结果。

## 12. 性能实验设计

必须测量而不是预设：
- 事件追加吞吐与写延迟；
- 反向依赖查找 P50/P95；
- 受影响节点数 / 总节点数；
- 单次失效传播节点/边处理速率；
- 每批峰值 RAM；
- SQLite 文件增长与索引空间；
- 崩溃恢复耗时；
- 高扇出、深链、多路径、共享祖先四类图的退化曲线。

对照：
1. 全量重建；
2. 简单 BFS 级联失效；
3. 版本级依赖 + justification 重评估；
4. 版本级依赖 + MCRL 价值调度。

不能只测平均链状图。必须加入高扇出和多路径压力图。

## 13. 与现有项目模块的接口边界

- N0.1：提供不可变事件账本和可重建投影基础。
- N0.2：提供双时间 claim version 和 as-of 查询。
- N0.3：提供 Derivation / Justification / 输入版本依赖和增量认知维护。
- XSL：提出类象映射候选及关系角色变换。
- CSG-GCR：生成候选结构并做全局约束求解。
- RSDN：提出认知状态编辑。
- MCRL：调度重评估、检索、验证和停止。
- 语言生成器：只消费当前可用、证据归属明确的认知快照。

任何上层模块都不能绕过事件账本直接修改 ZPCM 的认知状态投影。

## 14. 非目标与验收边界

本文件没有实现数据库表、工作队列或传播器，也没有运行测试。它定义 N0.3 的领域模型和验收标准。

完成 N0.3 的最低工程交付应包含：
1. SQLite schema 与 migration；
2. justification append / retract / reevaluate API；
3. 反向索引；
4. 持久化有界工作队列；
5. 多路径支持状态聚合；
6. 环检测；
7. 全量重建 oracle；
8. 上述确定性测试；
9. 可重复基准脚本；
10. 失败关闭和崩溃恢复说明。

只有实现、执行测试并保存可复现基准后，才可宣称 N0.3 原型完成。真机性能仍需独立验证。
