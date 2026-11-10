# E10-A 预注册协议与 v2 生成器一致性审查（2026-11-10）

状态：基于 GitHub 源码与文档的静态交叉审查；未运行 v2 测试，未修改并行分支，未产生实验结果。

审查对象：
- 预注册协议：`research/e10a-structure-induction-protocol-2026-11-10` / `docs/E10A_STRUCTURE_INDUCTION_PREREG_2026-11-10.md`
- v2 生成器：`research/e10a-latent-world-generator-2026-11-10` / `prototype/e10a_latent_generator.py`
- v2 说明：`docs/E10A_LATENT_WORLD_GENERATOR_V2.md`

## 1. 结论

v2 是可复用的第一阶段合成关系模板生成器，但不是预注册 E10-A 的完整实现。二者研究目标有交集，却在任务对象、数据生成机制、划分策略和评测接口上存在规格差距。

因此当前准确状态应写为：

- 已实现：episode 内属性条件二元/三元关系模板、角色顺序与展示顺序分离、上下文负例、角色近失负例、基本 learner/evaluator 视图、episode/object identity 隔离。
- 未实现：对象束恢复任务、多关系共享中间对象的组合拓扑、属性/关系缺失与噪声实验臂、四重 OOD split、support/query 隐藏标签协议、结构恢复指标、统一基线与正式实验。
- 未证明：跨 episode 稳定语义、关系算子迁移、开放环境自主发现。

## 2. 规格差距矩阵

| 预注册要求 | v2 当前状态 | 判断 |
|---|---|---|
| 对象类型、属性、行为状态 | 对象只有离散属性键值 | 部分覆盖 |
| 有向二元关系 | 参与者展示顺序被打乱，角色真值单独保存；模板角色约束存在 | 部分覆盖，不能据此评估方向恢复 |
| 带角色槽位的三元关系 | 奇数模板使用三元角色 | 部分覆盖 |
| 条件化关系 | 单一 context key/value 门控 | 部分覆盖 |
| 两条关系共享中间对象 | 每个模板独立采样角色对象，没有显式关系组合图 | 未覆盖 |
| 属性缺失率实验 | 无 missingness 参数 | 未覆盖 |
| 关系实例漏观测 | 无 omission 参数 | 未覆盖 |
| 标签翻转噪声 | 无 label-noise 参数 | 未覆盖 |
| 干扰对象比例 | 有固定对象池，但不是受控 distractor 实验臂 | 未覆盖 |
| 对象身份隔离 | split manifest 检查 episode/object ID | 已覆盖基础项 |
| 表面属性组合隔离 | 未实现 | 未覆盖 |
| 关系模板隔离 | 未实现 | 未覆盖 |
| 关系组合隔离 | 未实现 | 未覆盖 |
| Support -> hidden Query | 所有 observation outcome 均在 learner view 中 | P0 阻断 |
| 对象束/角色/关系骨架结构指标 | 当前主要是生成器必要条件报告 | 未覆盖 |
| 随机、查表、近邻、固定模板、E09、图/超图、CEGIS 基线 | v2 分支没有统一 benchmark runner | 未覆盖 |
| 易象先验消融 X0-X6 | 协议要求主实验 X0，后续单独消融；v2 不是先验实验 | 未开始 |

## 3. 必须区分的三个层次

### A. 数据生成器正确性

检查生成的潜在模板、实例、对象引用和观测是否内部一致。这是 v2 当前主要覆盖的层次。

### B. 任务可识别性与评测有效性

给学习器带标签 support 和无标签 query；由 evaluator 保存 query 真值；用有限 DSL 枚举所有与 support 一致的机制，并判定唯一、歧义或不一致。这一层当前尚未完成。

### C. 学习器能力与架构主张

在冻结的数据协议上比较基线、E09、图/超图或 CPG-EI 候选学习器，测结构恢复、OOD 泛化、拒答和成本。当前没有正式结果。

不能从 A 直接跳到 C。

## 4. 规格收敛建议

不要一次性把预注册协议所有任务塞进 v2。建议保留 v2 作为 generator v2，并定义分阶段验收：

### E10-A1：单 episode hidden-query 关系归纳

- 保留现有属性条件关系模板与上下文门控。
- 每个模板按实例分组切分 support/query，避免同一 observation 重复。
- support 带 outcome；query 只提供对象、参与者、关系符号、context。
- query 标签、role map、violation、template ID 和生成器真值全部放入 evaluator。
- query 的对象组合不得与 support 完全重复；同时记录是否出现过单个对象，防止把组合泛化误写成身份泛化。
- 加入有限 DSL oracle：对候选 feature key、角色值元组、context key/value、arity 穷举，与 support 完全一致的候选按结构同构归并。
- oracle 返回三态：`IDENTIFIABLE`、`AMBIGUOUS`、`INCONSISTENT`。AMBIGUOUS 样本必须允许 abstain。

### E10-A2：符号双射与顺序不变性

对同一个 latent episode 做独立双射重命名：object IDs、attribute keys、attribute values、relation symbols、context keys/values。只允许表面符号变化，潜在结构不变。验证 canonical structure 与 oracle 结果保持同构。

不能用不同随机 seed 生成两个 episode 代替同一世界的双射置换测试。

### E10-A3：结构 OOD 与噪声

分别实现并单独报告：
- attribute-combination OOD；
- relation-template OOD；
- relation-composition OOD；
- attribute missingness；
- relation omission；
- label flips；
- distractor objects。

不要把所有 OOD/noise 混成一个 aggregate score。

### E10-A4：多关系组合任务

引入显式 latent relation graph，允许两条或多条关系共享中间对象，并将“关系原语已知、组合拓扑未见”作为独立 L2 测试。该任务才开始真正覆盖预注册协议中的关系组合泛化。

## 5. E10-A1 的最小数据边界

Learner payload 仅允许：
- schema version；
- objects 及其可见属性；
- support 观测（含标签）；
- query 观测（不含标签）；
- 明确公开的任务约束。

Evaluator payload 独占：
- query 标签；
- query role mapping；
- violation class；
- latent template 与生成参数；
- oracle 候选集合、同构等价类和 identifiability 状态。

必须有测试证明：改变 evaluator query truth 不会改变 learner payload 的序列化字节或 hash。不能把 `Episode` 或 truth 对象引用直接传给 learner。

## 6. E10-A 当前能力声明建议

推荐使用以下表述：

> E10-A v2 已具备受控的潜在属性条件关系模板生成能力，可生成带角色约束和上下文门控的二元/三元关系观测。当前尚未实现 support/query 隐藏标签评测、有限假设空间唯一性 oracle、四重 OOD 划分、多关系组合结构和统一基线实验。因此它是结构归纳基准的数据生成组件，不是结构发现能力的实验验证。

## 7. 下一步优先级

1. 先实现 A1 的 support/query schema 和标签泄漏测试。
2. 再实现有限 DSL oracle 与三态可识别性 fixture。
3. 实现同一 latent world 的符号双射重命名。
4. 只有 A1-A2 的协议测试通过后，才跑 random、majority、lookup、nearest-neighbour、fixed-template 基线。
5. 再逐步扩展到预注册协议的四重 OOD、多关系组合和噪声实验。
6. 保持 X0 无易象先验为主实验；X1-X6 作为单独消融，且加入先验失配与拒绝实验。

本审查不要求推翻 v2，也不要求其他并行分支停工。它的作用是明确 v2 当前覆盖范围，防止研究规格与代码能力混淆。
