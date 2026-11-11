# MCRL：元认知资源控制与计算价值调度

日期：2026-11-11  
阶段：研究设计 / C0 可执行规格  
上游：CSG-GCR（PR #164）  
状态：Draft；尚未实现、训练或实测

## 0. 核心问题

CSG-GCR 能产生候选结构并执行全局协调，但它仍缺少一个关键能力：决定接下来应该执行哪个认知动作、为它分配多少资源，以及何时停止、等待新证据或向用户提问。

本设计提出 MCRL（Metacognitive Control & Resource Loop，元认知控制与资源循环）。

MCRL 不负责直接回答问题，也不替代 RSDN、XSL、YXO 或 CSG-GCR。它观察认知系统当前状态，选择下一项计算/信息获取动作，并根据动作结果更新预算与策略。

核心主张：

**思考不是越多越好；应该继续执行那些预期能降低决策风险、增加有效信息或推进目标，而且收益足以覆盖成本的动作。**

本设计区分：
- 置信度：当前模型对候选的主观评分；
- 证据强度：候选得到多少独立、可追溯的支持；
- 不确定性：当前状态中尚未解决的不同类型未知；
- 计算价值：某项额外动作预计能改善多少最终决策；
- 终止条件：当前是否已足以给出结论、部分结论、拒绝结论或请求新信息。

## 1. 研究依据与限制

近期研究为该方向提供了动机，但不能直接证明 MCRL 有效：

1. Conformal Thinking 将计算预算选择重构为风险控制问题，并研究在目标风险下减少计算。其保证依赖验证集和校准条件，不能自动外推到任意开放世界任务。
   https://proceedings.mlr.press/v306/wang26hd.html

2. EAGer 根据熵信号分配额外分支预算，避免对所有输入进行同等规模的并行采样。
   https://proceedings.mlr.press/v306/scalena26a.html

3. AERA 研究指出，当前检查点的证据强度与未来答案正确性之间可能不是单调关系；控制器应估计剩余计算的潜在价值，而不是仅按当前置信度停止。
   https://arxiv.org/abs/2608.27964

4. ACL 2026 对 overthinking 的研究发现，增加推理预算可能出现边际收益下降，甚至使原本正确的答案被放弃。
   https://aclanthology.org/2026.findings-acl.1199/

5. REFRAIN 研究自适应识别冗余反思并停止推理。
   https://aclanthology.org/2026.acl-long.1256/

6. Plan and Budget 将复杂问题分解为不确定性不同的子问题，并按复杂度调度计算预算。
   https://proceedings.iclr.cc/paper_files/paper/2026/hash/ae8d4084f418bb51575c2ca6c658a05b-Abstract-Conference.html

## 2. MCRL 在整体架构中的位置

- ZNCA：持久认知状态、事件、证据与版本；
- XSL：类象发现、映射与结构变换；
- YXO：版本化易象算子；
- RSDN：学习关系状态变化和候选编辑；
- CCL：组合约束学习；
- CSG-GCR：候选结构生成、组合与全局协调；
- **MCRL：决定何时调用上述模块、调用哪个模块、调用多少次，以及何时停止；**
- Realizer：把当前已验证结果转换为语言、工具调用或行动。

MCRL 读取的是状态快照和预算，不应直接修改事实状态。所有状态修改仍由既有验证和事件提交机制负责。

## 3. 控制循环

每轮控制分为六步：

1. Observe：读取当前状态、候选分布、未解决约束、证据和资源账本。
2. Diagnose：识别阻塞结论的关键未知与冲突。
3. Generate Actions：生成有限的下一步动作集合。
4. Estimate Value：估计每个动作的预期收益、成本、风险和可逆性。
5. Select & Execute：选择一个或一组可并行且互不冲突的动作。
6. Update & Decide：更新状态与预算，判断继续、停止、等待、询问或升级。

控制器应当是事件驱动的：新观察、新证据、验证失败、分支冲突、预算变化或用户目标变化，都可以触发重新调度。

## 4. 认知状态诊断：不确定性不能压成一个数字

定义诊断向量：

```
UncertaintyProfile {
  epistemic_uncertainty       // 模型/知识不足
  aleatoric_uncertainty       // 观察本身噪声或随机性
  structural_ambiguity        // 多种结构解释均兼容
  evidence_insufficiency      // 缺少必要证据
  constraint_conflict         // 约束之间冲突
  temporal_uncertainty        // 时间、时效或顺序不明
  model_disagreement          // 不同 proposer / verifier 分歧
  out_of_distribution         // 输入超出已校准分布
  calibration_status
}
```

这些量不能直接相加后当作真实概率。它们首先是不同原因的诊断指标，必须分别校准，并记录估计方法和适用范围。

例子：
- 多个模型给出不同答案，可能是模型不确定，也可能是问题存在多种真实解释；
- 证据不足不是再采样更多模型就能解决；
- 观察本身含噪时，继续做同一种推演可能只会重复噪声；
- 时间信息缺失时，最有价值的动作可能是询问时间，而不是扩大候选束。

## 5. 动作空间（Action Space）

控制器可以选择：

- EXPAND_CANDIDATES：扩展候选结构；
- MERGE_CANDIDATES：尝试候选组合；
- VERIFY_CONSTRAINT：验证关键约束；
- RETRIEVE_MEMORY：检索历史事件和证据；
- APPLY_OPERATOR：应用指定版本的 YXO/XSL 算子；
- RUN_COUNTERFACTUAL：建立反事实分支；
- SEEK_EXTERNAL_EVIDENCE：调用已授权的搜索/工具；
- REQUEST_OBSERVATION：请求新的环境观察；
- ASK_USER：向用户提出一个必要澄清问题；
- COMPRESS_STATE：把非活动区域压缩为带引用的状态摘要；
- REPAIR_PLAN：重新分解目标或更换推演路径；
- STOP_WITH_RESULT：输出当前可支持的结果；
- STOP_WITH_PARTIAL：输出已验证部分并说明未决项；
- ABSTAIN：拒绝作出没有依据的确定结论；
- DEFER：等待外部条件或未来事件。

动作定义必须声明：
- preconditions；
- expected_effects；
- resource_estimator；
- reversibility；
- required_permissions；
- expected_observation；
- failure_modes；
- timeout / budget cap。

MCRL 只能选择权限允许的动作。高风险、外部副作用动作必须经过单独授权流程，不能因计算价值高而自动执行。

## 6. 计算价值（Value of Computation）

不能把“模型分数提高”直接等同于“认知质量提高”。

对动作 a，定义一个待估计的价值向量：

```
ActionValue(a) = {
  expected_decision_risk_reduction,
  expected_information_gain,
  expected_goal_progress,
  expected_conflict_resolution,
  expected_evidence_gain,
  expected_state_repair,
  compute_cost,
  latency_cost,
  memory_cost,
  energy_cost,
  external_action_risk
}
```

初期采用受约束的成本效益选择，而非一个未经校准的万能分数：

```
eligible(a) =
  permissions_ok(a)
  AND hard_constraints_ok(a)
  AND resource_budget_ok(a)

select a from eligible actions
  where conservative_lower_bound(benefit(a))
        > cost(a) + risk_penalty(a)
```

若多个动作互相依赖，应先执行前置动作；若动作可并行且不争用关键资源，可以组成 ActionBatch。

收益估计要使用历史校准数据。对新任务类型、OOD 状态或样本不足的动作，扩大不确定区间，不能伪造精确收益。

## 7. 关键未知驱动（Bottleneck-Driven Control）

控制器不应平均扩展所有分支，而应先找到当前结论的关键阻塞点。

定义 BottleneckRecord：
- blocker_id；
- affected_claims；
- missing_evidence；
- violated_constraints；
- uncertainty_type；
- candidate_actions；
- dependency_scope；
- resolution_status。

选择动作的依据是它能否解决关键 blocker，而不是它能否生成更多文本或更多候选。

例如：
- 关键争议在时间先后：优先验证时间约束；
- 关键争议在类象映射：优先运行 XSL 对照和反例搜索；
- 关键争议在证据缺失：优先检索或询问，不盲目增加 proposer；
- 关键争议在组合深度：局部扩展 CSG-GCR 的 proof trace；
- 关键争议在模型能力：考虑升级模型或请求外部计算。

## 8. 停止、继续与升级：多条件决策

禁止只用单一置信阈值停止。

终止判定至少考虑：

1. 目标完成度：用户要求的任务是否已达到可交付程度；
2. 硬约束：是否有未解决的关键约束；
3. 证据完整性：结论所依赖的证据是否可追溯；
4. 风险：当前结果的错误风险是否低于任务允许范围；
5. 边际价值：可用动作的预期收益是否仍大于成本；
6. 资源：是否接近 RAM、延迟、能耗或时间上限；
7. 可逆性：是否可以先给部分结果，后续再修订；
8. 用户成本：是否应请求用户补充信息，而非消耗更多计算。

状态：
- CONTINUE：有正价值动作且预算充足；
- STOP_VERIFIED：目标和必要验证已完成；
- STOP_PARTIAL：已有可用的已验证部分；
- ASK_USER：缺少只有用户能提供的信息；
- WAIT_FOR_EVIDENCE：等待外部证据或事件；
- ESCALATE：需要更强模型、工具或人工审核；
- ABSTAIN：当前无法可靠回答；
- BUDGET_EXHAUSTED：预算耗尽，必须如实报告。

重要：BUDGET_EXHAUSTED 不等于 STOP_VERIFIED。预算耗尽只能说明停止计算，不意味着问题已经解决。

## 9. 防止控制器振荡和自我强化

动态控制器可能反复在“扩展—合并—拆分—扩展”之间切换。需要：

- hysteresis：进入/退出某种模式使用不同阈值；
- cooldown：同一失败动作在状态未变化前不得立即重复；
- action fingerprint：识别等价动作，阻止重复执行；
- branch lineage：跟踪分支来源，避免重复计算；
- evidence novelty：检查新动作是否真的带来新证据；
- rollback：当新计算降低验证质量时，恢复上一个有效状态；
- budget reserve：保留一部分资源用于最终验证和结果实现。

不得让控制器通过反复采样自己生成的证据来提高置信度。自生成候选不是独立外部证据。

## 10. 易象思想如何进入控制机制

这里可以研究易学中的“时、位、变、应、度”，但必须转成可检验的操作变量：

- 时：状态和证据的有效时间、变化速率、时效衰减；
- 位：当前对象在关系结构中的角色与约束位置；
- 变：状态变化方向、变化幅度和触发条件；
- 应：对象/关系之间的响应、反馈与相互制约；
- 度：动作强度、搜索范围、资源投入和停止边界。

“时中”可形成一个研究假设：动作策略应随状态阶段改变，而不是固定采用同一搜索强度。
“动静”可形成另一假设：当状态稳定且证据充分时减少扰动；当关键关系发生变化时重新激活相关子图。
“开合”可以对应探索与收敛两种控制模式：
- 开：增加候选多样性、扩大检索范围、探索新关系；
- 合：集中验证、压缩候选、固定已确认约束。

这些不是易学理论已经证明适用于 AI 的结论。必须与随机控制、通用不确定性策略和普通启发式调度器做消融对照。

## 11. 移动端多维预算

预算不应只有 Token 数。定义 ResourceLedger：

```
ResourceLedger {
  wall_clock_deadline_ms
  cpu_time_budget_ms
  accelerator_time_budget_ms
  peak_ram_budget_bytes
  disk_io_budget_bytes
  energy_budget_mwh
  max_active_nodes
  max_candidates
  max_branches
  max_branch_depth
  max_verifier_calls
  max_external_calls
  reserved_finalization_budget
}
```

Android 端资源由运行时测量，不用模型自报。每个动作执行前估算成本，执行后记录真实成本，持续修正 estimator。

内存控制：
- 冷层事件和证据保留在磁盘；
- 温层索引按需分页；
- 热层只驻留活动子图；
- 候选分支共享父状态，只存稀疏 delta；
- 临时张量、候选和中间激活及时释放；
- 预算紧张时优先压缩非活动状态，而不是删除证据来源。

## 12. Anytime 输出：任何时刻都能交付当前最好结果

MCRL 应支持 anytime 行为：

- T0：立即提供低成本、低风险的初步结果；
- T1：补充必要的结构和证据验证；
- T2：探索有价值的替代解释；
- T3：完成高成本验证和反例检查；
- T4：输出最终结果或说明仍无法解决的部分。

每个阶段都必须区分 VERIFIED、INFERRED、HYPOTHESIS、UNKNOWN。后续计算只能增加或修订状态，不能把未验证假设伪装成已验证事实。

## 13. C0 最小原型

先不训练控制模型。实现确定性 MCRL 模拟器：

输入：
- 一个 CSG-GCR 候选图；
- 当前未解决约束；
- 多维 ResourceLedger；
- 动作成本估计表；
- 动作执行结果模拟器。

输出：
- 下一步动作；
- 选择理由；
- 预计收益/成本区间；
- 更新后的预算；
- 继续/停止/询问/升级状态；
- 可复现的控制轨迹。

C0 必须覆盖：
1. 简单问题不触发大规模候选扩展；
2. 多候选分歧时优先验证关键差异；
3. 证据不足时选择检索/询问，而非重复采样；
4. 高成本动作预期收益不足时提前停止；
5. 预算耗尽时输出 STOP_PARTIAL 或 BUDGET_EXHAUSTED；
6. 新证据推翻旧结论时能够回滚和重算；
7. 防止重复动作和控制振荡；
8. 预留最终验证资源。

## 14. 学习阶段

MCRL-1：从模拟轨迹学习动作价值预测；
MCRL-2：学习 blocker 识别和动作路由；
MCRL-3：在离线日志上训练策略，使用保守策略评估；
MCRL-4：受限在线适配，只更新成本估计和校准参数；
MCRL-5：跨任务迁移，并对 OOD 输入采用保守回退。

不能一开始就用强化学习让控制器自由探索真实工具。先在模拟环境和离线轨迹上验证，再逐步开放动作。

## 15. 实验设计

基线：
- 固定推理预算；
- 固定步数；
- 单一置信度阈值；
- 熵触发扩展；
- 仅基于自一致性；
- CSG-GCR 无控制器；
- MCRL 确定性规则；
- MCRL 学习型策略。

任务：
- 简单、困难和不可解问题；
- 证据缺失与证据冲突；
- 类象映射多解；
- OOD 组合推理；
- 新证据推翻旧结论；
- 长时间运行的多阶段任务；
- 手机端 RAM/能耗/延迟受限任务。

指标：
- Task Success / Verified Success；
- Risk at Stop；
- Premature Stop Rate；
- Overthinking Rate；
- Expected Value Calibration；
- Action Selection Regret；
- Evidence Novelty；
- Duplicate Action Ratio；
- Time-to-Useful-Answer；
- Anytime Index；
- Compute / Energy / Peak RAM；
- Budget Exhaustion Reporting Accuracy。

关键实验：
- 相同平均预算下比较正确率和风险；
- 相同风险目标下比较平均计算成本；
- 改变问题难度分布，测试策略是否过拟合；
- 让中途正确答案被诱导偏离，检测过度思考；
- 让高置信但错误的候选出现，检测置信阈值失效；
- 让证据不足但模型分歧很低的任务出现，检测虚假确定性；
- 让同一工具返回重复结果，检测控制器是否误把重复当作新信息。

## 16. 失败判据

- 只降低计算量，却明显提高错误风险；
- 把模型置信度当作证据强度；
- 在证据不足时持续自我采样；
- 新推理覆盖旧的已验证结果，却没有反例或证据；
- 资源预算估算与真机测量长期严重偏离；
- 控制器只在训练任务难度分布上有效；
- 复杂控制策略的成本高于其节省的推理成本；
- 无法区分 STOP_VERIFIED 与 BUDGET_EXHAUSTED；
- 任何权限受限动作被自动执行。

## 17. 与 CSG-GCR 的接口契约

CSG-GCR 输出：
- candidate_graph_snapshot；
- unresolved_constraints；
- conflict_regions；
- proof_status；
- candidate_value_features；
- branch_cost_estimates。

MCRL 输入上述字段，输出：
- selected_actions；
- action_budget；
- action_dependencies；
- stop_or_continue_decision；
- decision_trace；
- resource_reservation。

MCRL 不得直接修改候选事实或证据。动作执行结果必须作为新事件回写 ZNCA，再由验证器更新状态。

## 18. 当前结论

MCRL 应成为 ZNCA/RSDN/CSG-GCR 上方的资源与策略控制层。它解决的不是“如何产生更多思考”，而是“如何选择最有价值的下一步认知动作”。

建议优先实现 C0 确定性控制器。它能检验动作协议、成本账本、停止语义和 anytime 交付。只有 C0 的控制轨迹可复现、可测量后，才值得训练策略模型。

当前仍未解决：
1. 如何可靠估计动作的未来边际收益；
2. 如何在开放世界任务中校准停止风险；
3. 如何区分模型不确定与真实世界随机性；
4. 如何处理用户目标变化和长期任务优先级；
5. 如何在资源不足时公平地分配多任务预算；
6. 易象“时、位、变、应、度”是否能带来超过通用控制策略的可重复收益。

**本文件是研究规格，不是已实现功能或实验结果。**
