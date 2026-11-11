# E13 共享数据契约与 E10/E12/XSL 集成审计

日期：2026-11-11  
状态：代码审计与接口设计；本文不声称联合运行时已实现。  
目标分支：`research/mobile-million-context-architecture-2026-11-11`

## 0. 本轮审计结论

本轮对 E10、E12 与 XSL-1 的分支原型进行了源码级检查。需要修正一个容易造成误判的说法：

- E10-B/C 并非完全没有代码。E10-A 有限关系版本空间分支已经包含 E10-B 的迁移/OOD 拒答实验、E10-B.3 不可识别性审计，以及 E10-C.1 冲突修订和 E10-C.2 漂移可表示性实验。
- 但 E10BC 的“联合类比映射 + 算子归纳”仍是研究提案；已有 E10-A/B/C 原型不能等同于联合类象算子学习器。
- XSL-1 已有确定性映射验证器，但它验证的是调用者提供的映射，不负责发现映射。
- E12-A1/A2/A3 已有独立原型，但输出契约彼此不同，也没有直接连接到 XSL-1 的类型化关系图。

因此当前主要工程缺口不是再增加一套独立算法，而是建立一个**不会丢失角色语义、证据谱系、未知状态和实验隔离信息的跨轨数据契约**。

## 1. 已检查实现及其真实边界

| 组件 | 已检查文件/分支 | 已实现能力 | 关键边界 |
|---|---|---|---|
| E10-A 属性束 | `prototype/e10_structural_concepts.py`，E10BC 分支 | 从观察记录挖掘重复属性束与角色属性束 | 频繁项集式结构归纳；不理解语义，不做跨域类比 |
| E10-A 有限关系学习 | `prototype/e10a_finite_relational_learner.py`，E10A finite relational 分支 | 有限 DSL 版本空间、Support 拟合、Query 拒答、增量过滤 | 每个关系符号只搜索“一个类别特征 + 无序不同角色值集合 + 一个上下文等值条件”；明确不识别角色顺序 |
| E10-B 迁移审计 | `prototype/e10b_transfer_experiment.py` | 一致重命名不变性、Query-only OOD 拒答、硬负例分片、支持证据消融 | 重命名不变性不是语义类比；未见值拒答不是外推成功 |
| E10-B.3 | `prototype/e10b_relation_ood_identifiability.py` | 构造可见输入完全相同、隐藏标签相反的两个世界 | 证明不透明新关系符号在没有公开描述或共享样例时不可识别；不是通用性能基准 |
| E10-C.1/C.2 | `prototype/e10c_conflict_revision.py`、`prototype/e10c_drift_representability.py` | 冲突证据导致版本空间收缩/清空；测试固定规则语言的漂移表示边界 | 不会自主判定来源可信度，也不自主发现新 epoch 或扩展新 DSL |
| E10 共享证据适配器 | `prototype/e10_shared_protocol_adapter.py` | 将 E10 原生 prequential ledger 镜像到 SQLite protocol v0.2 | 持久化/协议一致性适配，不是关系学习器；非跨库原子事务或安全沙箱 |
| E12-A1 | `prototype/e12a1_typed_predicate_induction.py` | 从 Train 值提出类型化一元谓词，并在 Gate 上筛选 | 预设 GE/GT/LE/LT/EQ/PARITY 语法；Gate 参与选择，不是最终独立 Test |
| E12-A2 | `prototype/e12a2_active_measurement.py` | 给定假设先验和测量似然表，计算期望信息增益并按成本选择 | 不生成真实测量动作、不执行环境观测；似然表必须由上游提供 |
| E12-A3 | `prototype/e12a3_relational_primitive_induction.py` | 从特征对提出 LT/GT/EQ/SAME/DIFFERENT/SAME_PARITY 关系候选 | 仅二元特征对和有限关系语法；不是任意高阶关系发现 |
| XSL-1 | `prototype/yixiang_analogy.py` | 验证显式给定的类型化部分图映射；保留有序参数、覆盖率、保持率、冲突和未映射 | 不自动搜索节点/关系映射；不推断因果等价；证据 refs 仅是标识符 |

## 2. 跨轨接口冲突

### 2.1 E10-A 的无序参与者语义不能伪装成 XSL 的有序角色语义

E10-A 有限关系学习器明确声明：

- `role_order_identified = false`
- `role_semantics = unordered_role_value_set; permutation invariant`

其生成器会打乱参与者顺序。因此即使它能在自身任务上正确预测，也不能把参与者位置解释为“施动者/受动者/媒介”等语义角色。

XSL-1 的 `Relation.arguments` 则按 tuple 顺序匹配；交换参数可能构成反例。二者语义不兼容。适配器必须显式携带 `role_semantics`，无序来源不得自动升级为有序关系。

### 2.2 E12-A3 的左右参数不等于语义角色

E12-A3 的 `left` / `right` 是特征对枚举顺序。对于 LT/GT，它们具有方向语义；对于 SAME/DIFFERENT，它们在数学上对称。不能统一把所有谓词都解释为有向关系。

关系类型必须声明：
- 对称性：SYMMETRIC / ASYMMETRIC / UNKNOWN；
- 角色定义：命名角色或仅位置参数；
- 允许的自同构/角色置换；
- 输入类型与输出类型。

### 2.3 XSL-1 的显式映射不等于映射发现

XSL-1 接收 `node_mapping`、`node_type_mapping` 和 `relation_mapping`。它能回答“给定映射是否保持关系”，不能回答“哪一个映射最可能正确”。

因此应把两个阶段分开：
1. MappingProposal：提出零个、一个或多个候选映射；
2. MappingValidation：对每个候选进行确定性结构检查。

不得把验证器通过率包装成类比发现准确率。

### 2.4 E12-A2 的测量选择与真实观测执行是两个接口

E12-A2 的 Probe 已包含 `P(outcome | hypothesis, action)`。选择器只计算信息增益/成本并返回 action_id。它不负责：
- 生成 action；
- 验证该 action 在当前环境可执行；
- 调用传感器或模拟器；
- 接收真实结果；
- 判断结果来源是否可信。

E13 必须把 QueryProposal、ActionExecution、ObservationReceipt 分开建模。

### 2.5 证据协议目前只解决部分持久化问题

E10 Shared Evidence Adapter 保留 E10 原生 ledger 和结构版本谱系，但其文档明确不提供跨存储原子事务、崩溃恢复或 OS 级隔离。XSL-1 的 evidence_refs 又只是字符串引用。当前不能声称已经存在跨 E10/E12/XSL 的统一 EvidenceLedger。

## 3. 建议的共享契约：CPG-EI Typed Experience Contract v0.1

本契约先作为适配层，不要求立即重写已有学习器。所有字段采用显式版本化；未知信息必须保留为 UNKNOWN，不能用默认值猜测。

### 3.1 ObservationEnvelope

- `schema_version`
- `observation_id`
- `source_id`
- `episode_id`
- `phase`: SUPPORT / GATE / TEST / QUERY / REVEAL
- `visibility`: LEARNER_VISIBLE / EVALUATOR_ONLY / PUBLIC_DESCRIPTOR
- `timestamp` 与 `context_ref`
- `payload_digest`
- `provenance_refs[]`

隐藏标签不得出现在 LEARNER_VISIBLE 的 Query payload 中。评估器只能在 prediction commit 后发布 reveal。

### 3.2 Entity

- `entity_id`
- `entity_type`
- `attributes[]`: 每项包含 attribute_type、typed_value、unit、source_ref
- `state_ref`：当前状态与持久概念身份分离

对象 ID 仅用于引用和谱系，不得成为学习特征。

### 3.3 RelationSchema 与 RelationInstance

RelationSchema：
- `relation_type`
- `arity`
- `argument_types[]`
- `role_names[]`
- `role_semantics`: ORDERED_NAMED / ORDERED_POSITIONAL / UNORDERED / UNKNOWN
- `symmetry_group[]` 或明确的 SYMMETRIC / ASYMMETRIC / UNKNOWN
- `context_schema`
- `temporal_semantics)

RelationInstance：
- `relation_id`
- `relation_type`
- `participants[]`：实体引用与角色名
- `context_values[]`
- `time_or_state`
- `evidence_status`
- `provenance_refs[])

只有 RelationSchema 声明角色后，系统才可把位置参数解释为语义角色。UNORDERED 与 UNKNOWN 必须在跨域映射时保留，必要时拒绝映射。

### 3.4 PrimitiveCandidate

- `primitive_id`
- `primitive_kind`: ATTRIBUTE_PREDICATE / BINARY_RELATION / NARY_RELATION / MEASUREMENT / TRANSFORM
- `input_signature[]`
- `output_signature`
- `executable_spec` 或可复现 evaluator 引用
- `scope_conditions[]`
- `support_refs[]`
- `counterexample_refs[]`
- `unknown_refs[]`
- `candidate_version`
- `compute_cost`
- `status`: PROPOSED / IDENTIFIED_IN_GRAMMAR / AMBIGUOUS / REJECTED / SUSPENDED

“IDENTIFIED_IN_GRAMMAR”必须带 DSL/schema 版本，不得被解释为开放世界唯一真理。

### 3.5 AnalogyMapCandidate 与 Validation

候选映射和验证结果分开存储。

候选映射至少包括：
- source_pattern_ref / target_pattern_ref；
- node_map、relation_map、role_map；
- context_map；
- 未映射部分；
- 假设的保持约束；
- proposal_method 与 candidate_budget。

验证结果至少包括：
- preserved / violated / unmapped / unknown；
- mapping_coverage；
- preservation_rate；
- scope_conditions；
- counterexample_refs；
- deterministic_digest；
- status：PRESERVED / PARTIAL / COUNTEREXAMPLE / UNTESTABLE / AMBIGUOUS。

AMBIGUOUS 不是 PARTIAL；多个结构上等价的映射必须保留为多个候选，不能按排序规则伪造唯一答案。

### 3.6 DiscriminatingQuery 与 ObservationReceipt

DiscriminatingQuery：
- `query_id`
- `candidate_set_digest`
- `competing_hypothesis_ids[]`
- `action_id`
- `predicted_likelihoods`
- `expected_information_gain`
- `cost`
- `selection_reason)

ObservationReceipt：
- `query_id`
- `action_execution_id`
- `observed_outcome`
- `source_id`
- `timestamp`
- `integrity_status`
- `evidence_ref`

E12-A2 只负责 Query 的候选排序；执行器和 receipt 校验属于另外两个组件。

### 3.7 EvidenceEvent

统一事件至少区分：
- OBSERVATION_RECORDED
- CANDIDATE_PROPOSED
- PREDICTION_COMMITTED
- QUERY_SELECTED
- ACTION_EXECUTED
- EVIDENCE_REVEALED
- MAPPING_VALIDATED
- STRUCTURE_REVISED
- CANDIDATE_SUSPENDED / REJECTED

每个事件必须有 event_id、episode_id、sequence、parent_refs、actor_track、payload_digest、visibility 和时间戳。证据状态 SUPPORT / COUNTEREXAMPLE / UNKNOWN / CONFLICT 不得折叠为一个置信分数。

## 4. 旧原型适配规则

| 旧模块 | v0.1 适配规则 | 禁止的隐式转换 |
|---|---|---|
| E12-A1 Predicate | 映射为 ATTRIBUTE_PREDICATE；保留特征类型、操作符、阈值和 Train/Gate 来源 | 不得将 Gate 唯一候选称为独立 Test 验证 |
| E12-A3 RelationalPredicate | 映射为 BINARY_RELATION；根据操作符声明对称性和方向 | 不得把所有 left/right 都当成命名角色 |
| E10-A RelationRule | 标记 role_semantics=UNORDERED；记录其有限 DSL 与 context equality | 不得把参与者 tuple 顺序当成角色顺序 |
| E10-B OOD audit | 映射为 OOD/ABSTAIN 证据与评估切片 | 不得把拒答率降低直接称为迁移成功 |
| E10-C revision | 映射为版本化 EvidenceEvent 和候选集修订 | 不得把空版本空间自动解释成概念漂移 |
| E10 Shared Protocol Adapter | 可复用事件顺序、结构版本和引用模式 | 不得声称跨库原子事务、OS 隔离或安全沙箱 |
| XSL-1 | 作为 MappingValidation 后端；输入显式 RelationSchema 和映射 | 不得把验证器输出当作自动映射发现 |
| E12-A2 | 作为 DiscriminatingQuery 选择策略 | 不得将 action_id 当成已执行观测 |

## 5. E13-A/B 的最小执行顺序

### E13-A0：契约与无损适配

1. 实现 v0.1 schema 与严格校验器。
2. 为 E12-A1、E12-A3、E10-A、XSL-1 写独立 adapter。
3. 对每个 adapter 做 round-trip / canonical digest 测试。
4. 测试 UNKNOWN、缺失字段、角色语义未知、隐藏标签混入 Query 等情况全部 fail closed。

### E13-A1：从关系观察构造 Pattern

先使用显式关系描述符构造 typed relational graph；不得用对象 ID、样本顺序或字段数量泄漏答案。数据集至少包含二元和三元关系、对称与非对称关系、上下文条件和噪声。

### E13-B1：映射候选发现

在有限小图上先实现精确枚举器作为 oracle：
- 枚举类型兼容的一对一节点映射；
- 枚举关系类型映射；
- 仅在 schema 允许时枚举角色置换；
- 输出所有等价最优映射，而非只输出一个；
- 超预算时返回 BUDGET_EXHAUSTED，不截断后假称唯一最优。

XSL-1 用于验证枚举器输出。二者必须独立实现，不能让 oracle 直接调用被测验证器生成预期答案。

### E13-B2：反例和 OOD

至少包括：
- 节点语义相似但关系方向相反；
- 参与者角色互换；
- 同一关系在不同上下文条件下失效；
- 对称关系与非对称关系混淆；
- 未见关系符号但无公开描述；
- 公开描述冲突或恶意误导；
- 多个自同构映射无法唯一识别。

对无公开描述的新关系，E10-B.3 已说明正确行为应是拒答，而不是猜测迁移。

## 6. 基线与验收门

必须对比：
1. Exact mapping enumerator（小图 oracle）；
2. XSL-1 explicit-map validator；
3. 自动 mapping proposal + XSL-1 validation；
4. 随机兼容映射；
5. 节点/属性最近邻映射；
6. 忽略角色顺序的 ablation；
7. 忽略上下文的 ablation；
8. 无易象先验与可学习通用关系先验。

验收指标：
- node mapping precision/recall；
- relation preservation precision；
- role-direction error rate；
- mapping coverage；
- ambiguity calibration；
- false analogy acceptance；
- OOD abstention quality；
- candidate enumeration count / wall-clock / memory；
- 未见对象、属性重命名、关系重命名和新组合迁移。

必须按对象实例、关系族、生成模板和上下文分组隔离。候选生成器不得访问 Test truth；独立 evaluator 不得复用候选生成器的内部状态。

## 7. 当前可复用组件与下一步

优先复用：
- E10-A 有限版本空间的候选预算、显式拒答、OOD 状态和证据更新思想；
- E10 prequential ledger / shared protocol 的事件顺序与结构版本谱系；
- E12-A1/A3 的类型化候选表示；
- E12-A2 的信息增益/成本选择器；
- XSL-1 的确定性关系保持验证。

不应直接复用为同一语义模型：
- E10-A 无序角色规则与 XSL 有序关系；
- E12-A3 二元特征谓词与任意高阶超边；
- XSL 验证器与自动映射发现；
- E12-A2 似然表与真实传感器执行。

**建议下一项实际代码任务：先实现 v0.1 的 RelationSchema / RelationInstance / EvidenceEvent 校验器和四个 adapter 的契约测试，再做有限图 exact mapping enumerator。** 这会先解决语义错接问题，并为后续引入易象的多视角投影、阴阳对偶、爻位条件和变换候选提供稳定的可验证接口。

## 8. 证据与限制

本审计检查了以下分支中的具体代码与测试：
- `research/e10bc-joint-analogy-operator-2026-11-11`
- `research/e10a-finite-relational-version-space-2026-11-11`
- `research/e12-a3-relational-primitive-induction-2026-11-11`
- `research/yixiang-typed-analogy-mvp-2026-11-11`

XSL-1 的最新精确 head commit：`cea59c40ff3a3c3d49cac91d2d01e995dea96d91`。该 commit 对应的 GitHub Actions `tests` Run #42963677970 在审计时仍处于运行中：unit-tests 步骤已完成成功，E01-C 已完成成功，E02-A 正在运行，后续 E02 步骤尚未完成。因此本文件不宣称该 workflow 全部通过。

E10-A/B/C 文档中记录了若干历史实验运行结果；这些结果只适用于相应的合成任务、固定 DSL、种子和预算，不代表开放世界智能、一般语义类比或 Transformer 替代能力。

本文件是接口审计与执行方案，不是已实现的 v0.1 共享运行时，也不构成性能结论。
