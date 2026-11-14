# N0.10 实现审查与下一轮基准门槛

日期：2026-11-11  
对应分支：research/n10-learnable-role-composition-2026-11-11  
对应 PR：#181（Draft；未合并）  
审查范围：prototype/n09_learnable_srok.py、tests/test_n09_learnable_srok.py、N0.10 设计说明

## 1. 本轮审查结论

N0.10 已经是可训练的结构评分器原型，而不再只是 N0.9 研究协议。它使用纯 Python 的结构 softmax 训练，具有角色条件 unary 权重、显式 pairwise/triple 逐维乘积特征、类型/标签硬过滤、有限笛卡尔组合、证据 ID 聚合和置信分差拒答。

但当前测试任务主要证明“代码能训练并拟合一个有明显单节点角色特征的合成任务”。它还没有证明模型必须使用三阶交互，也没有证明其优于 unary 或 pairwise 基线。当前不应把它称为已经验证的高阶认知模型。

## 2. 本轮发现并修复的边界缺陷

### 2.1 result_limit=1 曾绕过置信拒答

原实现先把排序结果截断到 result_limit，再用截断后的候选计算 top-1/top-2 margin。result_limit=1 时永远没有第二名，margin 被视为无穷大，低置信预测可能被错误接受。

修复：先基于完整的已搜索排序结果计算 top-two margin，再截断展示候选。新增 result_limit=1 的拒答回归测试。

### 2.2 零分差默认不拒答

原实现使用 margin < abstain_margin。默认阈值为 0 时，完全并列的候选不会触发拒答。

修复：使用 margin <= abstain_margin；新增精确并列分数的默认阈值测试。

### 2.3 搜索预算没有覆盖被唯一性约束拒绝的组合

原枚举器只在组合通过跨角色 node_id 唯一性检查后才增加 assignments 数量。大量重复成员组合会消耗实际计算，却不消耗 max_expansions 预算，导致预算报告低估搜索工作量。

修复：每检查一个笛卡尔组合先计入 expanded，再执行唯一性过滤；Prediction.expanded_assignments 现在报告实际检查的组合数。新增重复组合消耗预算测试。

### 2.4 训练角色池内重复 node_id 会重复加权候选

原训练入口没有拒绝单个 role pool 内重复 node_id。重复项会在笛卡尔积中制造重复结构，改变 softmax 概率质量。

修复：训练预处理阶段检查每个角色池的 node_id 唯一性；新增非法重复池测试。

## 3. 当前仍未解决的关键问题

1. **高阶必要性未证实**：现有训练生成器在每个角色的候选节点上直接植入该角色对应的高幅度特征。unary 角色检索就可能解决任务，三阶项并非必要。
2. **缺少强消融**：尚无同数据、同候选集、同预算下的 unary-only、pairwise-only、third-order、SROK-0/additive 基线对照。
3. **缺少结构归因干预**：尚未证明保留二元投影但破坏三元绑定会使 third-order 模型显著退化。
4. **检索指标缺失**：未单独报告正确节点进入 Top-K 的 Recall@K，也未绘制 Recall@K—组合预算曲线。
5. **训练数据规模与复杂度**：fit 对每个训练样本枚举完整角色笛卡尔积；复杂度随各角色池大小乘积增长。必须报告每样本候选数、训练内存和耗时。
6. **数值稳定性**：输入特征逐项有限不保证 pair/triple 乘积和最终点积有限。后续应加入特征幅值约束/归一化、交互特征有限性检查和溢出测试。
7. **校准尚未建立**：margin 是排序差，不是概率校准。不能将它直接解释为置信概率；需在独立 calibration split 上测 risk-coverage、ECE/Brier。
8. **E09 证据更新尚未接入**：当前 evidence_ids 是输出 provenance 聚合，不等于已实现预测—揭示—更新隔离。

## 4. 必须增加的高阶必要基准

下一轮不应继续用“目标节点拥有明显单点特征”的任务来证明高阶能力。

建议增加专门的 candidate-set 结构判别接口，使一个 episode 可以包含多个完整角色绑定候选及其独立标签。生成器应做到：

- unary 统计匹配：单个角色节点特征无法区分正负候选；
- pairwise 统计匹配：所有二元投影/二阶统计在正负组间匹配；
- triple 结构区分：只有正确的三角色联合绑定保留目标三阶关系；
- 角色置换负例：成员集合不变，仅交换角色后标签翻转；
- 高阶扰动：保留节点和二元边，打乱三元分组；
- 随机种子、实体、规则模板分组留出，避免近重复样本泄漏。

在此基准上比较：
- unary-only；
- unary + pairwise；
- unary + pairwise + triple；
- SROK-0 additive；
- 参数量匹配的 MLP/Set/Graph 对照。

若第三阶模型在高阶扰动后不退化，或 pairwise-only 达到相同性能，则不得声称其优势来自三阶结构。

## 5. CI 与训练状态

截至本审查，GitHub connector 对最新提交 d4fb30d5e0e252f1c0fb549d0eebbf61a90b865d 的 PR workflow 查询没有返回可见运行记录。因此：

- 本轮没有声称 CI 通过；
- 本轮没有声称新增测试已经执行；
- 本轮没有启动或声称完成模型训练；
- PR #181 仍是 Draft，未合并 main。

必须等待该 PR 对应的 Actions 结果，并在实际运行环境执行完整测试后，才能把软件验证标记为通过。

## 6. 进入下一阶段的门槛

N0.11 应优先完成高阶必要数据生成器、candidate-set evaluator、unary/pairwise/third-order 对照和 pairwise-preserving attribution。通过后再训练更复杂的神经检索器或加入易象算子先验。

易象/类象仍应作为可消融的候选算子先验；必须同时比较无先验、通用结构先验、随机置换先验、易象先验和错误先验。不得把卦象 ID embedding 的拟合结果当作类象机制学习。

**当前判断：N0.10 可以进入受控软件测试与基准构建阶段；尚不能进入“高阶能力已验证”或“完整 CPG-EI 已可训练”的阶段。**


## 7. Integration copy and hardening

The N0.10 source remains on its original Draft research branch. The P1 integration copy is imported as an isolated experimental scorer, not as a default SROK replacement. The integration copy adds finite-value checks for feature interactions, score/gradient/weight overflow, strict integer budgets and optimizer validation. It still requires the high-order necessity benchmark described above; no higher-order capability claim is made.
