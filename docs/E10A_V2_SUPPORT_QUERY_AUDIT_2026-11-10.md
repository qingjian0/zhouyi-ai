# E10-A Latent Generator v2 审查与 Support/Query 协议（2026-11-10）

状态：对并行分支 `research/e10a-latent-world-generator-2026-11-10` 的静态代码审查；未运行其测试，未修改其代码，未产生性能结果。

审查文件：
- `prototype/e10a_latent_generator.py`
- `tests/test_e10a_latent_generator.py`
- `docs/E10A_LATENT_WORLD_GENERATOR_V2.md`

## 1. 总体判断

v2 是有效的工程进步：它先定义属性条件关系模板，再生成实例；角色对象与观测参与者顺序分离；提供 context-negative 和 role-near-miss；校验 observation/truth 引用；生成 learner/evaluator 两种视图，并为 split 计算内容哈希。

但 v2 目前只能称为**带可观测标签的合成关系分类数据生成器**，不能直接称为支持样本归纳—隐藏查询预测的结构发现基准。它也没有证明开放环境自主发现。

## 2. 阻断问题

### P0：所有 observation outcome 都暴露给 learner

`Episode.learner_view()` 对每一条 observation 输出 `outcome`。当前没有 support/query 分层，也没有隐藏 query label 的数据接口。

这导致：
- 若把 learner view 当作模型输入，测试样本的标签已经泄漏；
- 若把全部 observation 当作训练样本，实验只验证拟合已标注关系，而不是从 support 归纳后预测 query；
- 当前测试只确认 learner view 没有 role/template truth 字段，不能证明 query 标签隔离。

**修复要求：** learner task 必须显式分成带标签 support 与不带标签 query。query 的正负标签、role map、violation 类型只能出现在 evaluator payload。

### P1：identifiability_report 不是 oracle 唯一性证明

当前报告检查正例数、角色属性值互异、角色支持数量和属性可见性。这些是必要条件检查，不是对候选假设空间的枚举，也没有证明只有一个结构同构等价类符合 learner evidence。

此外，字段名 `identifiable_up_to_role_permutation` 容易被过度解读。当前实现并未枚举竞争机制，也没有验证上下文门控与角色约束在所有观测上是否唯一。

**修复要求：** 定义有限 DSL：模板属性键、角色值分配、context key/value 和关系 arity。枚举所有与 support 完全一致的候选机制，按预先定义的同构关系去重：
- 一个等价类：identifiable；
- 多个等价类：ambiguous，要求 abstain；
- 零个等价类：out-of-model / inconsistent。

oracle 仅供 evaluator 使用。

### P1：符号置换测试没有测试置换不变性

现有 `test_determinism_and_symbol_renaming` 使用不同 seed，并检查 object IDs 不相交、learner view 不相等。这只证明随机输出不同，不证明对同一个潜在世界执行双射重命名后，结构预测保持等价。

**修复要求：** 对同一个潜在 world 应用独立双射置换（object ID、attribute key/value、relation symbol、context key/value），再比较 canonical truth 与 learner task。置换必须保持结构同构；不能用不同 seed 替代置换测试。

### P2：跨 episode 机制迁移尚未定义

每个 episode 独立随机生成属性 key/value、关系 symbol 和模板。当前可测的是单个 episode 内的关系模式恢复，不能证明跨 episode 形成稳定概念或可迁移算子。

**修复要求：** 分开报告：
- within-episode induction：同一 episode 的 support -> query；
- cross-episode transfer：训练 episode 学到的机制迁移到新对象/新表面符号；
- template OOD：未见机制识别，允许 abstain。

不能把三个任务混成一个准确率。

## 3. 建议的最小数据接口

### LearnerTask（只交给学习器）

- `schema_version`
- `objects`：对象 ID 与可见属性
- `support`：带 outcome 的已标注观测
- `query`：候选关系观测，不包含 outcome、role map、violation、template ID
- 可选的公开任务约束（例如 arity）；不得包含生成 seed 或 truth hash

### EvaluatorTruth（只交给评测器）

- query ID -> valid/invalid；
- query ID -> canonical role-to-object mapping（仅适用于定义了角色真值的候选）；
- query ID -> violation class；
- 潜在模板、生成参数、候选机制集合与 oracle identifiability 结果。

### 必须成立的不变量

1. support 与 query observation IDs 不重叠。
2. query outcome 不存在于 learner payload 的任何嵌套字段中。
3. query role map、template ID、violation、truth hash 不存在于 learner payload。
4. learner payload 序列化后再交给 learner；不传 Episode 或 truth 对象引用。
5. evaluator 对 query 标签做 mutation，不得改变 learner payload 字节或 hash。
6. query 候选不得与 support 的完全相同对象组合重复；若任务允许重叠，必须明示是重复观测而非 held-out query。
7. 每个 query 的可识别性由 oracle 单独标注；ambiguous 样本的正确行为是 abstain。

## 4. 最小实验矩阵

| 实验臂 | Support | Query | 目标 |
|---|---|---|---|
| A1-in-distribution | 模板内正例与负例 | 新对象组合 | 角色/关系恢复 |
| A1-order-perturb | 同上 | 同一 query 的参与者顺序置换 | 排除位置捷径 |
| A1-symbol-bijection | 同一潜在世界的重命名副本 | 重命名后的 held-out query | 检验符号置换不变性 |
| A1-ambiguous | 故意对称/缺少区分证据 | 多解 query | 检验 abstain |
| A1-identity-OOD | 训练对象与测试对象完全不交叉 | 新对象 query | 检验对象身份泛化 |

A1 不应同时承担跨 episode 迁移、组合拓扑 OOD 和开放集模板发现；这些分别作为后续实验。

## 5. 当前可保留的 v2 能力

- 潜在属性条件关系模板先于观测生成；
- 关系角色映射与参与者展示顺序分离；
- 正例、上下文反例、角色近失反例；
- episode 内对象引用和 truth 对齐的基本完整性检查；
- learner/evaluator 视图的初步分离；
- identity-disjoint split 与哈希记录。

这些成果值得保留。建议在其上增加 support/query 层，而不是推倒重写。

## 6. 下一步执行顺序

1. 在独立分支复制/扩展接口设计，不直接改并行分支。
2. 先写 schema 与信息泄漏测试，确保 query 标签无法进入 learner payload。
3. 实现有限 DSL oracle 枚举，并构造 identifiable / ambiguous / inconsistent 三类 fixture。
4. 对同一 latent world 实现双射符号重命名测试。
5. 通过上述门槛后，再训练简单 baseline；先跑 random、majority、fixed-template 与 nearest-neighbor。
6. 最后才把 E09 或新型非梯度结构学习器接入同一冻结数据接口。

**结论：** v2 解决了“随机关系没有潜在规律”的第一层问题，但没有解决“隐藏查询、唯一可识别性、符号重命名不变性”的实验有效性问题。当前不应据此宣称 E10-A 已验证结构发现能力。
