# YJ-10：自主高阶角色归纳

日期：2026-11-11  
分支：`research/yj10-autonomous-higher-order-role-induction-2026-11-11`  
基础：YJ-09 PR #219

## 目标

从 YJ-09 的类型化 n 元超边出发，归纳结构角色与超边 Schema，而不是继续依赖调用方提供的 `RoleBinding.role` 名称。角色归纳必须尊重关系对称性：证据不能区分的参与者保留在同一结构等价类中。

## v0.1 方法

### 高阶 WL 细化

每轮为实体收集其参与的超边邻域描述，包含：

- relation type；
- hyperedge arity；
- relation symmetry policy；
- 有序关系中的自身参数位置；
- 其他参与者的当前颜色；无序关系对邻居颜色排序。

颜色只由实体类型、上一轮颜色和高阶邻域签名确定。实体 ID、edge ID、evidence ID、输入角色名称和上下文值不进入结构颜色。采用有界迭代，并在分区稳定时提前停止。

### 对称性契约

- `ORDERED`：参数位置有意义，位置差异可以形成不同结构角色。
- `UNORDERED`：参与者排列不改变签名，无法区分的对象进入同一等价类。
- 每种 relation type 必须显式声明策略；缺失或重复策略 fail-closed。
- 本版本不从样本顺序猜测对称性，也不把 E13 的 `UNKNOWN` 自动解释为有序或无序。

### Schema 归纳

对每条超边，将推断出的参与者角色及实体类型组成 pattern。ORDERED pattern 保留位置；UNORDERED pattern 规范排序。跨 observation 按 distinct evidence ID 计数支持度，并受 hypothesis budget 限制。

## 重要边界

1. 归纳的是结构角色，不是自然语言语义角色或因果角色。
2. WL 颜色相同表示在当前有限轮次和特征下不可区分，不证明完整超图同构。
3. 结构等价类不是语义同一；新增关系、干预或上下文可进一步拆分。
4. 当前策略由数据集/实验者明确提供，不自主发现关系对称性。自动对称性发现需要 automorphism-aware hypothesis testing，作为后续任务。
5. 目前未实现概率角色分布、角色 split/merge 学习、跨域对齐或主动干预选择。
6. Schema support 统计 observation evidence，不是独立样本概率或置信度。
7. 本原型不执行算子，不代表训练完成或现实世界泛化。

## 必须进行的后续评估

- 与 pairwise WL、static hypergraph WL、random/fixed role、typed-position baseline 做匹配预算比较。
- 对参与者置换、实体重命名、输入 role name 重命名、对称节点和高阶 hard negatives 做不变性测试。
- 报告 role equivalence accuracy、schema precision/recall/F1、候选召回率、held-out relation coverage。
- 在成员组合 OOD、关系类型 OOD、上下文漂移和噪声超边下做至少五个独立种子实验。
- 只有在 held-out 与干预证据支持时，才讨论语义角色、因果关系或跨域迁移。
