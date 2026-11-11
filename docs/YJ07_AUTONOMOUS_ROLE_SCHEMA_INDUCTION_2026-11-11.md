# YJ-07：自主关系角色与 Schema 归纳（结构基线）

日期：2026-11-11  
分支：`research/yj07-autonomous-role-schema-induction-2026-11-11`  
基础：YJ-06 PR #210 → YJ-05 PR #207

## 1. 研究问题

YJ-04 从带有人工 role 标签的关系状态中归纳关系变化。即使机制发现是自动的，表示空间仍由数据生产者预先指定。YJ-07 把“角色标签由谁定义”变成可研究的问题：从有向、带类型的关系邻域中提出结构角色，并进一步归纳关系 Schema。

## 2. v0.1 方法

### 角色归纳

- 忽略输入中的 entity ID 和人工 Node.role 名称。
- 初始颜色只由 entity_type 决定。
- 执行有界的有向、带边标签 Weisfeiler–Lehman 邻域细化。
- incoming/outgoing 分开编码，保留关系方向。
- 角色 ID 由规范化结构签名确定，因此同构重命名不改变结果。
- 当前不把全局 context 纳入角色身份，避免瞬时上下文污染结构角色。

### Schema 归纳

每条关系形成候选结构：

`(relation_type, source_role, target_role, source_type, target_type)`

跨 observation 聚合 distinct evidence IDs，按最小支持数和候选预算筛选。关系方向不被折叠成无向边。

### 留出稳定性

在独立 held-out observations 上重新归纳 schema key，报告 precision、recall、F1 和 relation coverage。它衡量结构重复/稳定性，不是因果有效性。

## 3. 必须明确的限制

- Weisfeiler–Lehman 颜色细化不能区分所有非同构图；它是结构指纹，不是完整图同构算法。
- 结构角色相同不代表语义角色相同；对称节点可能被合并。
- 当前只支持二元有向关系；未实现超边、动态角色分裂/合并学习或不确定角色分布。
- 不从观察关联推出因果角色。
- 不使用语言模型或向量相似度；未来可作为候选生成器，但必须保留结构验证。
- 当前角色只基于 entity type 与局部关系拓扑；时间、阶段、阴阳互补、五行多关系等需作为显式可消融特征，不得偷偷混入。
- schema stability 不是跨域迁移成功；需要未来的干预与负迁移评估。

## 4. 反过拟合设计

1. alpha-renaming：更换实体 ID 和人工 role 名称，结果必须不变。
2. direction ablation：反转边应改变相应结构角色/schema。
3. context ablation：更换非结构 context 不应改变 v0.1 角色。
4. held-out graph：独立重建 schema 并报告结构稳定性。
5. budget reporting：搜索候选截断必须显式报告。

## 5. 验收范围

`tests/test_yijing_role_schema_induction.py` 包含 12 个测试，覆盖重命名不变性、方向敏感性、对称节点合并、schema 支持、留出稳定性、预算和证据 ID 唯一性。

本 PR 仅是可解释、确定性结构归纳基线；测试未运行前不声称通过。没有训练、性能或因果泛化结论。
