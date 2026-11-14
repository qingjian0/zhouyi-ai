# Zhouyi-AI 研究执行快照（2026-11-12）

> 本文从稳定分支 `main` 的基线 `b8b43926e666d83a9ce09d2e71eb9294b2d86c97` 独立建立。它记录本次核查到的分支证据，不代表这些研究分支已经集成。

## 结论

当前适合继续进行**组件级训练、算法对照和工程恢复验证**；不适合宣称统一认知系统已经完成端到端训练准备，也不应把任何研究分支直接批量合入 `main`。

当前最高优先级不是扩大参数规模，而是打通三个可审计闭环：

1. 关系发现：从候选关系生成、联合评分、结构选择到 OOD 验证。
2. 生命周期持久化：从权威事件日志到有界投影读取、重建和崩溃恢复。
3. 训练评估：从可重复流式数据到严格分组隔离、checkpoint 恢复和独立锁定测试。

## 本次 exact-head 核查

| 分支 / PR | 核查到的 HEAD | 证据 | 当前判断 |
|---|---|---|---|
| #379 E09 → ZPCM crash replay | `423c53a6b90bb71bfe97fbe9d6f08114d4b71057` | 父 HEAD `1301a8c` 的完整 workflow #43250954184 成功；当前 HEAD 新增 fail-closed replay 断言，workflow #43253292643 / #43253306110 运行中 | 提交前/后崩溃、进程重启恢复和继续学习已有成功证据；新增失败状态 replay 拒绝测试待 exact-head CI |
| #377 E12-A6 lazy projection reader | `0d30ce8d09ebeaedc5b3052b7e89182fa0359708` | Actions run #43250964080，full-validation 成功 | 分页读取和索引查询计划验证通过；仍不是 `PersistentLifecycleLedger._restore()` 的完整替代 |
| #378 CPG-EI beam fail-closed | `c3149603c011cb5e00c13c353331b641982a391f` | Actions run #43245395515 成功 | pruning / budget exhaustion 显式 abstain；不证明 beam 召回率提升 |
| #380 exact product vs beam | `33b14625baaf6657956ba2808c9b2b1a457700bd` | full workflow #43250729401 与后续搜索状态指标测试 #43251196951 均成功 | 对抗性三阶信号下 exact product 找回全局最优；窄 beam 剪枝并 abstain；这是特定合成场景，不是普遍召回率结论 |
| #363 bounded joint motifs | `176490351d4a3c5c62745f87834ce9ef48cde2b3` | 早期 exact-head 多种子及 matched-compute 结果记录在 PR | 有限 20 motif 合成空间的实验；不属于开放式关系发现 |
| #365 N0.10 out-of-core runner | `974d7ae9f3b3178e3bae5b5e708c3adc6d108925` | PR 记录的 15 项 focused tests 成功 | 文件流式训练组件已存在；独立锁定测试进程仍是调用方约定 |
| #374 N0.10 million-row signal/RSS | `84db642adf438a0b7976681a027916421492468b` | 两次百万行/双 epoch RSS 实验成功 | 约 5.08–5.29 MiB 增量峰值 RSS；只证明特定合成数据路径的内存行为和训练损失变化 |

## 算法判断

### CPG-EI：必须把结构恢复和预测泛化分开

当前证据显示：

- 原始稀疏 teacher：10 seeds 的 exact 6-edge recovery 为 0/10，平均 support recall 约 0.583。
- GF(2) parity teacher：贪心残差增长 exact 12-edge recovery 为 0/3，平均 support recall 约 0.306。
- 已知正确 support 的 oracle 可达到 100% bit / exact-state accuracy，说明当前特征基存在表达能力，但不能证明候选发现算法能找到该结构。
- 有限 joint-motif 搜索在一个 matched-compute seed 上恢复了完整 support，但 validation bit accuracy 约 0.5365，低于 greedy 的约 0.8229。

因此，不能把更高 support precision、完整 support recovery 或更低 expansion count 单独当作更好的学习器。后续每个方法必须同时报告：

- support precision / recall / FDR / exact support recovery；
- locked-test accuracy、coverage、abstention；
- candidate proposal 数、优化 passes、实际扩展数和 wall time；
- 多 seed 均值、方差和置信区间；
- label shuffle、feature permutation、pairwise-only 与 matched-compute baselines。

下一步优先研究**条件候选提议与有界联合子集搜索**，并与 greedy、joint motif、exact small-instance oracle 做相同训练预算对照。禁止用 locked-test 反馈调候选或超参数。

### E12-A6 / ZPCM：惰性读接口不等于有界恢复

当前 lazy reader 可分页读取投影 DTO，但 writer / compatibility adapter 仍保留完整事件重放和全量 Ledger 物化路径。必须把下列路径分开验收：

1. 正常启动：只读取投影和 checkpoint，不重建完整 Python 对象图。
2. 投影损坏或过期：按 keyset page、严格字节预算重建。
3. append：权威事件、投影和 high-water checkpoint 原子更新。
4. 崩溃：在 append 前、append 后、投影更新期间、checkpoint 发布前注入故障。
5. 恢复：fresh process、数据库重开、重复请求、重复回放均有确定性结果。

必须分别测量 OS peak RSS、Python allocation、SQLite cache/page、恢复延迟、事件数量和 payload bytes。不得用逻辑缓存计数替代 RSS。

### N0.10：百万行内存结果不是百万行学习能力证明

已有两百万条记录（每个 split 一百万）的合成数据流式 benchmark，双 epoch 两次运行的增量 peak RSS 约 5.08–5.29 MiB，耗时约 393 秒，训练损失从约 1.3863 降至约 0.7705。

这是有价值的工程证据，但数据重复了非常简单的二元模式。它不能证明复杂规则学习质量随数据量提升，也不能证明开放域泛化。下一步需要多 rule-family、多对象身份、source-group-disjoint 的数据，并独立封存 locked-test。

## 统一架构边界

- ZNCA：认知状态与生命周期语义。
- TRLW：有界工作集，不承担全历史存储。
- SROK：局部稀疏、类型化关系组合。
- CSG-GCR：全局候选协调、预算和停止。
- Yixiang / XSL：版本化易象算子与类象映射；结构相似不能自动升级为因果。
- RSDN：时间、事件和干预驱动的关系状态更新。
- E09 / E12-A6：证据、授权、生命周期和 receipt。
- ZPCM：唯一权威追加事件源；投影可重建。
- N0.10：流式训练、checkpoint 和独立评估。
- LLM / Transformer：可插拔教师或对照基线，不计入结构内核成绩。

不得再创建第二套事件账本、候选生命周期状态机、全局搜索调度器或预算策略。

## 下一阶段执行顺序

1. **已完成：** #380 exact-head full workflow 通过；保留对抗性三阶 fixture 的 recall / expansion trade-off 结果。
2. 下一步为 CPG-EI 增加 conditional proposal / bounded subset search 的独立研究分支；先固定实验协议，再跑多 seed。
3. 将 #377 的 reader 接入正常启动路径，确保 ordinary restore 不调用全量 materialization。
4. 为 E12-A6/ZPCM 增加 fresh-process crash/rebuild RSS benchmark。
5. 将 N0.10 source-group provenance、checkpoint fingerprints、独立 locked evaluator 合并到一个明确集成祖先。
6. 只有依赖链清晰、exact-head CI 全绿、跨模块 E2E / crash / OOD / RSS 验收通过后，才创建面向稳定主线的集成 PR。

## 发布门禁

所有研究 PR 默认 Draft。任何合并提议必须附带：父依赖状态、exact HEAD SHA、CI run URL、测试范围、数据集 digest、seed、资源曲线、未验证边界和回滚方案。稳定分支 `main` 在本轮保持不变。

---

快照性质：审计与执行计划，不是产品能力声明，不是训练就绪认证。
