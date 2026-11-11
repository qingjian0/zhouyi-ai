# YJ-10.4：精确自动同构到槽位置换群的桥接

## 目标

将 YJ-10.2 有界精确自动同构 oracle 输出的实体双射，转换为关系实例上的槽位置换证据，并交给 YJ-10.3 群学习器处理。

## 实现契约

- 精确 oracle 增加 `automorphism_mappings`，每个映射按实体 ID 对排序。
- 桥接器仅处理显式声明为 `UNORDERED` 的关系；当前 `ORDERED` 契约本身已固定槽位顺序。
- 对每条源超边应用实体映射，寻找同 relation type、participant set、context、attributes 和 validity bounds 匹配的目标超边。
- 目标槽位索引由映射后的实体在目标边中的位置确定。
- 重复 participant 会产生歧义，当前直接跳过，不猜测槽位对应。
- 每条映射/源边/目标边组合产生带来源标识的证据记录。

## 边界

- 这是结构映射，不是语义对称性发现。
- 证据来自同一个有限结构的 automorphism group action，不应误当作独立现实样本；YJ-10.3 的 distinct evidence ID 只是计数接口。
- 当前 oracle 的 UNORDERED 先验已经允许全槽位置换，因此本桥接不能凭空发现更细粒度的部分对称性。部分对称性需要更丰富的关系契约/候选结构与外部上下文约束。
- 当前仅导出映射和槽位置换证据，不自动声称学到了现实关系语义。

## 后续

将 exact oracle 扩展为候选 relation-slot action 的约束搜索，而不是先验地将关系设为全 UNORDERED；再构建部分对称性破缺 benchmark。
