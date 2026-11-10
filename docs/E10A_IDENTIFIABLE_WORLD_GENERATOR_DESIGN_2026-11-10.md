# E10-A 可识别潜在世界生成器设计（2026-11-10）

状态：研究设计稿；不是已实现生成器，不包含实验结果。本文基于当前 E10-A 生成器源码与静态审查，定义下一版数据生成器必须满足的语义契约。

## 0. 本轮结论

当前随机关系生成器不适合作为结构发现主基准：参与者、属性和上下文之间没有稳定的生成依赖。下一版不能只把随机抽样替换成固定模板；必须把“可识别性”作为数据集设计的首要约束。

本设计把任务分成三层：
1. **实例恢复**：从无标签观测恢复当前世界中关系实例及其角色。
2. **机制归纳**：从多个世界/episode 归纳可迁移的关系算子（角色约束、方向、条件）。
3. **组合迁移**：在训练中见过原语、但未见过组合的条件下预测新组合；另设真正未见原语模板的开放集识别任务，不把两者混为一谈。

## 1. 最小潜在世界（生成端）

每个 world 在生成任何对象或观测前，先固定以下潜变量：

- `ObjectState`：对象的属性状态；属性值由有限域取值，但其符号可在 world 间独立置换。
- `RelationPrimitive`：有向关系原语，包含唯一模板 ID、元数、角色集合及角色顺序的语义定义。
- `RoleConstraint`：每个角色需要满足的属性谓词；可包含多个必要条件，不允许只由一个显眼标签决定。
- `ContextCondition`：关系成立的环境条件（离散状态或区间）；必须存在条件满足与不满足的配对样本。
- `CompositionRule`：指定关系实例如何共享中间对象形成路径、分叉或闭环；共享对象必须同时满足两侧角色约束。
- `ObservationChannel`：独立控制符号置换、参与者呈现顺序、记录顺序、属性缺失、关系漏观测、干扰项和噪声。

生成顺序必须是：

`latent world -> object states -> valid relation instances -> composed structures -> candidate negatives -> observation transforms -> learner view / evaluator truth`

禁止先随机生成关系参与者，再事后给它们附加一个 truth 标签。

## 2. 最小可识别任务

### Task A：角色与方向恢复

每个关系至少有两个语义角色（例如 source/target），角色约束不同且不是单一属性即可区分。观测层随机打乱参与者呈现顺序；truth 保存角色到对象的映射。评测按角色映射计算，不按 tuple 位置计算。

必须提供三种对照：
- 正常方向正例；
- 相同对象、相同关系符号的方向反转负例；
- 属性近似但其中一个必要角色条件不满足的负例。

如果角色约束在观测中完全对称，则该样本在角色方向上不可识别，应标为 ambiguous，而不是强制要求猜中。

### Task B：条件有效域恢复（时/位/势的操作化）

对同一对象组和同一关系原语，生成 context 满足与不满足的成对候选。除 context 外，尽量保持其他字段一致。学习目标是恢复条件边界或状态依赖，而不是记忆某个 context token。

周易映射只作为可消融的结构假设：
- 时：context 状态/阶段；
- 位：角色槽位及其相对位置；
- 势：关系组合中的可达性、方向或约束压力；
- 变：状态变化后哪些关系保持、失效或转化。

不得把“时、位、势”直接当作正确标签；必须与随机结构先验、无先验和其他结构先验公平比较。

### Task C：组合关系迁移

先生成满足约束的关系链，例如 `A(x,m) AND B(m,y) -> composed_path(x,m,y)`。训练集可见 A、B 的原语实例，但不出现该组合形式；测试集检验模型是否能组合已学原语。

必须另外设置：
- 共享中间节点的真实组合；
- 仅外观相似但不共享合法中间节点的 hard negative；
- 中间节点角色条件不满足的 near miss；
- 关系顺序颠倒的反例。

不得把组合模板 ID、生成顺序、对象 ID 或 episode 编号编码进 learner view。

## 3. 负例矩阵（各因素独立开关）

| 负例类型 | 保持不变 | 破坏的条件 |
|---|---|---|
| role-near-miss | 关系符号、其余角色、context | 一个必要角色属性 |
| direction-reversal | 对象集合、关系符号、context | 方向 |
| context-invalid | 对象、角色、关系符号 | context 条件 |
| composition-break | 组成边及局部外观 | 中间节点共享/兼容性 |
| distractor | 对象属性分布 | 参与者组合无合法实例 |
| partial-observation | 潜在真实结构 | 隐藏部分属性或关系记录 |

每类负例必须单独计数、单独评测。禁止只报告一个混合准确率。

## 4. 符号置换与等价性

每个 world 使用独立随机双射置换：
- object IDs；
- attribute keys；
- attribute values；
- relation symbols；
- context keys/values。

同时独立扰动 observation 顺序和 participant 呈现顺序。置换前后 canonical latent structure 必须等价；结构指标必须在 canonical role/template 对齐后计算。

测试不能只检查 ID 集合不相交。必须检查：
1. 每一类符号均发生有效置换；
2. 置换是双射且无碰撞；
3. learner-view 内容确实改变；
4. evaluator canonical truth 在等价变换下保持一致；
5. 学习器输出经 canonicalization 后结果一致。

## 5. Split 设计：不要用一个 split 冒充所有泛化

- **S1 identity-OOD**：训练与测试对象身份完全不相交，模板相同。
- **S2 attribute-combination-OOD**：单个属性值在训练出现，但某些属性组合仅在测试出现。
- **S3 context-OOD**：训练覆盖部分环境状态/区间，测试覆盖未见状态或边界邻域。
- **S4 composition-OOD**：原语可见，组合拓扑（链/分叉/闭环）按预注册策略留出。
- **S5 template-OOD**：完整关系模板族留出。该任务是开放集/迁移任务，必须允许 abstain；不能与“组合迁移”混报。

每个 split manifest 至少记录：schema/generator 版本、种子、split 类型、模板族摘要、观测通道参数、episode IDs、对象 ID 集合、canonical learner-view hash、evaluator truth hash。truth hash 只用于审计，不能进入训练数据或模型输入。

## 6. 可识别性与拒答规则

对每个查询，评测器需判断 learner-view 是否足以唯一确定目标（允许预先定义的结构同构等价类）。

- 唯一可识别：要求给出结构预测。
- 存在多个同样符合观测的结构：要求输出 abstain/uncertain。
- 观测与任何候选机制都不一致：要求报告 unknown/out-of-model，而不是强行套用最近模板。

可识别性不能只靠生成器作者口头保证。实现时要加入有限规模 oracle 枚举：在该任务 DSL 的候选空间中枚举与 learner-view 一致的潜在结构，验证等价类数量。若超过一个等价类，自动标记为 ambiguous。此 oracle 只供评测器，不向 learner 暴露。

## 7. 信息隔离契约

- learner 接口只接收独立序列化的 learner-view 字节/对象，不接收 Episode、generator、truth 或 audit handle。
- evaluator truth 使用单独对象/文件/进程边界；禁止 learner 通过共享对象引用访问。
- learner-view schema 不含 label、role map、template ID、composition ancestry、生成 seed 或 truth hash。
- 测试应尝试递归检查 learner payload 字段，并对 truth mutation 做隔离测试；仅断言顶层没有 `truth` 字段不够。
- 记录数据集构建哈希和输入哈希，确保测试/评估时使用的是冻结版本。

## 8. 基线和报告

最低基线：
1. random；
2. majority / frequency；
3. nearest-neighbor；
4. fixed-template matcher；
5. graph / hypergraph structural baseline；
6. 现有 E09 非梯度方法；
7. 小型 oracle（仅给出该 DSL 下的可识别上限）。

至少报告：
- relation instance F1；
- role assignment accuracy（按 canonical role）；
- direction accuracy；
- context validity / boundary accuracy；
- composition exact match；
- OOD 分层结果；
- abstention precision/coverage 与 selective risk；
- 参数量、候选搜索量、运行时间和内存；
- 不同 seed 的均值、方差及失败案例。

所有方法使用相同 learner-view、训练样本、计算预算和超参数搜索预算。不能把 oracle 结果与可学习基线并列为普通模型成绩。

## 9. 进入实现的验收门槛

- [ ] 潜在机制先于实例和观测生成。
- [ ] 至少两个有方向的关系原语，角色约束不对称。
- [ ] 属性、角色、关系、context 之间有明确可执行依赖。
- [ ] 存在真实组合关系及共享中间节点。
- [ ] 六类负例可独立开关并分别评测。
- [ ] 五类 split 分开构建和报告。
- [ ] 四类符号置换和顺序扰动有独立测试。
- [ ] learner/evaluator 序列化边界通过隔离测试。
- [ ] oracle 可识别性枚举能识别 ambiguous 样本。
- [ ] manifest 可复现，含 learner-view hash。
- [ ] 基线、计算预算和指标在运行前冻结。

## 10. 当前研究决策

下一步实现顺序应为：
1. 先实现无噪声、单模板、角色不对称的 Task A，并用 oracle 验证可识别性；
2. 再加入 context 成对反例；
3. 再加入组合迁移；
4. 最后加入独立噪声通道与多种 OOD split。

在 Task A 未通过可识别性与符号置换测试前，不启动大规模训练，也不把任何准确率称为“自主发现”证据。
