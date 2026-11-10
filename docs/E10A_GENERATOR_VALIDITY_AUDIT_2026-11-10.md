# E10-A Generator Validity Audit（2026-11-10）

状态：对 `research/e10a-generator-prototype-current-2026-11-10` 的静态审查；未运行测试；未生成实验结果。
审查对象：
- `prototype/e10a_generator.py`
- `tests/test_e10a_generator.py`

本审查只新增文档，不修改该分支的代码或测试。

## 1. 总结判断

当前生成器实现了 learner-view 与 audit-view 的字段分离、随机表面符号、对象/关系记录生成，以及对象身份不重叠的基础 split 检查。

但它尚未生成“具有可恢复潜在规律”的关系结构。关系参与者基本由随机抽样决定，属性值随机分配，关系上下文每条随机生成。没有稳定的关系模板、跨对象可复用结构或由属性/上下文决定的关系规律。因此它目前适合作为随机关系负对照或 schema smoke test，不适合作为 E10-A 结构发现主基准。

## 2. 阻断性问题

### 2.1 没有可学习的潜在结构

`generate_episode` 为每条关系随机抽取 2/3 个参与对象。没有先生成潜在关系模板、角色约束、关系组合规则或条件有效域，再由观测器生成可见记录。

结果是：学习器看见的是随机超边样本，而不是由可复用机制产生的观测。即使学习器表现接近随机，也无法区分“架构能力不足”与“数据本身不可识别”。

**修正要求：** 先生成潜在程序/结构，例如若干关系原语、角色槽位约束、对象属性约束和条件变量；由该结构实例化多条关系，再把潜在真值隔离给评测器。

### 2.2 对象属性与关系没有生成机制上的联系

每个对象的每个属性值独立随机抽取；关系参与者也独立随机抽取。属性不影响对象角色，角色也不受关系模板约束。

因此对象属性无法帮助推断关系角色，属性束与关系骨架之间没有可检验的联系。

**修正要求：** 潜在生成程序应规定“属性/状态—角色资格—关系成立”的生成链；同时构造属性相似但角色不符的 hard negatives，防止单纯属性匹配得到高分。

### 2.3 关系符号和上下文没有可迁移语义

两个不透明 relation symbols 通过 `index % 2` 分配，但它们没有对应不同的可观测角色约束或结构机制。context 每条关系独立随机生成，也没有复用、阈值或条件变化。

因此当前无法测量：
- 关系类型恢复；
- 同一关系模板在新对象上的实例化；
- 条件关系有效域恢复；
- 环境变化下的关系迁移；
- 关系组合的 OOD 泛化。

**修正要求：** 每个 relation symbol 必须对应可审计的潜在关系机制；上下文变量必须影响关系成立，并设计跨环境有效/失效样本。

### 2.4 role truth 与 learner view 的任务边界定义不清

audit truth 中 `role_names` 为固定 `role_a/b/c`，`role_objects` 直接复制 observation 的 `participants` 顺序；learner view 暴露相同的有序 participants，却不暴露 role_names。

这意味着当前数据没有真正隐藏参与者的角色映射：参与者位置与 truth 位置直接一一对应，但角色名称是不可观测的任意符号。评测若按任意 role_a/role_b 名称要求恢复，会引入标签置换歧义；若只要求恢复位置，则只是恢复输入本身的顺序。

**修正要求：** 明确角色是可观测有序槽位，还是隐藏的、需由属性和结构推断的角色。若角色隐藏，生成器应随机置换参与者呈现顺序，并在 audit truth 中保留真实角色映射；若角色有序可见，则不应把它作为隐藏学习目标。

## 3. Split 与测试审查

### 3.1 当前 split 只检查身份隔离

`build_split_manifest` 检查 episode ID 和 object ID 不重叠，但不检查：
- 表面属性组合隔离；
- 关系模板隔离；
- 关系组合隔离；
- 环境条件隔离；
- train/test 的潜在程序是否真的独立；
- test 是否只把 train 关系换对象名。

因此它只能称为 identity-disjoint split validator，不能称为预注册协议要求的四重隔离。

### 3.2 split manifest 缺少可复现审计字段

manifest 没有 seed、生成器版本、潜在模板摘要、split 策略、观测噪声配置或数据内容哈希。传入的 train_ids/test_ids 与 Episode 本身也没有绑定校验。

建议 manifest 包含：
- generator_version / schema_version；
- seed 列表；
- episode ID 与实际 episode 的一一映射；
- train/test 潜在模板族；
- 对象/属性/关系组合隔离断言；
- 噪声和缺失率；
- canonical learner-view 内容 hash；
- evaluator-only truth hash（不得提供给 learner）。

### 3.3 现有测试断言力度不足

- `test_surface_symbols_change_across_seeds` 只检查对象 ID 集合不相交，没有检查属性键/值、关系符号和上下文符号的重映射，也没有验证结构在重映射下保持等价。
- `test_role_order_is_preserved_while_record_order_is_not_semantic` 只检查长度和记录数量，没有对记录顺序不变性做输出比较，也没有验证角色映射可识别性。
- `test_truth_is_separate_from_learner_view` 检查序列化视图没有显式 truth 字段，但不构成完整的信息流隔离证明；仍需确保 learner 代码只拿到 learner_view，不持有 Episode 对象。
- identity collision 测试修改 object record ID，却没有同步更新 observation participants，制造了 episode 内部引用不一致的数据。它能触发 ID overlap 检查，但不应作为有效 episode fixture。

## 4. 建议重构为可识别生成器

### 4.1 潜在世界层

先生成隐藏的世界结构：
- ObjectType / ObjectState；
- RelationPrimitive（方向、元数、角色约束）；
- RoleConstraint（角色所需属性/状态）；
- ContextCondition（成立的环境区间/离散状态）；
- CompositionRule（多条关系如何共享中间对象或组成高阶结构）。

潜在结构应跨多个 episode 可复用，也应有明确的 held-out template families。

### 4.2 观测层

对潜在世界施加独立可控变换：
- object / attribute / relation / context symbol permutation；
- observation order permutation；
- participant presentation-order permutation；
- attribute missingness；
- relation omission；
- distractor objects / near-miss relations；
- source duplication and correlated observations。

每种变换应有独立开关和单独测试，不能把所有变化合并成一个随机 seed 效果。

### 4.3 真值层

truth 必须保存可评测的结构：
- canonical object roles；
- relation template identity；
- instantiated relation edges/hyperedges；
- context validity；
- composition ancestry；
- held-out query answers。

truth 只能交给 evaluator。训练入口应接收序列化后的 learner-view 数据，且不应持有 Episode 或 generator 对象。

### 4.4 可识别性检查

每个 benchmark task 都要证明：给定 learner-view，目标结构在预注册的等价类意义下可识别。对不可识别任务，评测目标应是 abstain/uncertainty，而不是强制猜标签。

必须加入随机关系基线、固定模板基线和 oracle upper bound；oracle 只能用于评估数据可识别上限，不能作为学习器输入。

## 5. 进入正式 E10-A 前的验收门槛

- [ ] 生成器先构造潜在结构，再实例化观测。
- [ ] 属性/角色/关系/条件之间存在可验证的生成依赖。
- [ ] 至少有一个对象身份隔离的 ID split。
- [ ] 至少有一个属性组合、关系模板、关系组合分别隔离的 OOD split。
- [ ] 随机符号置换不改变 canonical structure 的评测结果。
- [ ] participant 顺序变化的语义已明确，角色恢复指标不受任意命名影响。
- [ ] near-miss、缺失、漏观测、干扰对象分别有可控参数。
- [ ] learner 与 evaluator 通过独立序列化边界隔离。
- [ ] 生成器有确定性、可审计 manifest 和内容 hash。
- [ ] 有随机、查表、近邻、固定模板、E09、图/超图基线。
- [ ] 报告结构恢复、OOD、拒答、校准和计算成本。
- [ ] 正式运行前冻结协议和数据版本。

## 6. 当前结论

当前生成器的有效成果是 learner/evaluator 视图的初步分离和随机关系数据 schema。它尚未构成关系结构发现 benchmark。

下一步不应急着训练学习器，也不应把现有生成器输出上的通过率当作架构证据。应先修复潜在结构生成与可识别性，再实现 split 和基线。否则任何性能结果都缺少科学解释力。
