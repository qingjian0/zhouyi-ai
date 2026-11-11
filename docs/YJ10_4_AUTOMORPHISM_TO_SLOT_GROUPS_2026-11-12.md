# YJ-10.4：精确自动同构到部分槽位置换群

日期：2026-11-12  
分支：`research/yj10-4-automorphism-to-slot-groups-2026-11-12`  
基础：YJ-10.3 PR #233

## 目标

将 YJ-10.2 的精确实体自动同构 witness 接入 YJ-10.3 的有限置换群学习器，避免由调用者手工提供置换兼容/冲突候选。

## 方法

1. 精确 oracle 可选返回完整 automorphism mappings；默认关闭，避免既有调用者承担额外内存成本。
2. 对每条目标超边，计算全局自动同构群在该超边参与实体集合上的 setwise stabilizer。
3. 仅对显式声明为 `UNORDERED` 的候选关系计算 stabilizer；`ORDERED` 关系作为固定位置的外部结构约束，不作为待发现目标。将 stabilizer 对参与实体集合的作用映射到该超边的 slot index，得到槽位置换子群。
4. 同一快照中 schema 相同的多条候选关系实例取群交集，采用保守的共同对称性。
5. 多个 observation 之间仅在 relation type、arity、slot frame、entity-type frame、context、attributes、validity 和 symmetry policy 完全一致时聚合。
6. 保留每个 observation 的精确槽位置换群，并按输入顺序比较相邻 observation，显式报告对称性破缺、扩张或重配置。\n7. 对跨 observation 的共同结构，再将每个候选置换的兼容/冲突记录交给 YJ-10.3 统计支持和计算共同子群。

## 关键数学性质

若 (G) 是超图的 automorphism group，(e) 是目标超边，则将 setwise stabilizer (G_e) 限制到参与实体集合，得到一个群作用；在参与实体唯一时，该作用诱导到 (S_n) 的群同态，其像是 (S_n) 的子群。因此输出不是任意兼容置换的集合，而是由精确结构对称诱导的置换群。

## 坐标系与保守边界

- `RoleBinding.role` 只作为跨 observation 对齐的显式 slot coordinate frame；不被当作自动发现的语义角色，也不参与 exact automorphism 结构判断。
- frame 不一致的 observations 分开输出，不强行合并。
- 同一快照中相同 schema 的多个实例取 stabilizer 交集；不把不同实例的坐标误对齐。
- 重复实体参与同一超边时，slot action 不唯一，fail-closed。
- Exact automorphism 仍受 factorial candidate budget 限制；完整 witness 输出只在显式启用时分配内存。
- 结构 automorphism 只证明显式超图契约下的结构对称，不证明语义或因果对称。
- evidence IDs 是记录标识，不自动证明统计独立；多个快照必须有独立来源才能解释为独立样本。

## 测试设计

覆盖 mapping opt-in、逐 observation 群保留与 transition 输出、无外部约束的 (S_3)、外部上下文约束出的 (C_2)、不对称上下文降为 identity、跨快照 (C_2	o 1) 对称性破缺、重复参与实体拒绝、slot frame 不一致隔离。

## 下一步

1. 将 slot-group transitions 接入 YJ-08/YJ-09 的动态结构演化与滞回。
2. 构造 WL-hard 超图族，对比 WL 颜色类、exact entity orbits、slot stabilizer groups。
3. 加入 exact group recovery、generator precision/recall、候选搜索预算和跨 seed 方差报告。
