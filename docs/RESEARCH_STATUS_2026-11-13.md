# Zhouyi-AI 研究状态增补（2026-11-13）

> 本文补充并覆盖旧 README / ROADMAP 中仍停留在 M1/M2 初始原型阶段的状态描述。它记录分支级证据，不表示任何 Draft PR 已集成到 main。

## 稳定边界

- 稳定分支：main
- 本次核查的 main 基线：b8b43926e666d83a9ce09d2e71eb9294b2d86c97
- 所有下述研究实现仍位于独立 Draft 分支；不因 CI 成功或 PR 可比较而视为已集成。
- 当前只批准可复现的组件级实验，不批准统一认知系统端到端联合训练。

## CPG-EI 混合算子研究现状

### 数据与基线

- 数据集：zhouyi-cpg-ei-mixed-operators-v1
- 单种子对照：seed 20261114；8 个独立 teacher family；每个 family 256 个 8-bit 状态、8 个输出；总计 2,048 行。
- 每个 family 固定分割：128 train / 64 development / 64 locked。
- 单种子 corpus SHA-256：f56948816847a587c194931588027f97d99a4541644932b81f2df26e7b381c15
- 五种子扩展：seed 20261114–20261118；40 个独立 teacher family、10,240 行；每个种子独立记录 corpus digest。

### 已验证的单种子对照

在同一 corpus digest 上：

| 方法 | Locked bit accuracy | Locked exact-state accuracy | 备注 |
|---|---:|---:|---|
| 有限符号搜索 | 99.90% | 不作为主要指标 | 3,864 个候选描述；3,388 个唯一 truth function；476 个结构别名 |
| 完整多项式 logistic，120 epochs | 85.52% | 20.90% | 255 个非空 Boolean monomial + bias；每个 family 独立拟合 |
| 完整多项式 logistic，development early stopping | 86.13% | 23.63% | max 600 epochs、patience 30；5/8 families 提前停止 |

符号搜索在全部 64 个输出上达到 98.44% full-truth-table exact recovery、85.94% operator recovery、84.38% exact-rule recovery。符号搜索使用声明的有限规则语法，按 train error 选择并用 development tie-break；locked labels 不参与选择。它不是可训练神经模型。

Early-stopping 结果的平均 best epoch 为 420.875，平均执行 439.625 epochs。其训练 bit / exact-state accuracy 为 95.03% / 67.38%，development 为 85.89% / 21.88%，locked 为 86.13% / 23.63%。训练与留出 exact-state 差距仍明显，不能据此认定模型已泛化。

### 五种子复现

五个独立 corpus 上，完整多项式模型的 locked 指标为：

- Bit accuracy：均值 86.15%，跨种子样本标准差 0.63 个百分点。
- Exact-state accuracy：均值 24.92%，跨种子样本标准差 2.97 个百分点。
- Unary-only 控制：79.98% bit / 13.75% exact-state。
- Train-derived majority 控制：77.72% bit / 11.37% exact-state。

这是五个合成种子的描述性离散程度，不是外部数据置信保证，也不是跨 family zero-shot 评估。每个 family 都使用自己的 train partition 进行拟合。

### 分支依赖关系

当前混合算子研究栈：

1. #409 / #410：早期候选与 typed operator 基础。
2. #411：102,400-row corpus，基于 #409 / #410。
3. #413：有限符号 mixed-operator discovery，基于 #411。
4. #417：trainable polynomial baseline，基于 #413。
5. #418：五种子 replication，作为 #417 的独立子分支。
6. #419 → #420 → #421 → #422：匹配对照 → sample-efficiency → development early stopping → compute-accounted symbolic-support hybrid。
7. #423（scalar pre-encoded cache）、#426（NumPy hybrid backend）、#427（full-basis vectorized experiment）、#428（compositional OOG）是 #422 的独立后续分支；#429 依赖 #426。它们是并行验证线，不应未经统一 optimizer API 审计而分别合并。

#418 与 #419 是 #417 的兄弟分支，不是彼此的父子依赖。#422 的 base 是 #421；#423、#426、#427、#428 的 base 均为 #422；#429 的 base 为 #426；不得跳过父链独立合并。#422 当前 exact head 为 251ecbe2f0cee36ce877fbbb4135df9a1cc0f67c，较 #421 base head 49a4147200a3fae52c0d06898f036623536e1fed 前进 4 commits。#427 当前 exact head 为 f142d669fff95fcce86b904c5721d616cd4b6769，较 #422 前进 11 commits。#428 当前 exact head 为 dde911b56414c8075a9e664125d391f8e35cf0c9。

### 当前新增研究：符号支持约束 hybrid

PR #422 增加三路同数据对照：

- 有限符号搜索；
- 完整 Boolean monomial basis 的 logistic learner；
- 使用 train-only 最小误差符号候选的 support scope 构建 per-output monomial basis，再进行 logistic fitting 的 hybrid。

Hybrid 的 support 选择只读取 train labels；development 仅用于 checkpoint 选择；locked 仅用于最终报告。该实现补充候选评估数、truth-table state evaluations、feature count、gradient feature contributions、wall time、Python allocation peak 和 process-wide RSS high-water。

PR #422 exact-head workflow [#43349730473](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730473) 已成功，focused leakage/accounting tests、三路 benchmark 和 artifact upload 全部通过。结果：
- Exhaustive symbolic：11.54 s，99.90% locked bit accuracy，98.44% full-truth-table exact recovery。
- Full polynomial + development early stopping：1,467.69 s，86.13% locked bit / 23.63% exact-state accuracy。
- Symbolic-support hybrid：711.25 s，90.04% locked bit / 41.21% exact-state accuracy。
- Hybrid 使用 1,752 个非 bias features（64 个 output heads 合计），full model 对应 16,320 个 feature slots；hybrid 相对 full model 约 2.06× wall-time speedup。
- Python traced allocation peaks 分别为 1.89 MB / 1.63 MB / 3.54 MB；34.58 MB 是所有方法共用进程的 peak RSS，不能当作每个方法独立 RSS。

### 精确 CI 证据

以下 workflow 均关联 PR #422 exact head 的验证运行：

- [Discovery baseline #43349730491](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730491)：success。
- [Trainable baseline #43349730532](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730532)：success。
- [Matched comparison #43349730471](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730471)：success。
- [Sample efficiency #43349730472](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730472)：success。
- [Early stopping #43349730489](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730489)：success。
- [Compute-accounted hybrid #43349730473](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730473)：success，benchmark 与 artifact 均完成。

这些是同一 PR head 上的工作流证据，不代表任何父 PR 已合并。

### 后续性能工程：向量化优化器（PR #427，前一 head 已通过）

PR #427 在 #422 之上保留原 scalar optimizer 作为 reference/fallback，并新增 NumPy float64 向量化路径：每个 fit 仅编码一次 train/development feature matrix，再使用矩阵乘法计算 logits 与 batch gradients。BCE、mean-gradient、non-bias L2、学习率、development checkpoint/patience 规则保持不变。CI 固定 NumPy 2.3.5 和单线程 BLAS 设置。

前一 head `f142d669fff95fcce86b904c5721d616cd4b6769` 的 exact-head workflow [#43365196479](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365196479) 已成功，测试、完整 paired benchmark 和 artifact upload 全部通过。同一 corpus digest `f56948816847a587c194931588027f97d99a4541644932b81f2df26e7b381c15`、8 families / 2,048 rows、128/64/64 split、600 max epochs：
- Scalar reference：296.59 s；locked bit / exact-state accuracy 86.1328% / 23.6328%。
- NumPy vectorized：2.45 s；locked bit / exact-state accuracy 86.1328% / 23.6328%。
- Paired speedup：121.03×；8 个 family 的 best epoch 全部一致；accuracy delta 0；best development loss 最大差值 2.22e-16。
- 该计时排除 corpus generation，且没有开启 tracemalloc；不可与 #422 instrumented compute-accounting wall time 直接比较。

前一 head 的 [hybrid regression #43365196396](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365196396) 和 [early-stopping regression #43365196471](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365196471) 也已成功。

当前 head `7e445c5be6317dcda982dd4cfd93ccbd2e463cb3` 修正了 feature accounting：区分一次性 cached feature-matrix encodings 与每 epoch gradient feature contributions，并补充无 NumPy fallback 及两种后端 accounting tests。当前 exact-head workflows 尚待完成：
- [Vectorized parity/speed #43365872933](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365872933)
- [Hybrid regression #43365872867](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365872867)
- [Early-stopping regression #43365872882](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365872882)

因此，121.03× 是前一 head 的已验证实现结果；当前 head 的 accounting/fallback 修订尚未通过 exact-head CI。PR #427 仍是探索分支，不是独立 merge 候选；应将 full-basis 证据用于决定是否把 #426 的 canonical NumPy optimizer API 扩展到 full-basis learner。
### 组合规则 out-of-grammar 基准（PR #428，exact-head CI 成功）

PR #428 使用 `(x_a AND x_b) XOR (x_c AND x_d)` 作为组合教师规则。当前符号发现器的候选空间只包含单一声明算子，因此测试目标刻意位于单算子 grammar 之外。

- 3 个独立种子：20261114、20261115、20261116；24 teacher families / 1,536 rows。
- 每个 family 6 个 Boolean 输入、4 个输出、64 个状态，32 train / 16 development / 16 locked，状态互斥。
- 同 corpus、同 split 对照有限符号搜索、完整多项式学习器和 symbolic-support hybrid。
- Exact-head workflow [#43365433589](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365433589) 成功；leakage tests、三种子 benchmark 和 artifact upload 全部通过。

| Method | Locked bit accuracy | Locked exact-state accuracy |
|---|---:|---:|
| Finite single-operator symbolic | 68.95% (SD 0.59 pp) | 32.29% (SD 5.92 pp) |
| Full polynomial | 46.68% (SD 3.99 pp) | 14.06% (SD 2.34 pp) |
| Symbolic-support hybrid | 56.84% (SD 1.79 pp) | 11.98% (SD 0.90 pp) |

重要负结果：hybrid 在 bit accuracy 上优于 full polynomial，但低于 symbolic；在 exact-state accuracy 上低于两者。由最小训练误差单算子 scope 构成的特征并集，不能可靠地作为 grammar 外组合规则的支持先验。

解释边界：这是 operator-grammar OOD，不是 held-out-family transfer；每个 family 仍提供自己的监督训练样本。它不证明自然语言、易学、因果或真实世界推理。
### 大规模 family 扩展（PR #431，待验证）

- 目标从 400 扩大到 1,600 个独立教师结构；每个 8-bit family 仍包含 256 个状态。
- 总规模 409,600 行、12,800 条教师规则（相对 400-family v1 为 4×）。
- 保持七种 typed operator、round-robin coverage、teacher digest、family split 与 family 内 state split。
- 当前 head `2220d4577f82b15b0e31e0b9b20c8219da422bd2`；精确工作流 [#43365798036](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365798036) 尚在队列中，1,600-family artifact 尚未宣称生成成功。
- 这是数据规模/结构多样性扩展，不是学习性能或泛化结果。

### ANF 可识别性（PR #425 → #430，待验证）

PR #425 提供完整 truth-table Möbius transform oracle 与 train-only GF(2) 部分观察求解器；PR #430 将其扩展为最大 ANF degree 0..8 的约束基底扫描，64 families / 16,384 rows。对 8 个输入，degree 0..8 的 basis sizes 为 1、9、37、93、163、219、247、255、256。每个 degree 分开报告 basis size、rank、nullity、consistency、uniqueness 和 oracle representability；full-table oracle degree 只用于事后参照，不进入训练方程。

- PR #425 当前 head `10a8c46c38f860b9f50be15aeb8d3c48822b7388`，exact-head 工作流尚未观察到完成结果。
- PR #430 当前 head `3fd244a67300652cd07f90769ffd1707f86741cc`，工作流 [#43365743326](https://github.com/qingjian0/zhouyi-ai/actions/runs/43365743326) queued。
- 这是有限 Boolean ANF 可识别性分析，不是 learned relation discovery 或 cross-family generalization。

### Held-out-family few-shot（PR #432 → #436，待验证）

这条线把原来仅作报告分层的 `family_split` 升级为真实协议边界：meta-train / validation / final-test 教师家族互不重叠；未见家族提供 16/32/64 个标注 support states，query 输入与标签分离。PR #436 在该协议上加入有限符号 grammar few-shot baseline，并与相同 support 的 per-output majority baseline 对照。

- 每个 seed 1,600 families：960 meta-train、320 validation、320 final-test；3 个独立 seeds。
- Validation query 使用 family 内 development states；final-test query 使用 locked states。
- 报告 per-family bit/exact-state、median、worst-family、candidate tie ambiguity、selection digest、corpus digest 和 evaluation wall time。
- PR #432 当前 protocol head `1f0d679aaee55906ee47ca815d3b4ee29e5ed489`；protocol workflow [#43366174958](https://github.com/qingjian0/zhouyi-ai/actions/runs/43366174958) queued。
- PR #436 当前 head `5b10832f117ff2c390ea556eab72cab31e25ce70`；protocol/symbolic workflows [#43366342910](https://github.com/qingjian0/zhouyi-ai/actions/runs/43366342910) / [#43366343052](https://github.com/qingjian0/zhouyi-ai/actions/runs/43366343052) queued。
- 这是带 labeled support 的 few-shot family transfer，不是 zero-shot，也不是 learned meta-learning。Learner/evaluator view 是 API-level guard，不是 process isolation。
- 旧 PR #435 因重复和依赖分支陈旧已关闭；#436 是当前干净 follow-up。

### 主动查询（PR #434，待验证）

主动查询基于同一有限假设 grammar，以 train-only 的候选预测分歧选择下一条 oracle query，并与同 query pool、同 budget 的 seeded random sampling 配对。Development 只用于 tie-break，locked 只用于报告，teacher manifest 仅事后评分。当前 head `ac69dce0490bb9abdcd3497e00dc6e57c27b7ada`，工作流 [#43366194964](https://github.com/qingjian0/zhouyi-ai/actions/runs/43366194964) queued。该研究是有限假设主动搜索，不是开放世界发现或跨家族 zero-shot。

### 其他实验与策略提案

- PR #424 adaptive learning-rate scheduler 是负/中性结果：在相同数据上与 early-stopping 选择相同 checkpoint 和相同质量，但平均训练 epoch 更多；不应推广为默认优化策略。
- PR #433 是文档型易象优先研究纲领提案，建议将类象、阴阳四象八卦六十四卦、五行动态关系、时位势变和象数理联合建模设为 P0。它尚未合并或被正式采用；由于会改变项目战略优先级，保留为独立提案审查，不自动改写项目目标。

## E09 / E12-A6 / N0.10 状态边界

E09、E12-A6/ZPCM 与 N0.10 仍由独立研究分支承载。现有架构收敛文档已经定义唯一模块所有权、事件账本边界、跨进程安全和恢复验收门槛；但分段实现、分支 CI 与端到端集成是不同层级的证据。

- ZPCM 仍是唯一权威追加事件源；投影可重建，不能成为第二权威。
- E12-A6 的 lazy reader、SQLite projection、crash replay 和 scratch-state 研究不能自动证明普通启动已完全避免全历史 Python 对象物化。
- E09 的 receipt / identity / learner binding 测试不能替代真实 OS 进程边界和权限隔离验证。
- N0.10 的 streaming / checkpoint 组件实验不能自动证明完整 runner 已经 out-of-core，也不能替代 source-group-disjoint OOD 与 resume equivalence。

在重新核查各分支 exact HEAD、依赖祖先、CI 和跨模块 E2E 前，不把这些工作线标为集成完成。

## 当前工程判断

- 允许：组件级受控训练、有限合成基准、独立种子复现、负对照、matched-compute 与资源审计。
- 不允许：把有限候选搜索结果解释为开放式关系发现；把 family strata 解释为 zero-shot transfer；把合成准确率解释为 Yi-Xue 理解、因果发现或自然语言推理。
- 不允许：以当前 CPG-EI 结果宣称优于 Transformer。
- 不允许：把 Draft PR 数量、代码行数或单次 CI 通过当作统一架构成熟度。
- 统一端到端训练仍未获准；main 保持稳定，不进行批量合并。

## 下一阶段优先顺序

1. 完成 #427 exact-head scalar/vectorized parity 和 full wall-time benchmark；若数值不一致，先修复再考虑启用。
2. 对 #422 hybrid 进行独立种子复现，并增加组合规则/严格未见 teacher-family 评估；不得使用 locked 结果调参。
3. 将 E12-A6 普通启动、bounded restore、checkpoint anchor 与 crash fallback 分开验收。
4. 将 E09 trusted identity / receipt / replay 与真实进程隔离分开验收。
5. 将 N0.10 data provenance、checkpoint fingerprints、streaming runner 和 locked evaluator 收敛到一个明确集成祖先。
6. 所有父依赖、exact-head CI、接口审计和 E2E/crash/OOD/RSS 门禁通过后，才提出独立可回滚的稳定主线切片。


## 架构文档与分支优先级审计

- PR #265 的主架构 v2 文档位于分支 `architecture/cpg-ei-master-convergence-v2-2026-11-12`，HEAD `86541fe33ebe93d145bc4f39f6b36821850dfc51`，基于 PR #253 的逐文件运行时映射分支 HEAD `564ac728620002f13db2d8b69975c2779a149e9f`。#265 相对父分支仅前进 2 commits，但相对 main 为 251 commits ahead / 9 commits behind；它是旧的长依赖栈，不能直接作为当前稳定集成祖先。
- PR #358 的全项目收敛基线以 main `b8b43926e666d83a9ce09d2e71eb9294b2d86c97` 为父基线；当前 Draft 分支 HEAD `c7b1eb15348a1d15ae21042bfa539f4aec9068c0`，相对 main 为 47 ahead / 0 behind，包含 README、ROADMAP 和架构/状态文档。此前 head `8cf3061432be3dc58c1fee90af093321bfa46aa9` 的文档测试 workflow [#43351080279](https://github.com/qingjian0/zhouyi-ai/actions/runs/43351080279) 已成功；当前 exact-head 文档 workflow [#43366925878](https://github.com/qingjian0/zhouyi-ai/actions/runs/43366925878) queued，尚未通过。
- PR #381 的 execution snapshot HEAD `1126a644e26458610ae8d867056551cfe5e819c0` 有 workflow #43253222365 success；它是 2026-11-12 的分支证据快照，不是第二套架构所有权规范。
- #265 的主架构 v2 与 #358 的项目收敛基线都包含模块责任、运行闭环和 KV-independent 分层，存在文档权威重叠。应选定一个唯一架构决策入口；另一个保留为逐文件证据/历史审计并链接过去，避免两个“master”同时有效。



### Sample-efficiency curve（same corpus digest）

在相同 8-family corpus 上，将每个 family 的 train support 分别限制为 16 / 32 / 64 / 128 states；development 与 locked partition 保持不变：

| Train states / family | Polynomial locked bit accuracy | Polynomial locked exact-state accuracy | Symbolic full-truth-table exact rate |
|---:|---:|---:|---:|
| 16 | 82.86% | 19.34% | 89.06% |
| 32 | 84.06% | 19.14% | 92.19% |
| 64 | 85.79% | 22.46% | 95.31% |
| 128 | 85.52% | 20.90% | 98.44% |

Symbolic 列是选中有限规则对完整 Boolean truth table 的精确恢复比例；不是与 polynomial locked accuracy 同一种指标。Polynomial 列是留出 locked states 的预测表现。该曲线只测每个 family 的 within-family adaptation，不是跨 family zero-shot transfer。
