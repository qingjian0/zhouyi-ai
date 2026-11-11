# YJ-10.3：部分置换群学习与对称性破缺

日期：2026-11-12  
分支：`research/yj10-3-partial-permutation-groups-2026-11-12`  
基础：YJ-10.2 head `2cbe912a53b12b21eef7fb5bf55223d86b4a6930`

## 研究问题

`ORDERED` / `UNORDERED` 只覆盖平凡群与全对称群，不能表达部分对称关系。YJ-10.3 将关系槽位允许的变换表示为 (S_n) 的子群。例如三元关系只允许交换槽位 0、1，槽位 2 固定，对应一个二阶子群。

## 方法

1. 输入显式的置换兼容/冲突证据，每条记录带 evidence ID。
2. 按不同 evidence ID 聚合；达到 `min_support` 且没有冲突的置换才可成为生成元。
3. 对生成元及其逆元计算群闭包；超出 `max_group_elements` 时 fail-closed。
4. 分别报告直接得到证据支持的生成元、群闭包元素和仅由代数闭包推出的元素。闭包元素不能伪装成直接观测证据。
5. 对连续阶段的群进行集合比较：严格子群是 `SYMMETRY_BROKEN`，严格超群是 `SYMMETRY_EXPANDED`，互不包含则为 `RECONFIGURED`。

## 重要边界

- 当前实现是有限槽位置换群的证据约束原型，不是端到端学习模型。
- 输入兼容/冲突记录必须由独立的外部结构证据或实验产生；本模块不自行判断语义对称。
- 群闭包保证代数一致性，但不增加经验支持度。
- `SYMMETRY_BROKEN` 表示观测到的候选置换群缩小，不自动证明现实因果机制改变。
- 该模块尚未从 YJ-10.2 精确超图自动同构映射中自动提取槽位生成元；本轮先建立可独立测试的群学习与演化契约。
- 不宣称语义角色、因果角色、训练能力或 OOD 泛化提升。

## 测试

覆盖单换位生成二阶子群、两个换位生成 (S_3)、冲突证据阻止生成元、distinct evidence 计数、闭包预算 fail-closed、非法置换拒绝，以及 (S_3	o C_2) 对称性破缺、群扩张和重配置。

## 下一步

1. 将精确 automorphism oracle 的映射输出接入槽位置换诱导映射。
2. 构造相同底层结构在新增上下文关系前后的成对 benchmark。
3. 加入 pairwise projection、typed-position、higher-order WL 和 exact-oracle 匹配预算比较。
4. 建立 WL-hard hypergraph families，报告群恢复 exact match、generator precision/recall、orbit partition accuracy、时间和搜索状态数。
