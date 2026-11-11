# Zhouyi-AI 统一路线图

本路线图与 [统一认知架构 v1](docs/MASTER_ARCHITECTURE_V1_2026-11-11.md) 配套。研究分支状态见 [集成登记册](docs/INTEGRATION_REGISTRY_V1_2026-11-11.md)。

| 阶段 | 目标 | 主要交付 | 退出门槛 |
|---|---|---|---|
| P0 | 统一架构与权威所有权 | 架构、DTO、模块登记册、ADR | 不再有重复账本/状态机/调度器定义 |
| P1 | 可运行认知闭环 | E09/E12-A6/E12-A20 适配、ZPCM 最小持久化、SROK、CSG-GCR | 端到端预测提交—证据揭示—修订—持久化测试通过 |
| P2 | 可学习结构认知 | 角色绑定、高阶评分、RSDN 状态更新 | 独立 OOD、消融、预算匹配基线 |
| P3 | 易象/类象算子学习 | Yixiang、XSL、E10/E13 | 关系保持、反例拒绝、随机先验消融 |
| P4 | 记忆与自主调度 | ZPCM/DCMF、CSL、MCRL、Hyper-Speed | 增量更新、恢复、预算/安全门控 |
| P5 | 非 Transformer 后端比较 | SSM/RWKV/xLSTM/图超图/EBM 等 | 统一任务、参数/FLOPs/延迟/RAM 对照 |
| P6 | 语言与多模态接口 | 解析、表达、工具、多模态 grounding | 分开报告内核、解析器、解码器贡献 |
| P7 | 移动端部署 | 磁盘优先记忆、有限工作集、量化和调度 | 目标设备长时压力测试与恢复验证 |

## 当前执行状态（2026-11-11）

- 主路线：非 Transformer 原生认知；Transformer 保留为可选语言接口和对照基线。
- P0 架构规范已合入 E09 集成分支，main 保持不变。
- P1 已集成 SROK-0 确定性组合内核与 N0.10 可学习评分器；候选池截断已作为独立不完整状态报告。
- SROK-0、N0.10 可学习评分器、候选池截断报告、SROK→E12-A6 生命周期投影、SROK→E09 prequential loop 已进入 E09 集成分支；相关完整 CI 均通过。
- 当前已打通可信单进程参考闭环：SROK 预测 → E09 durable commit → SUPPORT reveal → batch refit → 版本事件持久化；LOCKED_TEST 不进入学习更新。
- P1 仍未完成：ZPCM/工作集的认知记忆投影、CSG-GCR 全局协调接入、进程级 evaluator/learner 隔离、崩溃恢复与事务 outbox 尚未完成。
- N0.10 当前训练数据有 unary 捷径，不能宣称三阶/高阶能力已验证；先完成 pairwise-preserving 高阶必要性基准。
- PR #202 已合入本 E09 集成分支：增加 digest-verified observation payload vault、SROK/E09 learner checkpoint、可信单进程 episode resume；这补齐了单进程崩溃恢复切片，但不等于 evaluator/learner 进程隔离或事务 outbox 已完成。
- ZPCM 已有 E09 生命周期投影与通用检索标签脱敏；内部 learner snapshot / ledger checkpoint 不进入通用记忆包。尚需验证重放一致性、投影重建、事务 outbox 与移动设备资源。
- P1 当前剩余硬门槛：CSG-GCR 全局协调接入；evaluator/learner 独立进程与认证 IPC；原子提交/投递 outbox；故障注入和跨进程恢复。
- P2 当前科学门槛：N0.10 现有 unary 任务捷径仍未被排除。E02 parity probe 证明特定三变量 parity 任务对线性 unary/pairwise 假设有表示必要性，但不是学习收敛或普遍高阶优势证明；仍需 pairwise-preserving candidate-set benchmark 与匹配预算 MLP/Set/Graph 对照。
- YJ-01/YJ-04 易象算子研究保持独立研究分支；YJ-04 临时 CI PR 不代表正式集成或算子有效性。
- E09 集成分支最新 head `8b0aa2a` 的 Actions run `43001802066` 于 2026-11-11 10:13 UTC 完成，全部步骤成功；PR #149 仍为 Draft 堆叠集成 PR，未进入 main。

- 不立即启动大规模语言模型预训练。下一阶段仍以 P1 为主线。

## 执行纪律

每个阶段独立开分支、独立 CI、独立实验报告。未通过门槛不升级成熟度；失败实验保留，不通过修改指标制造成功。
