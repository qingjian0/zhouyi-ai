# E16：动态认知超图与可验证自我重构（2026-11-11）

> 状态：[设计]。本文是研究协议与架构提案，不代表 DCH 已实现，也不代表实验已执行。基线为 main 上 E02 动态超图设计、E02-C 生命周期原型和 CPG-EI v0.3 草案。

## 0. 本轮结论

E02 已提出高阶关系、动态超边和 CREATE/MERGE/SPLIT/PRUNE；E02-C 已实现确定性生命周期状态机。但现有原型是外部评估器驱动的结构治理脚手架，不是自主结构发现器。

E16 的研究目标不是再实现一个超边 CRUD 管理器，而是研究一个系统能否：
1. 从观察和预测误差中提出新的认知结构；
2. 在条件、角色、时间和证据谱系约束下比较竞争结构；
3. 选择局部重构操作并预测其影响；
4. 对受影响的下游结构执行选择性失效和重算；
5. 通过独立验证门控提交新版本；
6. 在资源预算内长期演化而不发生无界结构膨胀。

核心假设 H16：带有类型化高阶关系、条件化结构版本、依赖追踪和独立证据门控的动态认知超图，可能比仅维护超边集合的生命周期机制更可靠地支持结构发现、机制迁移和持续适应。该假设必须由 E16 实验检验。

## 1. 设计边界与已有工作关系

- E02-A：诊断高阶联合约束表达能力；不能单独证明动态超图优于静态超图。
- E02-C：确定性 CREATE/OBSERVE/MERGE/SPLIT/PRUNE/rollback 状态机；不负责候选发现，也不负责独立评估。
- E13：结构、类象、区分性查询与证据更新闭环。
- GPOI：从观察发现测量算子和原语。
- CGL：表示和执行类型化组合程序。
- DCC/CWU：安排认知工作、预算与并行任务。
- Cognitive DAG/SSCG：维护依赖、共享结构和选择性失效。

E16 不替代以上模块。DCH 是它们共享的结构底座；DCC 调度重构工作，GPOI 提出新原语，CGL 提出可执行程序，E13 产生区分性证据，CSL 管理证据和生命周期。

## 2. DCH 数学对象

定义时刻 t 的动态认知超图：

\[
\mathcal H_t=(V_t,E_t,\mathcal C_t,\mathcal P_t,\mathcal D_t,\mathcal X_t)
\]

- V：语义单元、状态、原语、概念、机制、程序、目标和证据节点。
- E：带角色的高阶关系超边。
- C：条件、适用域、环境、时间窗和上下文约束。
- P：证据来源谱系与来源依赖。
- D：结构依赖和派生依赖。
- X：版本、事件、执行效果与生命周期状态。

超边不是无序集合的别名。其参与者具有角色：
\[
e=(id,\rho,\{(v_i,r_i)\}_{i=1}^{k},c,s,p,d)
\]
其中 rho 是关系类型，r_i 是参与者角色，c 是条件，s 是作用域，p 是证据引用，d 是依赖引用。对于无序关系才允许置换不变聚合；对于施事、受事、条件、媒介、结果等角色必须保留顺序和角色身份。

### 2.1 关系语义分层

必须区分：
- ASSOCIATION：统计/经验关联；
- TEMPORAL：时间先后或同步；
- ANALOGY：跨域结构映射；
- CONSTRAINT：联合约束；
- MECHANISM_CANDIDATE：机制候选；
- CAUSAL_CLAIM：经干预或强识别设计支持的因果主张；
- DEPENDENCY：计算/结构依赖；
- SUPPORTS / CONTRADICTS：证据立场；
- TRANSITION：状态变化。

不能从共现边自动升级为因果边；不能从词面相似自动升级为类象映射；每次语义升级必须创建新版本并附带验证记录。

## 3. 节点、超边与结构版本

### 3.1 NodeRecord

最小字段：
- node_id、node_type、schema_version；
- payload_ref（大型数据外置存储，不把原始内容全部塞入图）；
- semantic_embedding_ref（可选，不作为语义真值）；
- provenance_refs；
- domain_scope、valid_time、created_at；
- epistemic_status、confidence、uncertainty；
- lifecycle_status、version、supersedes_refs。

### 3.2 HyperedgeRecord

最小字段：
- edge_id、edge_type、schema_version；
- participants：node_ref、role、position、role_type；
- conditions、domain_scope、valid_time；
- support_refs、counterexample_refs、source_groups；
- prediction_signature、validation_receipt_refs；
- compute_cost、reuse_count、uncertainty；
- lifecycle_status、version、parent_refs、supersedes_refs。

### 3.3 StructureVersion

结构更新不得原地覆盖：
- structure_id、version_id、parent_version_ids；
- operation、operation_parameters；
- input_snapshot_hash、grammar_version、operator_version；
- evidence_snapshot、validation_receipt；
- changed_node_refs、changed_edge_refs；
- dependency_invalidation_set；
- resource_cost、commit_status、created_at。

原始观察、证据事件和已发布结构版本均不可变。可通过投影构造当前视图，但不能删除历史来伪造“从未发生”。

## 4. 动态结构生命周期：从边操作到结构重写

操作集合：
- CREATE：创建新节点、边或结构子图；
- MERGE：合并语义等价或可组合的结构；
- SPLIT：按条件、机制、角色或预测残差拆分；
- PRUNE：停止激活或从默认工作集淘汰；
- RETYPE：修订关系类型；
- REWIRE：重连参与者或角色；
- ABSTRACT：从多个实例抽象出模式；
- SPECIALIZE：将通用结构细化到特定条件域；
- SUSPEND / REACTIVATE：暂停或恢复调用；
- REPLACE：以新版本替代旧版本，但保留旧结构；
- ROLLBACK：回到已验证的历史投影，不删除事件历史。

### 4.1 MERGE 的安全条件

成员重叠度只作为候选召回信号，不能作为合并充分条件。必须检查：
1. 关系类型兼容；
2. 角色映射存在且保持语义；
3. 条件和适用域可合一，或明确形成条件析取；
4. 证据来源不冲突，支持/反例没有被并集操作抹平；
5. 合并结构在独立验证集上不退化；
6. 合并后的预测签名没有把两个不同机制混为一体；
7. 复杂度/成本收益优于保留两个结构。

若两个结构只在部分上下文兼容，应创建带条件分支的上层结构，而不是简单并集。

### 4.2 SPLIT 的安全条件

SPLIT 不应强制所有子边对父边成员做无重叠集合分区。应区分：
- MEMBER_PARTITION：参与者集合确实分区；
- CONTEXT_SPLIT：相同参与者在不同条件下形成不同机制；
- ROLE_SPLIT：角色解释存在稳定分歧；
- MECHANISM_SPLIT：同一表面模式由不同作用机制产生；
- TEMPORAL_SPLIT：结构随阶段或时间发生变化；
- EVIDENCE_SPLIT：支持证据实际来自不同数据生成机制。

子结构可以共享节点，但必须明确分裂维度、互斥/重叠条件和适用范围。拆分后应检查子结构是否覆盖父结构原有适用域，未覆盖部分标记为未知，不能静默丢弃。

### 4.3 PRUNE 与删除的区别

PRUNE 首先表示不再默认激活，不等于删除知识。至少有：
- ACTIVE：默认可参与检索/推理；
- DORMANT：保留但不主动激活；
- SUSPENDED：存在关键反例或待验证冲突；
- SUPERSEDED：被新版本替代；
- REJECTED：在明确范围内被证伪；
- ARCHIVED：仅历史追溯。

全局硬删除不属于普通认知生命周期操作。

## 5. 自我重构闭环

每次重构按以下协议执行：

1. Detect：检测预测残差、反例、分布漂移、结构冲突、检索失败或成本异常。
2. Localize：沿依赖图确定最小受影响子图，不默认重建整个认知库。
3. Propose：由 GPOI、CGL、类象提议器、反事实提议器产生多个候选重写。
4. Predict：对每个候选预测其适用范围、收益、风险和依赖影响。
5. Challenge：主动寻找区分候选结构的观察、反例或干预。
6. Evaluate：在隔离评估器中执行结构选择和验证。
7. Commit：通过门控后创建新 StructureVersion；失败则保留候选记录但不进入已验证共享视图。
8. Invalidate：仅使依赖发生变化的派生结果失效。
9. Recompute：按优先级重算受影响节点。
10. Monitor：观察新旧分布表现、结构震荡和资源成本。

任何阶段都允许 ABSTAIN / BUDGET_EXHAUSTED / INSUFFICIENT_EVIDENCE；部分执行结果不得伪装成完整成功。

## 6. 证据谱系与独立性

支持样本数不等于独立证据数。EvidenceProvenance 至少记录：
- evidence_id、source_id、source_group_id；
- acquisition_batch、generator_id、environment_id；
- object_id、scenario_id、time_window；
- raw_observation_ref、annotation_protocol；
- supports/contradicts、reliability、uncertainty；
- independence_assumptions、known_dependencies。

同一原始来源的多个片段不能自动计作多份独立证据。结构门控按 source_group 或更高层级聚类计算有效支持量，并进行来源留组验证。

评估数据至少分为 Train、Discovery Validation、Independent Gate、Locked Test。候选搜索不能反复访问 Locked Test；结构选择与独立门控不能复用同一批验证数据而不做多重比较控制。

## 7. 结构重写目标与调度

不要只优化一个准确率或单一效用分数。对候选重写 m 记录多目标向量：
\[
J(m)=(
\Delta Q_{predict},
\Delta Q_{explain},
\Delta Q_{transfer},
\Delta Q_{evidence},
-\Delta Cost,
-\Delta Risk,
-\Delta Complexity
)
\]

由 DCC 在预算内维护 Pareto 候选，并根据目标选择探索、验证、压缩或停止。若需标量化，必须记录权重和敏感性分析。

MDL 风格目标可作为候选筛选而非最终真理：
\[
L(M)+L(D\mid M)+\lambda C(M)+\mu R(M)
\]
复杂结构只有在独立预测增益足以抵消结构、存储和计算成本时才应保留。

## 8. 增量失效与重算

为每个派生结果记录：
- program_hash；
- input_version_refs；
- structure_version_refs；
- grammar/operator/environment version；
- effect_set；
- output_hash；
- validation_status。

依赖变化时：
- 纯函数且全部输入版本不变：允许缓存复用；
- 任一输入或算子版本改变：结果标记 stale；
- 测量、随机、外部动作或状态写入：按效果语义决定是否可重放；
- 证据撤回/来源失效：沿证据依赖传播；
- 结构局部变化：只失效受影响闭包，不清空整个图。

需要分别报告 invalidation precision、recompute ratio、stale result leakage 和与全量重算的一致性。

## 9. 与易象思想的可检验连接

易象不作为固定标签库，而作为候选结构变换先验：

- 阴阳：生成对偶、互补、抑制/促进、方向反转等候选关系；
- 四象：探索两组二元状态的组合与阶段差异；
- 八卦：多维状态投影和视角切换；
- 六爻：位置、阶段、时间与条件化状态；
- 卦变：局部状态变化触发的结构转移候选；
- 五行：带方向、符号、强度、条件和时间的动态作用图；
- 象数理：分别产生结构投影、计数/组合、约束检验和机制解释操作。

这些只是现代计算映射假设，不声称等同于古代易学原义。必须与随机先验、通用结构先验、无易象模型比较。易象先验若没有独立增益，应允许被降权或移除。

## 10. 复杂度与内存控制

DCH 不应成为全量激活的巨大图数据库。采用分层存储：
- 原始观察/证据对象外置、不可变；
- 长期结构索引保存轻量节点、超边和依赖元数据；
- 热工作集仅激活与当前目标相关的子图；
- 中间结果按版本缓存；
- 低复用、低证据、过期结构转为 dormant；
- 大型向量和原始 payload 延迟加载。

单轮成本目标应依赖检索候选数 K、激活子图规模 G、工作集大小 T 和预算 B，而非无条件扫描历史总量 N。必须实测索引开销、最坏情况检索和回溯成本，不宣称恒定时间。

## 11. E16 实验矩阵

### E16-A：条件化结构重构
同一参与者集合在不同环境条件下具有不同机制。比较无条件 MERGE、条件化 MERGE、CONTEXT_SPLIT、机制分裂。指标：机制识别、条件边界准确率、错误合并率、覆盖率。

### E16-B：来源相关证据攻击
构造多个证据 ID 但共享来源/生成器/采集批次。比较按 ID 计数和按来源谱系计数。指标：错误接受率、校准误差、有效独立证据估计。

### E16-C：结构漂移与持续适应
环境分阶段改变机制。比较静态结构、CREATE/PRUNE、完整重构、完整重构+独立挑战查询。指标：新域适应、旧域遗忘、结构震荡、重构次数、恢复时间。

### E16-D：依赖失效正确性
随机改变节点、超边、算子和证据版本。比较全量重算、DAG 失效、DCH 局部失效。指标：结果一致性、失效精度、漏失效率、重算比例、延迟和内存。

### E16-E：结构复杂度与计算预算
扫描节点规模、候选阶数、候选预算、活跃工作集和历史规模。测量峰值内存、检索延迟、更新成本、超边数量和最坏情况退化。

### E16-F：易象先验消融
比较无先验、随机先验、通用结构先验、易象先验。保持参数量、候选数和搜索预算匹配。

### 对照组
1. Pairwise Graph；
2. Strong Pairwise Graph；
3. Static Hypergraph；
4. Learned Static Hypergraph；
5. E02-C 生命周期状态机；
6. Conditional Dynamic Hypergraph；
7. DCH + provenance + dependency invalidation；
8. DCH + active challenge + DCC；
9. Oracle structure（只作为上界）。

所有实验预注册数据生成器、分组拆分、随机种子、预算、指标和停止规则。至少区分数据生成随机性、模型初始化随机性和候选顺序随机性。报告均值、方差/置信区间和失败案例。

## 12. 证伪条件

出现以下情况时必须收缩设计：
- 条件化结构没有降低错误合并率；
- 来源谱系不能降低相关证据导致的错误接受；
- 完整重构不优于 E02-C 或静态超图；
- 结构更新带来显著震荡、遗忘或内存膨胀；
- 局部失效与全量重算不一致；
- 易象先验在参数和预算匹配后无独立增益；
- DCH 的索引和治理成本超过它节省的推理/重算成本。

## 13. 实施顺序

P0：
1. 先扩展数据契约：条件、作用域、来源组、依赖、结构版本；
2. 为 E02-C 添加有限数值校验、来源独立性接口和条件兼容接口；
3. 增加 CONTEXT_SPLIT、RETYPE、REWIRE 的纯函数提案与门控；
4. 将回滚改为事件追加、版本投影与重放测试；
5. 实现依赖失效闭包及全量重算对照。

P1：
6. 接入 E13 区分性查询；
7. 接入 GPOI/CGL 的候选结构提议；
8. 接入 DCC 的 Pareto 预算调度；
9. 实现 E16-A 至 E16-E 的合成基准。

P2：
10. 引入连续潜在结构提议器；
11. 引入易象先验消融；
12. 进行真实多模态与长历史工作集评估。

## 14. 本文状态与禁止性结论

本文只定义研究问题、数据契约建议、结构重构协议和实验计划。当前没有在本文分支中实现 DCH runtime、结构学习器、依赖失效引擎或 E16 实验；没有产生 E16 实验结果；不宣称 DCH 优于 Transformer、图网络或现有超图模型。

下一步应先完成 P0 的契约与审计修复，再开展结构学习实验。不要同时引入神经提议器、易象先验和新的重构操作，以免无法归因。
