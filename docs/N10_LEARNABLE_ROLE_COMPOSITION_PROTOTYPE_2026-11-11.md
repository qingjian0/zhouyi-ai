# N0.10：可学习角色绑定与高阶结构评分器（首个训练原型）

日期：2026-11-11  
状态：CPU 友好、纯 Python 原型；需以 CI 结果为准。  
基线：N0.8 SROK-0。研究协议：N0.9（PR #180）。

## 1. 本轮实现范围

N0.10 将 N0.9 中最小可学习切面落实为可执行代码：

- **角色条件检索**：每个角色有独立线性权重，对节点特征排序。
- **确定性约束**：节点类型、必要标签、唯一 ID 和角色数由普通代码校验，不受训练权重覆盖。
- **结构联合评分**：评分包含角色 unary、角色 pairwise、角色 triple 的逐维乘积项。
- **结构级训练**：在有限角色候选笛卡尔积上使用 softmax 交叉熵；监督目标是完整有序角色绑定，而非独立节点标签。
- **拒答**：最佳与次佳结构分差不足时返回 LOW_SCORE_MARGIN。
- **预算**：推理显式限制每角色 Top-K 和最大扩展数，并报告预算是否耗尽。
- **证据**：证据 ID 仅随候选结构聚合，不作为模型指令或训练标签。
- **Checkpoint**：支持确定性 JSON 导出/恢复，包含角色 schema、feature dimension、权重、训练步数和 SHA-256 内容摘要；加载时校验字段、版本、权重形状、数值有限性和摘要。摘要用于完整性/版本指纹，不是签名或来源真实性证明。

实现文件：prototype/n09_learnable_srok.py  
测试文件：tests/test_n09_learnable_srok.py

## 2. 为什么不是简单 MLP 节点分类器

单节点分类无法表达“节点 A、B、C 各自看起来都合理，但只有特定角色绑定联合起来才成立”。本模型把完整绑定映射为结构特征：

Phi(x_1,...,x_R) = [x_i ; x_i ⊙ x_j ; x_i ⊙ x_j ⊙ x_k]

其中包含所有角色的一元项、所有角色对的二阶交互，以及所有角色三元组的三阶交互。权重由结构级 softmax 目标学习。

这仍是受限的显式交互模型，不等于通用高阶推理。逐维乘积无法表达任意张量交互；后续可比较低秩张量、因子化交互和小型 MLP，但必须匹配参数量与计算预算。

## 3. 与 SROK-0 的边界

SROK-0 提供透明的确定性组合基线；N0.10 独立验证可学习排序和结构评分。当前原型尚未直接替换 SROK-0 内部候选池构造，也没有宣称两者已完成端到端集成。N0.10 仍显式执行类型/标签硬过滤、唯一成员约束和预算限制。

当前候选枚举采用有界笛卡尔积，若预算截断则结果不是全局最优保证。训练阶段若目标结构不在候选组合内会直接报错，不静默制造标签。

## 4. 测试覆盖

- 多角色结构级训练损失下降；
- 留出合成样本上的角色绑定 exact match；
- 类型与必要标签硬过滤；
- 三阶特征块确实参与评分；
- 低分差拒答；
- 预算耗尽报告；
- 重复 ID 与非法训练输入拒绝。

这些测试是软件正确性与受控合成任务检查，不构成真实语义理解、易象有效性或架构优越性的证据。

## 5. 易象/类象接入原则

本原型不把卦象 ID 直接塞进 embedding，也不把类象映射设成硬规则。后续应把取象、互、错、综、应、时、位、变等候选关系定义为带类型签名、前后置条件、证据和反例的算子先验；先作为可学习偏置或候选生成建议，再通过随机置换先验、通用关系先验和错误映射对照验证增量价值。

## 6. 下一轮实验门槛

1. 固定随机种子、多种子训练/测试；
2. 对照 SROK-0 additive、节点 unary-only、pairwise-only、third-order；
3. 规则族与对象不相交 OOD；
4. 保留二元投影但破坏三元绑定的归因干预；
5. 报告 Recall@K、结构 exact match、拒答风险覆盖率、扩展数、p50/p95、峰值 RSS；
6. 对同等参数量与搜索预算进行公平比较；
7. 如果三阶模型优势在高阶扰动后仍存在，优先排查低阶捷径。

## 7. 相关研究参照

- Kong et al., From Reasoning Traces to Reusable Modules, ICML 2026：离散技能与路由模块的组合选择，提示应把“学会局部操作”与“学会如何选取/组合操作”分开评估。
  https://proceedings.mlr.press/v306/kong26c.html
- Qu et al., RLAD: Training LLMs to Discover Abstractions for Solving Reasoning Problems, ICLR 2026：抽象提议与解题过程分离，支持把候选结构探索与最终验证拆开研究。
  https://proceedings.iclr.cc/paper_files/paper/2026/hash/ef7f6a2f18415e0e89edf50def91ecb6-Abstract-Conference.html
- Khalid & Schockaert, Systematic Relational Reasoning With Epistemic Graph Neural Networks, ICLR 2025：多路径关系证据聚合，作为后续对照方向，而非直接替代本原型。
  https://proceedings.iclr.cc/paper_files/paper/2025/hash/6590cb829f5ffef50050f3e5845fbb4c-Abstract-Conference.html

## 8. 诚实状态

该实现是一个小型、可训练的结构打分器原型，不是完整 CPG-EI、不是语言模型、不是训练完成的类象发现模型，也没有证明优于 Transformer/GNN。所有性能和泛化结论等待 CI 与独立基准实验。


## 9. Checkpoint 与模型版本

- 导出：`model.checkpoint_json()`
- 恢复：`LearnableSROK.from_checkpoint_json(raw)`
- JSON 中的 `sha256` 是规范化 payload 的内容摘要；任何字段/权重变化都会导致加载失败。
- 加载会拒绝未知字段、错误 schema 版本、非法角色定义、权重维度不匹配、非有限权重和非法训练步数。
- 该摘要不是数字签名，也不证明 checkpoint 来自可信训练者；需要可信分发时还要增加外部签名与制品来源验证。
