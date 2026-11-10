# E10-A Latent-World Generator v2

状态：[原型设计与实现] 本文件定义一类可学习的合成关系世界。它不替代 E10-A 预注册协议，也不宣称完成关系发现。

## 1. 从随机超边改为潜在机制生成

v1 的主要问题是关系参与者随机抽样、对象属性独立随机、上下文随机。它没有稳定的生成规律，因此不能作为结构发现主基准。

v2 先定义潜在模板，再生成对象和关系观测：

`attribute(object, feature) = opaque_value`

`role_i(object) := attribute(object, feature_key) == role_value_i`

`relation(object_1,...,object_k | context)` 成立，当且仅当：
- 每个参与者满足其对应角色的属性约束；
- 参与者互不相同；
- 上下文变量等于模板要求的状态。

每个模板在同一 episode 内重复实例化。观测端随机打乱参与者呈现顺序；评测端保留真实 role-to-object 映射。

## 2. 可见信息与隐藏信息

Learner view：
- 不透明 object ID；
- 不透明 attribute key/value；
- 不透明 relation symbol；
- 无序语义的 participant 列表（传输顺序每条观测随机化）；
- context；
- relation outcome（成立/不成立）。

Evaluator view：
- template family 与 template ID；
- 角色对应的属性值；
- context 的有效条件；
- 每条观测的 role-to-object 真值；
- 负例违反的约束位置。

学习器入口必须只接收 `Episode.learner_view()` 的序列化结果，不应持有 Episode 对象或调用 `audit_view()`。

## 3. 负例结构

每个潜在正例至少生成：
- context-negative：参与者不变，只改变上下文状态；
- role-near-miss：只替换一个角色对象，使其不满足该角色的属性约束。

两类负例独立标注，评测真值中记录违反因素。learner view 不暴露负例来源。

## 4. 可识别性边界

当前可识别性报告只检查必要条件：
- 每个模板至少两个正例；
- 每个角色至少两个对象支持；
- 角色属性值互异；
- 正例参与对象的角色属性均可观测。

这不是对所有可能假设空间的唯一性证明。正式实验前仍须加入：
- 角色标签置换不变的评分；
- 观测顺序置换测试；
- 属性 key/value 置换不变性；
- 多个潜在程序等价时的 abstain 评测；
- hard-negative 和 oracle upper bound。

## 5. 当前覆盖范围与明确不支持项

已覆盖：
- 同一 episode 内可复用的二元/三元角色约束模板；
- 属性—角色—关系成立之间的生成依赖；
- context-gated validity；
- 随机参与者顺序；
- context-negative 与 role-near-miss；
- learner/evaluator 独立序列化视图；
- identity-disjoint split manifest 与数据哈希。

尚未覆盖：
- 跨 episode 的稳定世界语义；
- 属性组合、关系模板、关系组合的严格 OOD split；
- 多关系组合/共享中间对象的复合真值；
- 属性缺失、关系漏观测、噪声翻转的独立实验臂；
- 自动验证所有目标结构在 learner view 下唯一可识别；
- E09、图、超图、查表、近邻和随机基线；
- 任何性能结论。

因此 v2 只能作为“可控属性条件关系模板”的最小数据生成器。不能称为开放式关系发现 benchmark。

## 6. 运行门槛

在开始训练任何关系学习器之前，必须先通过：
1. generator invariants；
2. participant-order invariance；
3. attribute-symbol permutation invariance；
4. split leakage attacks；
5. evaluator/learner information-flow tests；
6. oracle identifiability check；
7. baseline sanity checks。

若 oracle 无法从 learner view 恢复目标结构，相关 episode 必须标记为不可识别，不得计入结构准确率。
