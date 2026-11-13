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

#418 与 #419 是 #417 的兄弟分支，不是彼此的父子依赖。#422 的 base 是 #421；不得跳过父链独立合并。#422 当前 exact head 为 251ecbe2f0cee36ce877fbbb4135df9a1cc0f67c，较 #421 base head 49a4147200a3fae52c0d06898f036623536e1fed 前进 4 commits。

### 当前新增研究：符号支持约束 hybrid

PR #422 增加三路同数据对照：

- 有限符号搜索；
- 完整 Boolean monomial basis 的 logistic learner；
- 使用 train-only 最小误差符号候选的 support scope 构建 per-output monomial basis，再进行 logistic fitting 的 hybrid。

Hybrid 的 support 选择只读取 train labels；development 仅用于 checkpoint 选择；locked 仅用于最终报告。该实现补充候选评估数、truth-table state evaluations、feature count、gradient feature contributions、wall time、Python allocation peak 和 process-wide RSS high-water。

PR #422 exact-head focused leakage/accounting tests 已通过；compute benchmark 与 artifact 尚待该 exact head 的 workflow 完成。不得在 artifact 生成前宣称 hybrid 有质量或效率提升。

### 精确 CI 证据

以下 workflow 均关联 PR #422 exact head 的验证运行：

- [Discovery baseline #43349730491](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730491)：success。
- [Trainable baseline #43349730532](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730532)：success。
- [Matched comparison #43349730471](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730471)：success。
- [Sample efficiency #43349730472](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730472)：success。
- [Early stopping #43349730489](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730489)：success。
- [Compute-accounted hybrid #43349730473](https://github.com/qingjian0/zhouyi-ai/actions/runs/43349730473)：focused tests passed；benchmark step仍在运行，artifact尚未发布。

这些是同一 PR head 上的工作流证据，不代表任何父 PR 已合并。

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

1. 完成 #422 exact-head compute-accounted artifact，核查质量、候选评估、特征数、wall time 与内存。
2. 若 hybrid 结果稳定，再在独立种子上复现；不得使用 locked 结果调参。
3. 将 E12-A6 普通启动、bounded restore、checkpoint anchor 与 crash fallback 分开验收。
4. 将 E09 trusted identity / receipt / replay 与真实进程隔离分开验收。
5. 将 N0.10 data provenance、checkpoint fingerprints、streaming runner 和 locked evaluator 收敛到一个明确集成祖先。
6. 所有父依赖、exact-head CI、接口审计和 E2E/crash/OOD/RSS 门禁通过后，才提出独立可回滚的稳定主线切片。
