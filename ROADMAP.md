# 开发路线图

## 当前状态快照（2026-11-13）

稳定主线保持为 main；下表反映研究分支中的组件证据，不代表代码已集成。

| 阶段 / 研究线 | 目标 | 当前证据 | 状态 |
|---|---|---|---|
| M0 | 理论与文献调研 | 研究总纲、相关工作、风险与证伪条件已建立 | 持续维护 |
| M1 | 数学理论定稿 | CPG-EI v0.3 草案已写入；模块所有权和运行闭环见架构收敛文档 | 草案，待继续证伪 |
| M2 | 基础组合原型 | E01/E02 有可运行基线与测试；仍不是统一认知模型 | 组件级完成，整体未完成 |
| CPG-EI | 混合算子关系学习 | 400-family / 102,400-row 语料；有限符号、完整多项式、五种子、sample-efficiency、early-stopping；symbolic-support hybrid 正在 exact-head 验证 | 活跃研究，Draft |
| E09 / E12-A6 / ZPCM | 证据、授权、生命周期和持久化 | 存在分段 reader、projection、receipt、crash/replay 研究；普通启动、写入与恢复的端到端边界仍需验证 | 分段实现，未集成 |
| N0.10 | 流式训练、checkpoint 与隔离评估 | 有 trainer、streaming、checkpoint 组件实验；完整 runner 的 out-of-core、source-group-disjoint OOD 和 resume equivalence 仍需统一验收 | 组件研究，未完成 |
| M3 | 易象计算实验 | 编码工具和单测存在；模型级、跨域语义效用尚未证明 | 部分完成 |
| M4 | 自组织学习 | CREATE/MERGE/SPLIT/PRUNE 需要独立识别、反例和预算门控证据 | 未完成 |
| M5 | 对照实验 | 有限规则、符号、图/超图和训练基线正在分线验证；尚无统一 matched-compute 的完整模型比较 | 进行中 |
| M6 | 扩展与评估 | 多模态、设备部署、真实数据与生产验收未完成 | 未开始 |

## 训练准备度

**当前判定：允许组件级受控训练；不批准统一认知系统端到端联合训练。**

以下不能互相替代：

- 有限候选空间中的结构恢复，不等于开放式关系发现。
- 锁定样本上的合成预测，不等于真实分布泛化。
- 分支级单测 / CI 成功，不等于跨模块集成、进程隔离或生产可用。
- 流式数据接口，不自动证明完整训练 runner 的内存有界。
- checkpoint 可保存，不自动证明跨代码、数据、配置和优化器变更的精确恢复。

## CPG-EI 当前验证顺序

1. 完成 PR #422 的 compute-accounted symbolic-support hybrid：同 corpus、同 split、候选评估数、feature count、wall time、allocation peak 和 RSS scope。
2. 先看 development 和 locked 指标，再决定是否进行独立多种子复现；locked 结果不得用于调参。
3. 若 hybrid 的收益不足以抵消候选搜索成本，保留其为负结果，不以扩张模型规模掩盖问题。
4. 将结构恢复、operator recovery、truth-function recovery、bit accuracy 和 exact-state accuracy 分开报告。
5. 只有完成同数据、多种子、负对照和 compute-accounting 后，才讨论与其他架构的 matched-compute 对照。

详细数据、corpus digest、exact-head CI 和依赖链见 [2026-11-13 研究状态增补](docs/RESEARCH_STATUS_2026-11-13.md)。

## 近期优先顺序

1. 完成 #422 的 exact-head hybrid benchmark，并复核 artifact 与 commit SHA。
2. 收敛 CPG-EI 依赖栈：#409/#410 → #411 → #413 → #417；#418 是 #417 的独立子分支；#419 → #420 → #421 → #422 是另一条连续链。
3. E12-A6：分别验收普通启动、bounded restore、checkpoint anchor、semantic replay 和 crash fallback。
4. E09：分别验收 trusted identity、receipt/nonce、lineage 和真实 OS 进程边界。
5. N0.10：收敛数据 provenance、group-disjoint split、checkpoint fingerprints、streaming runner 和 locked evaluator。
6. 只有父依赖、exact-head CI、接口审计、E2E/crash/OOD/RSS 门禁全部通过后，才建立从 main 派生的单一集成祖先。

## 发布门禁

- 所有研究 PR 默认 Draft；不因 mergeable 或某个旧 SHA 的 CI 成功自动转为 Ready。
- 每项结果绑定代码 SHA、数据集 digest、seed、配置、测试范围和 CI run。
- train/dev/locked 严格隔离；locked 只在选择结束后评估。
- 任何架构结论都必须同时报告基线、资源预算、失败案例和未验证边界。
- main 不接受批量堆叠分支；只合并独立、可回滚、已验证的能力切片。
