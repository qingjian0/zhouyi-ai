# Zhouyi-AI 开发路线图（2026-11-18）

> 本路线图以 `dev` 当前集成状态为准；`main` 是稳定分支，未经明确发布决策不修改。状态只表示代码/实验资产的实际落地程度，不把设计文档、工具存在或历史 CI 结果等同于验收通过。

## 项目定位

研究组合并行生成与易象启发式认知架构（CPG-EI），重点探索动态关系组合、证据约束的结构学习、多路径推演与可检验的易象表征。项目尚不能宣称已实现通用认知系统、通用语言模型或 Transformer 替代品。

## 当前集成基线

- 集成分支：`dev`；稳定分支：`main`。
- 本路线图更新基线：`a846daf3bd0ace0fa3fd4227add38ca2d45901ae`。
- `dev` 相对 `main`：ahead 24、behind 0（本次核对）。
- 基线 CI：Run [44299206115](https://github.com/qingjian0/zhouyi-ai/actions/runs/44299206115)，7/7 jobs 成功；该结果只证明该 SHA 的相应自动化检查通过。
- 当前研发重点：E12-A6 生命周期状态投影；M1/M2 有界恢复和实测；N0.10 规模/分组隔离验证；CPG-EI 神经/非有限语法跨族学习；易象真实 Gold 数据验证。

## 能力状态

| 工作流 | 已落地 | 尚未通过的关键验收 |
|---|---|---|
| ZPCM / E12-A6 | 追加式事件日志、SQLite 持久化、事件摘要校验、授权 receipt/nonce 唯一索引、候选历史索引、授权历史 keyset 分页、幂等和重放验证 | `PersistentLifecycleLedger` 启动仍全量 replay 到 Python `LifecycleLedger`；缺少规范化 current-state projection、事务内 append+projection+checkpoint、损坏重建和大规模 RSS 验收 |
| M1 数据摄取 | UTF-8 分块读取、Manifest、Chunk Digest、SQLite 持久化、恢复和有界 chunk 读取 | 跨 Chunk tokenizer 一致性、整篇 reference 对照、大文本吞吐与 RSS exact-head 报告 |
| M2 Observation | Observation DTO、EvidenceRef、Lazy Store、SQLite 索引、Keyset Paging、来源校验与重启恢复 | 大规模 RSS 实测、Gold 标注、语义提取质量、abstention 与独立标注评估 |
| N0.10 / SROK | SROK 组合内核、LearnableSROK、JSONL 流式/out-of-core runner、SQLite 元数据、checkpoint 恢复、locked-test 评估与 RSS 工具 | 百万行真实运行、峰值 RSS、恢复一致性、group-disjoint split、与 materialized oracle 数值一致性；工具存在不等于规模验收完成 |
| CPG-EI | 有限候选语法、符号搜索、经验贝叶斯 few-shot、混合算子发现、组合 OOD、motif/optimizer 诊断、扩展合成语料 | 神经或非有限语法 meta-learner、强基线预算公平性、更深组合 OOD、跨分布验证；现有结果限于声明的合成任务 |
| 易象 / Yixiang | 卦爻编码、状态转移、五行/类象关系工具、结构保持映射与多组合成 OOD 原型 | 真实古籍 Gold 语料、独立标注/仲裁、页码来源追踪、消融、因果/语义层级验证和真实任务评估 |
| 集成编排 | Orchestrator、实验协议、测试与工作流自动化 | 证据摄取→表征→候选发现→学习→评估→生命周期持久化的完整 clean-checkout E2E 闭环 |

## 优先级与交付门禁

### P0 — 工程持久化与可恢复性

1. 将 `memory_events` 保持为唯一权威事件源；SQLite current-state projection 只能是可重建投影。
2. 建立独立的 candidate、evidence、action、candidate-evidence、action-evidence 索引；action_id 与 candidate_id 必须分列。
3. 投影元数据记录 schema、high-water sequence、事件链摘要和 generation。
4. 启动优先验证投影 checkpoint；有效时不全量物化 Python ledger。缺失/损坏时按有界 keyset page 从权威事件重建，失败时 fail closed。
5. append、领域状态校验、投影更新和 checkpoint 发布必须具备明确事务/崩溃语义；保留 E09 receipt/nonce、split、状态迁移、幂等和 digest 约束。
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

截至本路线图基线，项目仍处于多条研究原型并行推进阶段，尚未达到 P0–P4 全部验收条件。尤其 E12-A6 仍有全量 Python replay 路径；N0.10 百万级训练、M1/M2 大规模资源曲线、CPG-EI 神经跨族学习和易象真实 Gold 验证均未完成。任何项目完成度表述必须保留这些边界。
