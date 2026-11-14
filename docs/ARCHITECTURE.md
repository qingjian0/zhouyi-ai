# Zhouyi-AI 架构入口

本文件是兼容旧链接的入口。统一架构、模块契约、集成状态和训练验收以以下文档为准：

- [统一认知架构 v1](MASTER_ARCHITECTURE_V1_2026-11-11.md)
- [模块契约 v1](MODULE_CONTRACTS_V1_2026-11-11.md)
- [集成登记册 v1](INTEGRATION_REGISTRY_V1_2026-11-11.md)
- [训练与评估路线 v1](TRAINING_EVALUATION_V1_2026-11-11.md)
- [架构决策记录 v1](ARCHITECTURE_DECISIONS_V1_2026-11-11.md)

## 一句话架构

**非 Transformer 原生结构认知系统：以 ZNCA 组织认知状态，以 TRLW 表示类型化关系工作空间，以 SROK 做稀疏非相邻组合，以 CSG-GCR 做全局协调，以 ZPCM 管持久记忆，以 E09/E12-A6 管证据和生命周期，以 Yixiang/XSL 提供可证伪的易象/类象算子。**

语言模型是可插拔的解析/表达/蒸馏接口，不是认知账本或唯一推理核心。

## 核心计算闭环

`Observe → Ground → Retrieve → Propose → Compose → Infer → Commit → Reveal → Revise → Validate → Persist → Express/Act`

## 关键约束

1. 连续潜在表示与离散结构共存。
2. 组合搜索有界、稀疏并报告截断。
3. 证据、置信度、真值和不确定性分离。
4. 每种持久状态只有一个权威所有者。
5. 传统易象映射是候选先验，必须通过随机/学习先验对照和反例检验。
6. 模块成熟度以代码、测试、实验和资源数据分级。
7. 不以百万级可检索记忆冒充百万 Token 原生上下文。

详细定义见统一架构文档。
