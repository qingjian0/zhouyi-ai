# Zhouyi-AI 开发路线图（2026-11-19）

> 本路线图以 `dev` 当前集成状态为准；`main` 是稳定分支，未经明确发布决策不修改。状态只表示代码/实验资产的实际落地程度，不把设计文档、工具存在或历史 CI 结果等同于验收通过。

## 项目定位

研究组合并行生成与易象启发式认知架构（CPG-EI），重点探索动态关系组合、证据约束的结构学习、多路径推演与可检验的易象表征。项目尚不能宣称已实现通用认知系统、通用语言模型或 Transformer 替代品。

## 当前集成基线

- 集成分支：`dev`；稳定分支：`main`。
- 最近一次代码集成基线：`9452d6f41384ca5483531a53c09bdbe230c90c5b`；其后的 `f4f5317` 与本次 `c728c27` 均为路线图状态同步提交。代码基线相对 `main` ahead 60、behind 0；`main` 未修改。
- 本轮已合并 PR #537（CPG-EI one-pass evaluation）和 PR #539（E12-A6 hard-process-termination recovery test）。#537 精确 head 的 22 项检查全部成功；#539 精确 head 的 unit-tests 与 detect-research 成功。
- #539 的强杀测试验证 SQLite 权威事件提交后、scratch-state mutation 前进程退出，再由新进程恢复；它不等同于断电、磁盘故障或完整 checkpoint 验收。
- `9452d6f` 的整仓 `tests` 工作流 #44390349072 已完成：`unit-tests` 与 `detect-research` 均 success，研究评估矩阵按路径条件 skipped；该结果验证的是代码提交 `9452d6f`，不是后续仅修改路线图的 `f4f5317`。
- 当前研发重点：E12-A6 安全快速恢复协议；N0.10 百万行真实训练与 RSS；CPG-EI 神经/非有限语法跨族学习；易象真实 Gold 数据校勘与独立标注。


## 能力状态

| 工作流 | 已落地 | 尚未通过的关键验收 |
|---|---|---|
| ZPCM / E12-A6 | 追加式权威事件日志、SQLite 持久化、事件摘要校验、授权 receipt/nonce 唯一索引、候选历史索引和授权历史 keyset 分页；候选/证据/动作当前状态已有 SQLite 投影表，事件插入触发器在同一 SQLite 事务内更新投影与 high-water/count 元数据；提供投影按需读取、keyset 遍历、digest 校验、原子重建；`PersistentLifecycleLedger` 已将候选/证据/动作/动作 ID 放入临时 SQLite scratch state，普通写入不再 deepcopy 全账本，`ledger`/`snapshot()` 是显式全量物化边界 | 启动仍需 O(N) 重放全部权威事件并进行语义校验，当前投影尚未用于跳过重放；checkpoint 目前只有 schema/high-water/count，缺少事件链 digest/generation 和可信快速恢复协议；scratch state 是进程级临时库；写入压力、磁盘故障、进程强杀、并发 adapter、清理失败和当前 exact-head RSS 尚待验收 |
| M1 数据摄取 | UTF-8 分块读取、Manifest、Chunk Digest、SQLite 持久化、恢复和有界 chunk 读取 | 跨 Chunk tokenizer 一致性、整篇 reference 对照、大文本吞吐与 RSS exact-head 报告 |
| M2 Observation | Observation DTO、EvidenceRef、Lazy Store、SQLite 索引、Keyset Paging、来源校验与重启恢复 | 大规模 RSS 实测、Gold 标注、语义提取质量、abstention 与独立标注评估 |
| N0.10 / SROK | SROK 组合内核、LearnableSROK、JSONL 流式/out-of-core runner、SQLite 元数据、checkpoint 恢复、locked-test 评估与 RSS 工具 | 百万行真实运行、峰值 RSS、恢复一致性、group-disjoint split、与 materialized oracle 数值一致性；工具存在不等于规模验收完成 |
| CPG-EI | 有限候选语法、符号搜索、经验贝叶斯 few-shot、混合算子发现、组合 OOD、motif/optimizer 诊断、扩展合成语料 | 神经或非有限语法 meta-learner、强基线预算公平性、更深组合 OOD、跨分布验证；现有结果限于声明的合成任务 |
| 易象 / Yixiang | 卦爻编码、状态转移、五行/类象关系工具、结构保持映射与多组合成 OOD 原型 | 真实古籍 Gold 语料、独立标注/仲裁、页码来源追踪、消融、因果/语义层级验证和真实任务评估 |
| 集成编排 | Orchestrator、实验协议、测试与工作流自动化 | 证据摄取→表征→候选发现→学习→评估→生命周期持久化的完整 clean-checkout E2E 闭环 |

## 优先级与交付门禁

### P0 — 工程持久化与可恢复性

1. 将 `memory_events` 保持为唯一权威事件源；SQLite current-state projection 只能是可重建投影。
2. candidate、evidence、action 当前状态投影已落地；补齐候选-证据、动作-证据关系的高效查询索引（按实际查询负载选择规范化表/索引），action_id 与 candidate_id 必须保持独立字段。
3. 当前投影元数据已记录 schema、lifecycle high-water sequence 和 event count；下一步增加可验证的事件链 digest、projection generation 和版本迁移门禁。
4. 当前启动仍对权威事件做 O(N) 语义重放到临时 SQLite scratch state。下一步设计经过 digest/generation 验证的持久 checkpoint；只有 checkpoint 完整匹配权威事件链时才允许快速恢复，缺失/损坏时按有界 keyset page 重建并保留语义校验，失败时 fail closed。
5. append 与 candidate/evidence/action 投影已通过 SQLite 触发器置于同一事务；scratch state 写入失败会从权威事件流重建。仍需完成 checkpoint 发布、磁盘故障和崩溃注入的完整事务语义；保留 E09 receipt/nonce、split、状态迁移、幂等和 digest 约束。
6. 保留 `ledger`/`snapshot()` 作为显式 O(total state) 兼容导出接口，普通启动和按需读取不得隐式调用。
7. 验收：投影删除/损坏重建、事件篡改拒绝、并发写入、崩溃注入、snapshot 与 replay oracle 一致；在 1K/10K/50K/100K/500K 事件规模报告 RSS、Python allocation、SQLite cache/page、恢复耗时。

**完成定义：** 不以“存在 SQLite 表”或单元测试通过作为完成；必须有 exact-head 测试、重建/崩溃测试和 OS RSS 结果。

### P1 — 数据管线与训练规模

1. M1：定义 tokenizer 跨块状态协议，使用 whole-document reference 做边界一致性验证。
2. M2：补齐 Gold Annotation、来源证据、语义单元和 abstention 的独立评估。
3. N0.10：增加版本化数据 Manifest、source/world/rule-family group-disjoint split 和数据摘要校验。
4. 将 locked-test 标签隔离在训练进程之外；训练、验证和最终评估使用明确的数据边界。
5. 在固定预算下比较 unary、pairwise、高阶 SROK、参数匹配 MLP、compute 匹配图模型、exact oracle 与不同 beam 宽度。
6. 报告多种子均值/方差、coverage、abstention、预算耗尽、参数量、耗时和峰值 RSS。

**完成定义：** 规模测试必须在目标规模真实执行；不把 benchmark 工具或小样本 smoke test 作为百万行通过证明。

### P2 — CPG-EI 学习与泛化

1. 将候选生成、候选评价、结构选择和跨域泛化分开度量。
2. 从固定候选枚举推进到预算约束的候选提议机制，并保留规范化、去重、可证伪和证据来源。
3. 实现神经/非有限语法 meta-learner；与符号经验贝叶斯、MLP 等强基线在同数据、同预算下比较。
4. 扩大组合深度和规则族 OOD；固定 train/dev/locked-test 隔离，至少多种子复现。
5. 对 truth-function、operator、exact-rule 分层报告，处理结构等价别名。

**完成定义：** 不以有限语法符号搜索的高准确率宣称神经跨族学习或开放域关系发现已完成。

### P3 — 易象真实数据验证

1. 建立许可清晰、版本固定、可追溯到书名/版本/页码/段落的古籍 Gold 语料。
2. 至少双人独立标注并仲裁，记录歧义和异文。
3. 分别检验结构同构、统计不变性、语义类比和因果等价，不跨层级推断。
4. 对无先验、随机编码、可学习编码、结构编码、传统关系先验进行预算匹配消融。
5. 发布错误案例、负结果和复现协议。

**完成定义：** 编码正确不等于解释正确；合成规则有效不等于真实古籍映射有效。

### P4 — 系统集成与发布

- 建立 clean checkout 的端到端路径：数据/证据摄取 → 类型化表征 → 候选生成 → 学习/筛选 → locked evaluation → 生命周期持久化 → 可追溯报告。
- 固定 API/schema 版本、运行配置、数据摘要、随机种子和代码 SHA。
- 验证可恢复、权限边界、资源预算、可观测性和故障关闭。
- 先完成 dev 验收，再进行发布审查；不得仅因 CI 通过就自动合并到 main。

## CI 与 PR 收敛原则

- `dev` 是唯一集成目标；禁止为同一功能继续制造平行长期分支。
- CI 以变更路径触发必要专项检查；全量测试保留为集成门禁，重型研究实验只在相关代码/数据变化时运行。
- 同一分支旧运行可取消；不得通过删减必要断言或跳过失败测试来“优化 CI”。
- 对开放 PR 先按 diff 与 dev 基线分类：已覆盖、被替代、仍有独立价值、依赖未满足、纯实验/过时。未完成逐项核对前不批量 merge/close/delete。
- 历史 PR 的 predecessor-head 成功不能代替当前 exact-head 验证。

## 当前未完成声明

截至 2026-11-19，项目仍处于多条研究原型并行推进阶段，尚未达到 P0–P4 全部验收条件。E12-A6 已增加真实子进程强制退出恢复测试，但启动仍为 O(N) 全事件重放，且尚无可验证的持久化状态 checkpoint；N0.10 百万行基准脚本已具备，但百万行真实训练结果尚未取得；CPG-EI 经验贝叶斯结果仍是有限语法符号方法，神经跨族学习未完成；易象案例库当前 26 条案例均为 unreviewed，不能计作 Gold。M1/M2 大规模资源曲线也未全部验收。任何项目完成度表述必须保留这些边界。
