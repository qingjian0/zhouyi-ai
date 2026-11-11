# YJ-10.1：证据驱动的关系对称性辨识

日期：2026-11-11  
所属：YJ-10 自主高阶角色归纳

## 问题

YJ-10 v0.1 需要调用方为每种 relation type 指定 ORDERED 或 UNORDERED。这个接口适合已知契约，但不是自主辨识。本增量研究如何从关系参与者的外部结构上下文中提出可检验的槽位置换假设。

## 方法：外部上下文置换检验

对目标关系类型 R：

1. 从每个 observation 中移除所有 R 超边，防止目标关系自己的位置编码循环地证明自身对称性。
2. 在剩余 typed hypergraph 上运行有界高阶 WL，得到参与者的外部结构颜色。
3. 对元数 n 的目标关系枚举 S_n 中所有位置置换（受 arity 与 permutation budget 限制）。
4. 若一个置换只交换外部结构颜色相同的参与者，则该 observation 对该置换提供结构兼容证据；否则提供冲突证据。
5. 按 distinct observation evidence IDs 聚合。存在任何冲突时标记 CONTRADICTED；无冲突且达到 min_support 标记 STRUCTURALLY_COMPATIBLE；否则保留 UNRESOLVED。
6. 仅当成对换位有充分兼容证据时，合并槽位等价类。

## 解释边界

- STRUCTURALLY_COMPATIBLE 仅表示置换没有被当前外部结构证据区分；不是关系在语义上可交换的证明。
- WL 颜色相同是必要但不充分的结构同构证据；WL 可能无法区分非同构结构。
- 一次观察不足以达到默认的 min_support=2。
- 不将无外部上下文自动升级为语义对称；结果的 semantic_status 固定为 NOT_ESTABLISHED。
- 本版本发现的是与观测结构兼容的置换，不是从数据中恢复关系真实语义的完整算法。
- 不使用目标关系的角色名称、实体 ID 或自身位置编码来生成外部颜色。
- 元数阶乘超过预算时 fail-closed，不截断枚举后伪造完整置换群。

## 测试

覆盖无上下文同类型参与者的保守等价、外部关系导致单个槽位可区分、独立 evidence support、角色名/实体命名不变性、缺失上下文策略、目标关系信息隔离、重复证据拒绝和置换预算拒绝。

## 下一步

- 加入带已知 automorphism group 的合成数据集。
- 与精确小图 automorphism、hypergraph canonical labeling 和 WL baseline 对照。
- 评估置换群 precision/recall、slot equivalence accuracy、ambiguous-case calibration。
- 扩展到部分对称关系（如仅允许子群置换），再研究上下文条件下的对称性破缺。
