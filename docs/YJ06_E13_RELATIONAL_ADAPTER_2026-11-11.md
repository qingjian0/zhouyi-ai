# YJ-06：YJ-04 ↔ E13 关系图严格适配器

日期：2026-11-11  
分支：`research/yj06-e13-lossless-relational-adapter-2026-11-11`  
基于：YJ-05 PR #207

## 1. 目的

YJ-04 的 `RelationalState` 是轻量的二元有向关系状态；E13 的 `RelationalGraph` 是带实体、关系 schema、元数、角色语义、证据状态和 provenance 的共享契约。两者不能直接互换。

YJ-06 提供一个严格的可逆映射子集：能无损映射则转换；遇到表达能力不匹配时明确拒绝，不静默丢失信息。

## 2. 映射规则

- YJ-04 `Node(entity_id, entity_type, role)` → E13 `Entity`，角色写入保留命名空间 `yj_role`。
- YJ-04 二元有向 `Relation(source,target,type,attributes)` → E13 `RelationSchema` + `RelationInstance`。
- relation schema 使用 `ORDERED_NAMED`、角色槽 `source/target`、`ASYMMETRIC`。
- relation attributes 通过 `yj_attr:<key>` 命名空间映射到 E13 relation context。
- YJ-04 全局 context 由 `E13Envelope.state_context` 单独保存，避免重复伪装成每条边的属性。
- E13 evidence status 固定为 UNKNOWN，因为 YJ-04 单条关系本身没有等价的 evidence status 字段。

## 3. Fail-closed 条件

以下情况拒绝转换：
- 同一 relation_type 出现多个不同的有序端点类型签名；
- E13 entity 缺少或包含额外的非 YJ role 属性，无法无损还原；
- schema 不是有序、命名、非对称二元关系；
- relation context 出现保留命名空间之外的字段；
- adapter 版本不匹配。

## 4. 不承诺的语义

- 这是数据结构映射，不证明两个研究模块的推理语义等价。
- E13 provenance/evidence lifecycle 不会凭空从 YJ-04 Relation 推导出来。
- 跨域迁移仍需显式 mapping validation 和 held-out intervention evidence。
- 当前不支持 E13 任意元数超边、无序关系、概率转移或多实例角色到 YJ-04 的无损映射。

## 5. 验收

`tests/test_yijing_e13_adapter.py` 覆盖：
- 正向/反向 round-trip；
- 无关系图的全局上下文保留；
- relation type schema 歧义拒绝；
- role metadata 丢失拒绝；
- 非 YJ entity metadata 拒绝；
- 非二元/无序 schema 拒绝；
- relation context namespace；
- adapter version。

只有 round-trip 和拒绝边界都通过，才可将其作为 E13 bridge adapter 的基础。它不是 E13 runtime 的全面集成。
