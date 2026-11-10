# E02-I2：关系身份与谱系（设计与证伪协议）

## 1. 研究问题

E02-I 已验证有限场景中的结构保持、重配置、退化与退役。它仍把“关系”近似为成员集合与真值表签名。下一步必须区分：

\[
\text{Relation Identity} \neq \text{Relation Structure}
\]

结构变化不必然意味着关系身份改变；成员相似也不意味着两个关系拥有同一身份。

E02-I2 的问题是：在隐藏真实身份和变化谱系的条件下，系统能否为跨窗口候选关系分配稳定身份，识别结构版本变化，并在 split / merge / suspend / reactivate 等情况下保留可审计的证据来源？

## 2. 核心数据模型

### 2.1 RelationIdentity

身份对象只描述持续存在的关系实体，不直接承载某个结构版本的全部属性。

建议字段：
- `identity_id`：不可复用的稳定 ID。
- `status`：ACTIVE / SUSPENDED / SPLIT / MERGED / REPLACED / RETIRED。
- `created_at_window`、`last_active_window`。
- `parent_identity_ids`、`child_identity_ids`：有类型的谱系边索引。
- `identity_confidence`：身份连续性判断的校准分数，不等同于关系成立概率。

### 2.2 RelationVersion

每个身份可拥有多个不可变结构版本：
- `version_id`、`identity_id`、`version_index`。
- `members`、`roles`、`operator`、`rule`。
- `context_signature`：成立环境/条件。
- `valid_from_window`、`valid_to_window`。
- `evidence_refs`：证据记录引用，不存聚合置信度副本。

版本内容不可原地覆盖。MODIFY 必须新增版本并保留前一版本。

### 2.3 LineageEdge

谱系边必须有类型、方向、窗口和证据：
- MODIFIED_FROM：同一身份的版本演化。
- SPLIT_FROM：一个父身份分化为多个子身份。
- MERGED_FROM：新身份由多个父身份合并而来。
- REPLACED_BY：旧身份被语义上不同的新身份取代。
- REACTIVATED_FROM：可选审计边，指向同一身份此前的最后一个活动版本；不得创建伪造的新身份连续性。

谱系边不能只由成员 Jaccard 相似度决定。

## 3. 事件语义与不变量

| 事件 | 身份行为 | 结构版本行为 | 必须满足的不变量 |
|---|---|---|---|
| KEEP | 保持同一身份 | 不新增版本 | 证据持续有效，结构未发生实质变化 |
| MODIFY | 保持同一身份 | 新增版本 | 有版本差异记录；旧版本不可变 |
| SPLIT | 父身份转为 SPLIT | 创建多个子身份 | 每个子身份独立验证；父证据按角色/成员相关性筛选 |
| MERGE | 创建新身份 | 新身份创建初始版本 | 保留全部父来源；冲突证据不得丢弃或平均抵消 |
| SUSPEND | 保留身份 | 不要求新增版本 | 暂停不等于退役；保留最后活动状态与原因 |
| REACTIVATE | 恢复同一身份 | 无结构变化可沿用版本；变化则新建版本 | 必须有新的独立确认，不得仅因成员相似而恢复 |
| REPLACE | 创建新身份，旧身份结束 | 新身份创建初始版本 | 记录 REPLACED_BY；不能把旧身份证据直接迁移成新身份支持 |
| RETIRE | 身份进入终态 | 不再接受新活动版本 | 终态不可被普通 KEEP/MODIFY 复活 |

**终态规则：** RETIRED、SPLIT、MERGED、REPLACED 不得通过普通事件恢复；如后续发现相似关系，应创建新身份并显式建立谱系关系。

**身份与版本规则：** identity_id 不随成员顺序变化；角色置换需经过角色对齐，不能直接当作身份改变。

## 4. 身份匹配与决策层

E02-I2 不应把身份匹配混入候选发现器。先独立生成候选，再由 lineage resolver 进行身份分配。

候选与历史身份的匹配特征至少包含：
1. 角色对齐后的成员/结构差异；
2. 规则语义与算子等价性；
3. 上下文/环境兼容度；
4. 独立证据的时间连续性；
5. 支持与反例的来源连续性；
6. 变化是否符合 MODIFY、SPLIT、MERGE 等可解释事件。

建议采用两阶段决策：
- **匹配阶段：** 生成候选身份对应图，计算每条边的可解释分数；允许 ABSTAIN。
- **事件阶段：** 结合全局约束决定 KEEP / MODIFY / SPLIT / MERGE / SUSPEND / REACTIVATE / REPLACE / RETIRE。

全局约束：
- 普通 KEEP/MODIFY：一个候选最多匹配一个身份，一个身份每窗口最多匹配一个候选。
- SPLIT：一个父身份可连接多个新子身份，但必须有分化证据。
- MERGE：一个新身份可连接多个父身份，但必须有联合关系证据。
- 匹配不确定时必须 ABSTAIN，不得强行选择最高分候选。

至少比较以下基线：
- Exact signature matching；
- Jaccard member overlap + threshold；
- 角色对齐后的结构距离；
- Hungarian / bipartite matching；
- embedding similarity + threshold；
- lineage-aware resolver；
- oracle identity 上界（仅用于评估，不可用于系统决策）。

## 5. 证据继承与来源约束

证据必须保存为可追溯记录，至少包含：
- evidence_id、sample_id、window、environment；
- source relation/version；
- 涉及成员、角色和变量状态；
- 支持/反例类型；
- 原始预测与观测结果；
- 采集与验证分割；
- 是否允许用于子关系或合并关系的再次验证。

禁止直接把父关系置信度复制给子关系，也禁止将多个父关系置信度做平均。

### SPLIT
子关系只可引用与其成员、角色和规则投影相关的父证据。所有继承引用必须保留父来源；子关系仍需独立 Gate 确认。父关系的反例不能因为拆分而被删除。

### MERGE
合并关系可保留所有父证据作为来源，但冲突必须并存。只有对合并规则有直接支持的证据才可进入其有效支持集；父关系各自成立不等于合并关系成立。

### MODIFY / REPLACE
MODIFY 保留身份谱系，但新版本的证据状态必须重新计算。REPLACE 不继承旧身份的有效支持，只保留审计链接。

## 6. 合成实验协议

隐藏真实 identity、version 和 lineage。生成器只负责产生观测数据；系统不能读取事件计划。每个 episode 至少包含 6 个窗口，独立 train / Gate / Test 分割，Test 不参与身份匹配、事件决策或证据转移。

### 场景族

1. **Stable identity：** 结构和上下文不变。
2. **Role permutation：** 成员顺序或角色编码变化，但语义身份不变。
3. **Modify：** 同一关系身份的成员、角色或规则发生可解释变化。
4. **Split：** 一个关系分化为两个或多个可独立验证的子关系。
5. **Merge：** 多个关系形成一个新关系，要求联合证据。
6. **Temporary dropout：** 关系短暂不可观测，随后以相同身份恢复。
7. **Reappearance after retirement：** 已终态退役后出现相似结构，必须创建新身份。
8. **Same members, different semantics：** 成员相同但规则/角色/上下文不同，检验错误合并。
9. **Parallel similar relations：** 同时存在成员高度重叠但身份不同的关系。
10. **Ambiguous lineage：** 证据不足以决定身份，正确行为是 ABSTAIN。
11. **False split / false merge traps：** 通过局部噪声制造表面相似或表面分化。

### 防泄漏要求

- identity_id、事件类型和谱系图仅用于生成器内部与最终审计。
- 候选发现、身份匹配、事件分类、证据继承均不得读取隐藏真值。
- 每个 split 的 sample_id 必须互斥。
- 所有搜索尝试、阈值、候选图和拒绝原因都要记录。
- 测试分布包含未见过的变化组合，不能只测试预定义事件的简单重放。

## 7. 评估指标

必须分别报告：
- Identity precision / recall / F1；
- Identity switch rate；
- Lineage edge precision / recall / F1（按边类型分别报告）；
- Event classification macro-F1；
- False merge rate / false split rate；
- Reactivation precision；
- ABSTAIN precision 与 coverage；
- Evidence transfer precision / recall；
- Evidence provenance completeness；
- Version reconstruction accuracy；
- 事件延迟、候选图规模、时间与内存成本。

准确率不能掩盖错误合并。尤其需要单独报告 false merge，因为把两个独立关系合并为同一身份会污染后续全部证据。

## 8. 预注册证伪标准

出现以下任一情况，不得宣称 E02-I2 通过：
- role permutation 导致大量 identity switch；
- 同成员不同规则被系统性合并；
- split/merge 的谱系边 F1 低于简单 bipartite baseline；
- 临时 dropout 被误判为 RETIRE，或退役身份被普通 REACTIVATE 恢复；
- 子关系继承了不相关父证据，或合并关系把冲突证据平均抹平；
- ABSTAIN 被强制决策替代；
- 仅在生成器已知事件模板上有效，未见变化组合显著失败。

所有门槛必须在锁定测试前确定；若根据测试结果修改算法，必须使用新种子和新测试集重新验证。

## 9. 与周易类象思想的接口

周易思想在此阶段只作为可检验的结构启发，不作为身份判定的真值来源：
- **象：** 候选关系的可观测结构/角色配置；
- **位：** 成员在关系中的角色与位置；
- **时：** 窗口、环境和有效期；
- **变：** 版本变化与事件；
- **应：** 跨关系或跨环境的对应关系；
- **承乘比应：** 可作为角色依赖/关系约束的候选操作符。

这些术语必须映射到明确的数据结构和可证伪操作。不能用卦象相似度直接继承身份或证据。

## 10. 实施顺序

- I2-A：定义 identity/version/lineage 数据模型与不可变事件日志。
- I2-B：实现 Exact/Jaccard/Hungarian 基线和 ABSTAIN。
- I2-C：实现 KEEP/MODIFY/SUSPEND/REACTIVATE/REPLACE/RETIRE。
- I2-D：实现 SPLIT/MERGE 及证据 provenance 约束。
- I2-E：构造隐藏身份的合成生成器和防泄漏审计。
- I2-F：多种子评估、OOD 变化组合、强基线比较。
- I2-G：消融身份特征、上下文特征、证据连续性和类象启发。

在 I2-F 通过之前，不把谱系学习接入 E03 主引擎。
