# CPG-EI 快速集成审计与下一阶段研发门禁（2026-11-11）

## 0. 本轮结论

本轮检查了 v0.3 PR #121、E12-A6 × E02-D lifecycle runner、E12-A3 compositional induction、E09 prequential adapter、E02 ternary learner 和易象编码器。

当前仓库已有多个可信的研究组件，但它们仍主要是相互独立的实验模块。现阶段不能称为端到端 CPG-EI，也不能称为非自回归通用 AI。最短路径不是继续增加更多独立原型，而是建立一个可重放、可证伪、通道隔离的 MTS-0 实验闭环。

## 1. 本轮代码审计发现

### 1.1 v0.3 store（PR #121）

已实现：
- 单 SQLite 事件账本上的原子有序批量追加；
- 批次幂等、内容冲突检测、整批事务回滚；
- TRAIN/SUPPORT ingest 与观察引用；
- E12-A6 生命周期动作和状态转换；
- 候选结构谱系、修订批次；
- 事件日志重放、事件摘要校验、确定性投影；
- commit 成功但 projection 失败时显式返回 recovery-required。

最新 CI run 42944858299 已完成且 success。此结论只表示当前工作流通过，不表示协议语义缺口已经消除。

仍需修复：
1. 没有 evaluator-only 的独立事件类型/读取通道。现有 evidence_reveal 既服务 learner feedback，也可能承载 Gate/Locked 评估标签。
2. E09 E09SharedProtocolAdapter.reveal() 对任何传入标签都会调用 runner.reveal()，没有 split-role 类型；不可供 Gate-Final 或 Locked-Test 复用。
3. structure_version.support_evidence_ids 目前只检查证据存在，不检查证据 learner_track 与结构轨道一致。
4. evidence_ingest.outcome_ref 仅验证非空字符串，source_provenance 仅验证非空对象；当前并未解析或认证这些引用。协议文档应将它们描述为 caller assertions，直到接入可信 resolver 或内容摘要验证。
5. 当前投影摘要不是原始标签本身；不能错误声称 projection 已直接暴露标签 bytes。真实问题是原始 payload 仍在事件账本中、缺少窄 learner API，且没有 evaluator/learner projection 契约。

### 1.2 E12-A6 × E02-D

当前 runner 对预先声明的 27 条 Z3 affine rules 做 exact symbolic enumeration。其价值是验证：
- 有限假设类中的可识别性；
- TRAIN support → Gate-Final acceptance → Locked-Test challenge 生命周期；
- 延迟反例引发挑战。

它不是开放世界原语发现，也不是训练得到的学习器。当前 runner 的 prediction/label step 数是合成字段，没有持久化真实 prediction-commit/reveal 事件。必须由 v0.3 event store 承担真实因果记录，不能仅凭整数 step 宣称 durable prequential protocol。

### 1.3 E12-A3 composition

当前组合器以 E12-A1 生成的有限类型谓词为叶节点，使用固定布尔算子 AND/OR/XOR/NOT 和有界 arity/depth/node/candidate budget。它证明的是有限 DSL 内的稀疏组合搜索能力，不是开放式结构归纳。

下一阶段应比较：
- 固定布尔 DSL；
- 可学习关系/超边组合；
- 允许跳过中间元素的非连续组合；
- 参数量/搜索预算匹配的 MLP、规则枚举与随机组合基线。

### 1.4 E02 ternary 与易象编码

E02 ternary learner 是固定特征展开上的 pairwise-vs-third-order 逻辑回归诊断；它的三阶特征增加了参数，并没有实现可学习三元关系结构、太玄三分认知或动态超图。现有数据在 train/validation/test 间重复相同九种查询，当前报告明确不支持 rule-family OOD 或符号重映射泛化。

yixiang_encoding.py 是规范一致的 6-bit 卦象索引编码器，声明 1=阳、0=阴、爻位自下而上；它不包含语义预测。不能将六十四卦二进制索引与《太玄经》三分系统混为一种编码。

建议把易象/太玄分成独立可比较的结构先验族：
- B2：阴阳二值状态；
- B4：四象/二阶状态；
- B8/B64：八卦/六十四卦组合索引；
- T3/T27/T729：三值状态及其三进制组合；
- H3：三元关系/超边结构，而非简单 one-hot 编码。

每一种先验都必须与容量、参数量、训练样本数、搜索预算匹配的通用结构基线比较。只有跨符号置换、组合 OOD、噪声和分布漂移中稳定胜出，才可声称它提供了归纳偏置收益。

## 2. 必须分开的证据通道

MTS-0 应严格区分：

1. evidence_ingest：预测前已可见的 TRAIN/SUPPORT。
2. evidence_reveal：预测后明确授权 learner 使用的反馈。
3. evaluation_reveal：Gate/Locked-Test/Post-deploy evaluator-only 标签；不能进入 learner support 或 E09 runner.reveal()。
4. evaluation_attestation：由 evaluator 从 Gate 结果导出的有限结论（例如 candidate pass/fail、评估摘要、对应 digest）；如要反馈给 learner，也只能释放最小必要信息，不能携带隐藏标签。
5. challenge_release（可选、显式授权）：Locked-Test/Post-deploy 发现反例后，由独立 policy 决定是否向 learner 释放一个经过最小化的 challenge。它不是原始 evaluator reveal，也不能回写为原始 TRAIN。

Locked-Test 必须在候选集合及其摘要 durable freeze 后才允许 prediction commit；label reveal 只能匹配该 commit 的 evaluation role、learner track 和 candidate-set digest。

投影：
- evaluator projection：可读全量事件及原始评估标签，只能由可信 evaluator runner 持有；
- learner projection：默认只读 TRAIN/SUPPORT ingest 和明确授权的 learner feedback；排除 evaluator payload、label、摘要、私有 provenance 和 evaluator-only causal refs；
- learner 代码不得直接打开 evaluator SQLite 文件。投影过滤只是 defense-in-depth，不是进程隔离。

## 3. MTS-0 最小端到端闭环

建议只做一个小而完整的实验环境，先用合成 Z3/离散关系任务，之后再扩大：

Observation → Propose → Identify → Compose → Freeze → Predict → Evaluate → Revise/Abstain

每一步都写入同一 durable event ledger，且 learner/evaluator 有不同投影。

最小组件：
- ObservationAdapter：统一结构化观测和 observation ID；
- PrimitiveProposer：至少两个独立家族（typed predicate / relational-hyperedge）；
- ActiveProbeSelector：从候选分歧中选择信息增益高的 probe；
- SparseComposer：非连续组合，带 MDL/复杂度/预算限制；
- CandidateFreezer：持久化候选集和 digest；
- Predictor：commit 前不可访问 evaluator 标签；
- Evaluator：Gate/Locked-Test 独立评分；
- RevisionController：只接收被授权的 learner feedback 或 challenge release；
- EvidenceKernel：唯一事件账本，负责原子性、重放、投影和审计。

## 4. 核心实验矩阵

每项实验使用固定任务生成器、预注册 seed、独立 train/gate/locked split，并报告置信区间和预算：

| 实验 | 比较 | 主要指标 | 证伪条件 |
|---|---|---|---|
| P1 原语提议 | typed predicate vs relational proposer vs random | hidden-rule recall、precision、proposal cost | 多 proposer 不优于最强单 proposer |
| P2 主动观测 | EIG vs random vs fixed schedule | label budget 下的识别率、校准 | EIG 无稳定优势 |
| P3 稀疏组合 | sparse hypergraph vs Boolean DSL vs MLP | composition OOD、MDL、latency | 稀疏结构被简单基线 Pareto 支配 |
| P4 易象先验 | B2/B4/B8/B64/T3/H3 vs capacity-matched generic | symbol-permutation OOD、data efficiency | 先验无稳定增益或只在单一编码上过拟合 |
| P5 修订 | incremental local revision vs batch refit | recovery、forgetting、revision cost | 局部更新不能改善成本/稳定性 |
| P6 证据隔离 | adversarial evaluator-label injection | learner-visible byte/payload absence | 任一 Locked-Test 标签能到达 learner |

## 5. 立即实施顺序

1. 在 v0.3 中新增 evaluator-only event/schema 与 learner/evaluator projection；不改写 v0.2 历史事件。
2. 强制 structure/candidate/lifecycle/revision 的 learner_track 一致性；跨轨道共享必须显式声明 shared_scope，默认禁止。
3. 给 E09 adapter 拆分 reveal_feedback() 与 evaluator-only record_evaluation()；后者绝不能调用 learner reveal()。
4. 将 E12-A6 runner 的真实 prediction commit 与 evaluation reveal 写入同一 ledger；删除用合成 step number 代表持久化因果链的说法。
5. 接入 E12-A1/A2/A3 的真实调用，完成一个端到端 MTS-0 episode。
6. 再加入 B2/B4/B8/B64/T3/H3 结构先验对照实验。

## 6. 验收标准

MTS-0 只有同时满足以下条件才算完成：
- 单 episode 全链路可运行、可重放、结果摘要稳定；
- 所有模型预测先 commit，评估标签后 reveal；
- Locked-Test freeze 在 prediction commit 之前 durable；
- learner projection 对 Locked-Test 原始标签和 evaluator-only provenance 做字节级排除；
- 跨轨道 support 引用在 append 与 replay 两处都拒绝；
- v0.1/v0.2 历史事件读取兼容；
- E09 learner 只能接收显式授权的 feedback/challenge release；
- 至少三个独立 seed family、locked OOD 和匹配基线；
- 报告 coverage、accuracy、abstention、calibration、compute/search cost、revision cost；
- 失败实验和负结果保留，不允许只报告最佳 seed。

## 7. 当前状态

- v0.3 原子事件存储：已有实现与绿色 CI，但仍是实验模块。
- evaluator/learner 分离：审查中，未完成。
- track 隔离：审查中，未完成。
- E09/E12 durable causal integration：未完成。
- MTS-0 端到端训练闭环：未完成。
- 易象/太玄结构先验比较：已有编码与有限诊断，未完成系统对照。

本文件是研究/实施门禁，不代表以上未完成事项已经实现。