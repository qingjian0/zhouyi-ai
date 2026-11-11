# ZPCM N0.4：认知恢复与主动再推演

日期：2026-11-11  
状态：研究设计 / 叠加于 N0.3；文档交付，不代表实现、测试通过或真机验证。  
上游：PR #172，N0.3 head `36a1b7e8594520c80342f833d02d90972788a49c`

## 1. 目标与核心判断

N0.3 解决“已有推导是否仍然成立”：版本化依据、多重 justification、增量失效与状态维护。

N0.4 解决另一类问题：“当既有推导失去支持后，系统如何主动寻找新的解释与证据，并在不篡改历史的前提下形成新的认知？”

N0.4 是认知恢复（cognitive recovery）与主动再推演（re-derivation）机制，不是自动把旧结论复活，也不是把模型生成的合理故事直接写成事实。

核心闭环：

1. 发现目标结论失去支持、过期、冲突或关键关系断裂；
2. 将故障转换为明确的缺失约束与待解释观察；
3. 检索已有证据、记忆、关系和可用观察；
4. 由 XSL/E13 提出多样化类象与关系映射候选；
5. 由 CSG-GCR 生成多条可组合推导结构；
6. 通过反证、反事实、来源相关性和约束验证筛选；
7. RSDN 提出状态编辑，确定性验证器决定是否可提交；
8. 新推导以新 Derivation / Justification / ClaimVersion 追加到 ZPCM；
9. 对未解决部分保留 UNKNOWN / UNSUPPORTED / DISPUTED / STALE，不伪造完整恢复。

## 2. 理论定位：从维护转向溯因与假设修复

N0.4 的主要推理任务是溯因（abduction）：给定观察与约束，提出能够解释它们的候选假设，再比较候选的解释力、代价和反证。

这与演绎不同：
- 演绎：前提成立时，结论是否由规则必然推出；
- 归纳：从多个样本总结可能稳定的模式；
- 溯因：寻找能够解释观察的候选原因或结构。

溯因只产生“值得检验的假设”，不自动产生事实。候选必须经过证据验证和约束检查。

参考脉络：
- Doyle (1978/1979) 的 TMS：记录信念理由、依赖定向回溯与增量维护；
- de Kleer (1986) 的 Assumption-based TMS：以假设集组织多个潜在解，支持不一致信息与候选上下文切换；
- Johnson & Shapiro (2005) 的 Dependency-Directed Reconsideration：只重新检查受变化影响的信念子集；
- Bai et al. (ACL 2024) 的复杂逻辑假设生成：从观察生成复杂逻辑假设，但仅靠结构相似的监督目标不能保证泛化，需结合知识图约束；
- 2026 年关于溯因任务评测的工作提示：假设生成、候选判别、证据到达后的修订、主动选择下一条证据应分别评估，不能用单一选择题代表完整溯因能力。

N0.4 吸收这些研究方向，但不等同于任何传统 TMS 或知识图生成方法。

## 3. 输入：恢复请求 RecoveryRequest

恢复不是对整个知识库无差别搜索。N0.3 应向 N0.4 发送可定位、可审计的恢复请求。

建议字段：
- `recovery_request_id`
- `target_claim_id` / `target_claim_version_id`
- `trigger_event_seq`
- `trigger_reason`：ALL_JUSTIFICATIONS_INVALID / SOURCE_REVOKED / RELATION_BROKEN / TEMPORAL_EXPIRED / CONFLICT_DETECTED / MODEL_OR_RULE_DEPRECATED / USER_CHALLENGE
- `missing_constraints[]`：缺失的必要条件或关系角色
- `observations[]`：当前仍有效的观察版本引用
- `scope`：时间、空间、对象、任务、权限等边界
- `as_of_seq`：本次恢复所使用的账本快照水位
- `priority` / `deadline` / `budget_profile`
- `status`：PENDING / ACTIVE / PARTIAL / RESOLVED / BLOCKED / EXHAUSTED / CANCELLED

必须引用具体版本，不得只引用逻辑 claim id。请求快照确定后，候选生成过程中出现的新事件应进入后续增量批次，不能悄悄改变当前批次的输入世界。

## 4. 故障解释：把“失效”转成可搜索的问题

恢复引擎首先生成 FailureProfile，而不是直接开始生成答案。

FailureProfile 包含：
- 哪些 justification 失效、为何失效；
- 哪些输入仍然有效；
- 哪些关系角色缺失或发生变化；
- 哪些时间/位置/作用域条件不再满足；
- 哪些冲突尚未解决；
- 哪些结论只是过期，哪些是被反证；
- 哪些来源共享同一祖先，避免重复计证；
- 可被新观察检验的区分性预测。

把缺失约束分类：
1. Missing entity：关键对象尚未识别；
2. Missing attribute：对象属性缺失；
3. Missing relation：对象间关系未知或断裂；
4. Missing role：主体、客体、条件、工具、结果等角色不确定；
5. Missing condition：触发条件、边界条件或例外未确定；
6. Missing temporal alignment：证据发生时间与结论有效时间不匹配；
7. Missing provenance：来源不明或版本不可追溯；
8. Contradictory constraint：现有观察之间存在无法同时满足的约束。

FailureProfile 应是结构化的任务定义，不能把模型的自然语言解释当作唯一输入。

## 5. 候选假设与推导结构

### 5.1 CandidateHypothesis

候选不是一个孤立句子，而是一个可检验的结构对象：
- `candidate_id`
- `target_claim_id`
- `candidate_graph_ref`
- `hypothesis_kind`：ABDUCTIVE / ANALOGICAL / CAUSAL / TEMPORAL / STRUCTURAL / COUNTERFACTUAL
- `assumptions[]`
- `predicted_observations[]`
- `supporting_refs[]`
- `contradicting_refs[]`
- `unresolved_constraints[]`
- `scope`
- `generator_id` / `generator_version`
- `candidate_parent_ids[])
- `diversity_signature`
- `status`

候选与事实分离。候选状态至少包括 GENERATED、FILTERED、NEEDS_EVIDENCE、CONTRADICTED、VALIDATED、COMMITTED、EXPIRED。

### 5.2 非相邻组合是一级能力

不能只生成相邻 token、相邻节点或单条链式路径。CSG-GCR 应允许从一个有限候选池中选取非连续元素，形成新的组合结构，例如：

`a + b + c + e -> H`

其中 d 可以不参与；也可以从不同时间、不同关系簇抽取元素，但必须满足 scope 与版本约束。

候选结构应显式区分：
- 必要前提 AND；
- 多条替代路径 OR；
- 可选条件 OPTIONAL；
- 排除条件 EXCLUSION；
- 解释上下文 CONTEXT；
- 反证 DEFEATER。

不能把“元素组合自由”误解为“任意拼接都有效”。全局约束、角色类型、时间一致性、来源谱系和反例检查必须限制组合。

### 5.3 多路径与候选族

同一目标至少允许多个结构不同的候选族并行探索。候选之间记录：
- 共享输入与共享来源；
- 结构差异；
- 关键假设差异；
- 预测结果是否可区分；
- 失败原因是否相同。

如果所有候选都来自同一个错误假设或同一来源，它们只是表面多样性，不应视为真正的独立探索。

## 6. 易象与类象：作为可学习的结构变换先验

易象不是给普通图节点贴上乾坤震巽标签。它应影响系统如何提出、变换和比较关系结构。

建议将下列概念实现为可组合算子族；具体语义必须由数据与任务学习校准，不把古典术语直接等同于现代数学对象。

| 易象概念 | 候选计算操作 | 必须保留的审计信息 |
|---|---|---|
| 取象 | 从观察抽取实体、属性、关系、角色 | 原始观察、抽取置信与遗漏 |
| 类象 / 比类 | 在结构层寻找相似关系模式 | 正向匹配、反向不匹配、映射角色 |
| 变 | 对状态、属性或关系施加变换 | 变换前后版本、触发条件 |
| 互 | 从局部结构抽取内部关系组合 | 组合输入及非相邻选择依据 |
| 错 | 对关系极性、位置或对应关系作对照变换 | 对照轴与保持/翻转项 |
| 综 | 变换观察视角或关系方向 | 视角映射、可逆性与信息损失 |
| 应 | 检验不同位置/对象之间的呼应约束 | 关联对象、应答条件 |
| 时 | 对结构施加时间窗口和阶段条件 | valid-time、时序顺序 |
| 位 | 对结构施加角色、层级与位置约束 | 角色类型、位置约束 |

算子输出必须包括：
- 输入结构版本；
- 变换定义与版本；
- 输出候选结构；
- 保持的不变量；
- 允许变化的维度；
- 失败条件；
- 支持与反对证据；
- 适用范围。

算子参数可学习，算子本身不必永远固定。训练目标应包括：映射正确性、关系保持、反例区分、跨域泛化、恢复后预测质量，而非只学习术语分类。

## 7. 反证、反事实与抗确认偏误

### 7.1 反证候选必须进入同一搜索流程

不能只生成支持目标的解释。每个恢复批次必须：
- 尝试生成至少一个有实质差异的对抗解释；或
- 明确记录为何在当前预算和证据范围内无法生成。

反证可以是：
- 目标关系不存在；
- 关系方向相反；
- 另一原因同样解释观察；
- 关键条件不成立；
- 证据只在不同时间或作用域成立；
- 结论是共同来源造成的重复表象。

### 7.2 反事实检验

对每个高优先级候选，构造最小反事实：
- 若核心假设不成立，哪些观察应改变？
- 若替代假设成立，哪些现有约束会被违反？
- 哪个新观察最能区分两个候选？
- 候选是否只靠自身结论作为前提？
- 删除某个关键前提后，候选是否仍然成立？

反事实是检验工具，不是实际世界事实。反事实分支必须标记为假设上下文，不得混入当前事实投影。

### 7.3 防止循环自证

候选依赖图必须经过环检测。恢复候选不得通过“候选支持候选自身”形成闭环。对递归假设未来若要支持固定点推理，必须另立规范并定义语义。

### 7.4 来源相关性惩罚

评分时不能简单数支持边。应计算来源祖先重叠、证据重复、同一模型生成的伪独立解释等因素。首版采用可解释的 provenance overlap 指标，不宣称得到统计独立概率。

## 8. 候选评估：多目标而非单一置信分

建议候选评估向量：
- `constraint_coverage`：满足的必要约束；
- `contradiction_cost`：与已验证事实的冲突；
- `evidence_quality`：证据来源、直接性、时效和版本；
- `provenance_overlap`：支持来源相关性；
- `predictive_discrimination`：能否产生区分性预测；
- `scope_fit`：时间、对象、任务范围匹配；
- `structural_complexity`：引入的新假设与结构复杂度；
- `robustness`：对输入扰动、删去单一证据的稳定性；
- `verification_cost`：进一步验证所需成本；
- `risk`：错误恢复造成的下游影响。

首版不把这些维度粗暴加权为一个“真值概率”。采用分层筛选：
1. 硬约束过滤；
2. 已知反证过滤或标记冲突；
3. 证据谱系与范围审查；
4. 多目标 Pareto 排序；
5. MCRL 根据任务价值和成本选择下一步；
6. 通过验证的候选才允许提交。

候选可以高解释力但仍是 NEEDS_EVIDENCE；不可因为排序第一就自动变成事实。

## 9. 主动选择下一条证据：Value of Information

恢复引擎不应只问“哪个候选分数最高”，还应问“下一步观察什么最能减少不确定性”。

对候选观察动作 o，估计：
- 可能区分的候选数量；
- 预期减少的未解决约束；
- 预期信息增益；
- 获取成本与延迟；
- 权限、隐私和安全限制；
- 观察失败或不可获得的概率。

建议使用可解释的近似效用：
`VOI(o) = expected_recovery_gain(o) - acquisition_cost(o) - risk(o)`

首版不要求精确贝叶斯 VOI；可用离散等级或经验模型。任何外部观察动作必须受工具权限控制，不能因“主动认知”而越权访问或执行。

## 10. 预算与 anytime 恢复

恢复引擎必须能在普通计算机上分批运行，并支持中断恢复。预算至少包含：
- 最大候选数；
- 最大组合宽度；
- 最大推导深度；
- 每批节点/边数量；
- 最大 CPU 时间片；
- 最大临时 RAM；
- 最大外部观察次数；
- 最大反事实分支数；
- 总恢复成本。

优先级由 MCRL 决定，参考：
- 当前任务是否引用目标；
- 目标影响的下游范围；
- 失败原因是否可修复；
- 新证据可获得性；
- 预计恢复价值；
- 风险与计算成本。

预算耗尽时返回 PARTIAL 或 EXHAUSTED，并保存 checkpoint。不得把“没算完”误报为“验证失败”，也不得把 STALE 伪装为 CURRENT。

## 11. 恢复会话与持久化模型

建议新增持久化实体：

### RecoverySession
- `recovery_session_id`
- `recovery_request_id`
- `snapshot_seq`
- `algorithm_version`
- `budget_profile_id`
- `status`
- `created_event_seq` / `updated_event_seq`

### CandidateBatch
- `candidate_batch_id`
- `recovery_session_id`
- `batch_no`
- `input_cursor`
- `candidate_cursor`
- `generator_version`
- `status`
- `idempotency_key`

### CandidateEvaluation
- `candidate_id`
- `evaluation_version`
- `constraint_report_ref`
- `counterexample_report_ref`
- `provenance_report_ref`
- `result_state`
- `evaluated_event_seq`

### RecoveryCheckpoint
- `recovery_session_id`
- `completed_stage`
- `cursor_state`
- `budget_consumed`
- `last_committed_event_seq`

幂等键建议：
`(recovery_session_id, batch_no, generator_version, snapshot_seq)`

恢复会话的候选与评估结果可以作为事件追加；临时缓存可重建。进程崩溃后从最近 checkpoint 继续，重复批次不得重复提交 Derivation。

## 12. 提交协议：候选不直接写入当前认知

候选进入当前认知状态必须走严格协议：

1. 候选图冻结并绑定 snapshot_seq；
2. 运行类型、时间、作用域、环和全局约束检查；
3. 检查支持与反对证据，生成可审计报告；
4. 对新推导输入引用具体 ClaimVersion / EvidenceVersion；
5. 由验证器产生 ACCEPT / REJECT / NEEDS_EVIDENCE / QUARANTINE；
6. ACCEPT 时追加 DerivationCreated、JustificationAdded、ClaimVersionAsserted 等事件；
7. N0.3 按 AND/OR 规则重新计算支持状态；
8. 物化投影并推进 evaluation watermark；
9. 保留旧版本与原失败记录。

如果候选只恢复了部分关系，则只提交已验证部分，其余目标保持 UNKNOWN / UNSUPPORTED / DISPUTED。禁止为了让整个目标“看起来恢复”而补齐缺失证据。

## 13. 与其他模块的职责边界

- ZPCM N0.1：不可变事件账本、确定性投影。
- ZPCM N0.2：双时间 ClaimVersion、as-of 查询。
- ZPCM N0.3：多重依据、推导谱系、增量失效和状态维护。
- ZPCM N0.4：恢复请求、故障解释、主动溯因、候选再推演、反事实与恢复会话。
- XSL/E13：产生类象映射与关系变换候选；输出正反匹配证据。
- CSG-GCR：组合候选结构、支持非相邻元素组合、求解全局约束。
- RSDN：提出认知状态编辑或候选关系变化。
- MCRL：选择恢复任务、预算、候选批次与下一条观察。
- 验证器：确定性检查并决定是否允许写入。
- 语言生成器：只读取当前认知快照；把假设、冲突和未知明确表达。

任何生成模块不得绕过验证器和事件账本修改当前认知投影。

## 14. 确定性验收测试

R1. **新推导不复活旧版本**：旧 ClaimVersion 曾 UNSUPPORTED；新证据到达后必须创建新 Derivation/Justification/ClaimVersion，旧状态历史仍可查询。

R2. **非相邻组合**：候选生成器可从 a,b,c,d,e 中选 a,b,c,e，跳过 d；所有输入版本与组合理由可追溯。

R3. **多候选并行**：同一恢复请求可同时保留多个候选族；一个候选失败不关闭其他分支。

R4. **反证生成**：恢复批次产生对抗候选，或记录预算/输入不足导致未能生成的明确原因。

R5. **反事实隔离**：假设分支不得污染现实事实投影或当前有效记忆。

R6. **共享来源识别**：多个候选若共享同一证据祖先，不得计为独立证据。

R7. **循环自证阻断**：候选图形成环时拒绝提交或隔离。

R8. **部分恢复**：一个复合目标的部分子结构验证成功时，只提交该部分，未解决部分保持未知/争议状态。

R9. **时位约束**：有效时间或角色位置不匹配的候选不能通过验证。

R10. **候选顺序稳定性**：同一冻结快照、同一算法版本和预算下，确定性阶段结果可复现；随机生成阶段必须记录 seed 和模型版本。

R11. **崩溃恢复**：任意阶段中止后可从 checkpoint 继续，幂等键阻止重复提交。

R12. **预算严格受限**：候选数、组合宽度、时间片和临时 RAM 均不超过配置上限；预算耗尽状态准确。

R13. **新证据区分候选**：新增观察能使至少一个候选被排除或显著改变排序；若不能区分，系统应如实保留不确定性。

R14. **增量与全量一致**：恢复提交后的 N0.3 投影与从事件账本全量重建一致。

## 15. 评测与基准

不能只用“恢复成功率”作为指标。至少评测：

- hypothesis recall：参考解释是否出现在候选集；
- candidate precision：候选中有多少满足约束；
- counter-hypothesis coverage：对抗解释覆盖率；
- evidence traceability：输入证据版本可追溯比例；
- provenance calibration：相关来源是否被正确识别；
- recovery latency：从失效到部分/完整恢复的耗时；
- compute per validated recovery：每个验证恢复消耗的计算；
- false resurrection rate：无新有效依据却恢复旧结论的比例；
- partial-state correctness：部分恢复是否准确；
- robustness：删去一个来源或改变事件顺序后的稳定性；
- incremental/full rebuild equivalence：增量与全量投影一致率。

测试集要包含：多解、无解、欠定、矛盾、共享来源、时间错位、角色反转、非相邻组合、分布外类象与诱导性错误线索。

## 16. 实施顺序

建议拆成可独立审查的小步，而不是一次实现全部：

- N0.4-D0：恢复请求、FailureProfile 和状态机 schema；
- N0.4-D1：候选结构、非相邻组合与 provenance；
- N0.4-D2：反证/反事实和循环自证阻断；
- N0.4-D3：预算、checkpoint、幂等恢复会话；
- N0.4-D4：验证提交协议与部分恢复；
- N0.4-D5：基准集与增量/全量一致性测试。

先用确定性小型候选生成器验证数据流，再接入学习型 XSL/RSDN/CSG-GCR。不要先训练一个大模型，再试图用它解释无法审计的恢复结果。

## 17. 非目标与完成边界

本 PR 只提交研究设计文档，不包含 schema、恢复引擎、模型训练或测试实现。

N0.4 研究设计完成不等于认知恢复能力已经实现。工程原型完成至少需要：
1. 持久化 RecoveryRequest / RecoverySession / CandidateBatch；
2. 非相邻候选组合器；
3. provenance 与反证报告；
4. 反事实隔离和环检测；
5. 预算及 checkpoint；
6. 验证提交协议；
7. 上述确定性测试；
8. 增量/全量一致性测试；
9. 可复现性能基准。

普通计算机性能、手机性能和模型智能能力必须分别测量，不能用结构设计推断实际速度或效果。
