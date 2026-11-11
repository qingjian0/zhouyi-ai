# YJ-10.2：精确超图自动同构基准

日期：2026-11-11  
分支：`research/yj10-autonomous-higher-order-role-induction-2026-11-11`

## 目标

为 YJ-10 的高阶 WL 角色等价类建立独立的精确结构基准。有限轮 WL 颜色相同并不保证两个实体位于同一个超图自动同构轨道；WL 颜色不同也可能是实现或策略定义造成的过度区分。必须把这两类错误分开测量。

## 精确契约

在明确的 `RelationSymmetry` 策略下，枚举保持实体类型的实体双射。一个映射只有在映射后的超边多重集与原超边多重集完全相同时才是自动同构。

保留：
- entity type；
- relation type 和元数；
- ORDERED 关系的参数位置；
- UNORDERED 关系的参与者多重集；
- edge context、attributes、valid_from、valid_until；
- 超边重复出现的多重性。

忽略：
- entity ID；
- edge ID；
- evidence ID；
- caller-provided role names；
- observation provenance。

因此此 oracle 定义的是结构自动同构，不是语义角色、因果角色或现实对象同一性。它只在明确的关系顺序契约下有效。

## 输出与误差

精确 oracle 输出 automorphism group 的实体轨道。与高阶 WL 分区比较所有实体对：

- true positive：精确同轨道，WL 也合并；
- false merge：精确不同轨道，WL 却合并；
- false split：精确同轨道，WL 却拆分；
- true negative：精确不同轨道，WL 也拆分。

同时报告 pairwise precision/recall。无正例时采用空预测 precision/recall=1 的约定，报告中必须结合 TP/FP/FN 数量解释，避免单独解读比例。

## 复杂度与安全边界

该算法是指数/阶乘级精确 oracle，不是生产推理路径。候选双射数量为各实体类型分组阶乘的乘积。超过 `max_candidate_bijections` 时直接 fail-closed，不采样后冒充精确结果。

建议只用于小规模基准图（例如 3–9 个实体，具体上限由类型分布和预算决定），更大图需使用专门的 partition refinement / individualization-refinement automorphism solver。

## 测试

覆盖无序三元超边全对称、有序三元边位置区分、有向三环、有向路径、实体/角色名重命名、实体类型约束、边属性保持、缺失策略和搜索预算。

## 下一步实验

1. 生成已知 automorphism group 的超图族：完全对称、循环群、二面体群、局部对称、对称性破缺。
2. 对照 YJ-10 WL、pairwise projection WL、typed-position baseline。
3. 统计 pairwise precision/recall、轨道分区 exact match、运行时间、候选状态数。
4. 构造 WL-hard negatives：1-WL/有限轮 WL 无法区分但精确自动同构不同的超图对。
5. 只有这些基准完成后，才讨论部分置换群学习与主动辨识是否有效。
