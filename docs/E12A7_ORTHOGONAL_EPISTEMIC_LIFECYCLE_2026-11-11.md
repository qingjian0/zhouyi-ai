# E12-A7：正交认知生命周期与反事实修订设计

日期：2026-11-11  
分支：research/e12a7-orthogonal-epistemic-lifecycle-2026-11-11  
状态：设计提案；未实现、未运行实验，不构成性能结论。  
前置：E12-A6 独立可辨识性审计与原语生命周期基准协议。

## 1. 核心发现：单一状态枚举会混淆不同问题

E12-A6 的生命周期状态（PROPOSED、TRAIN_SUPPORTED、GATE_VALIDATED、REUSED、CHALLENGED、RETIRED 等）适合描述工作流阶段，但不应同时承担“证据有多强”“适用范围是否稳定”“当前是否允许调用”等语义。

例如，一个原语可能：
- 在旧环境中 GATE_VALIDATED；
- 在新环境中因分布漂移而 CHALLENGED；
- 在旧环境仍可安全 REUSED；
- 在新环境必须 abstain。

若只保存一个全局状态，系统只能在“全局继续使用”与“全局废弃”之间二选一，丢失局部有效性。

**建议：把原语生命周期拆成多个正交维度，而不是继续扩展一个越来越大的 enum。**

## 2. 四个正交维度

### 2.1 Workflow stage（工作流阶段）

描述候选正在经历什么流程：

- OBSERVED
- PROPOSED
- DISCRIMINATION_PENDING
- TRAIN_SUPPORTED
- GATE_VALIDATED
- REUSED
- CHALLENGED
- REVISION_PENDING
- RETIRED

该维度由状态机控制，迁移必须有事件依据。

### 2.2 Epistemic status（证据状态）

描述当前证据支持到什么程度：

- UNKNOWN：尚无足够证据
- UNDERDETERMINED：多个候选在当前测量制度下不可区分
- SUPPORTED：在声明数据与范围内得到支持
- CONTRADICTED：存在尚未解决的冲突证据
- REFUTED_IN_SCOPE：在明确范围内被可重复反例否定

禁止把 SUPPORTED 简写成 TRUE。证据状态必须附带证据集版本、测量制度和范围。

### 2.3 Scope status（范围状态）

描述某一候选版本在某个范围中的适用情况：

- UNTESTED
- IN_SCOPE_SUPPORTED
- OUT_OF_SCOPE
- SHIFT_SUSPECTED
- SPECIALIZED

范围不是一个自由文本标签。至少应有稳定 scope_id、环境/实体分组、时间窗、前置条件与测量制度。相同原语可以在多个 scope_id 下有不同状态。

### 2.4 Invocation policy（调用策略）

描述运行时是否允许系统依赖该候选：

- ALLOW
- ALLOW_WITH_WARNING
- REQUIRE_CONFIRMATION
- ABSTAIN

调用策略由前三个维度和风险预算推导，不由提议器直接写入。被标记为 REUSED 的候选也可能在某个 scope 下必须 ABSTAIN。

## 3. 最小数据模型

每个候选版本是不可变对象：

- candidate_id：跨版本稳定身份
- version：单调递增版本号
- parent_versions：修订/组合的父版本集合
- definition_ast：规范化表达式
- type_signature：输入输出类型与单位
- scope_contract：适用范围约束
- grammar_version：表达式语言版本
- provenance：提议来源与父候选
- created_event_id：创建事件

所有变化写入 append-only event ledger，不原地覆盖候选定义。事件至少包含：

- event_id、event_type、candidate_id、candidate_version
- scope_id（允许为空，但必须说明全局事件原因）
- evidence_ids、measurement_regime_id
- actor/component、timestamp、policy_version
- previous_event_hash（可选的完整性链）
- decision、reason_code、cost

事件账本是历史事实；当前状态是由事件重放得到的投影。不得把投影反写成唯一真相。

## 4. 转移与投影规则

1. PROPOSED 只能由合法提议事件创建，且必须包含 AST、类型、范围和可执行预测。
2. DISCRIMINATION_PENDING 要求至少两个存活假设对某个合法测量产生不同预测。
3. UNDERDETERMINED 不等于失败：当所有可用测量都不能区分假设时，记录不可辨识并 abstain。
4. GATE_VALIDATED 必须绑定冻结的 candidate version、独立 Gate 证据与匹配基线；修改定义后不得沿用旧 Gate。
5. REUSED 只记录一次实际调用及其贡献，不自动提升证据状态。
6. CHALLENGED 是事件/工作流标记，不等于已证伪；必须进一步分类噪声、测量错误、范围外、漂移、真反例或未决。
7. REFUTED_IN_SCOPE 只对明确 scope_id 生效；不得自动推断所有范围都失效。
8. SPECIALIZED 必须产生新版本或新候选，并显式声明子范围；父版本保留并限制其原范围调用。
9. RETIRED 禁止普通调用，但保留完整谱系；重新启用必须创建新版本并重新验证。

## 5. 反事实修订：不能只追求解释已发生的反例

当候选被挑战时，系统应构造至少三种竞争解释：

- H1：候选机制本身错误；
- H2：候选只在更窄的 scope 内成立；
- H3：观测/测量过程发生变化，候选机制未变。

然后选择一个能区分这些解释的干预前测量或额外观测。若没有合法测量可区分，应输出 UNDERDETERMINED，而不是强行选择最顺眼的故事。

每次修订须保存：
- 被挑战的旧版本；
- 反例与其来源；
- 竞争解释集合；
- 被选择/未选择的测量及成本；
- 修订后的 AST 差异；
- 旧范围保留、缩小或撤销的理由；
- 新版本重新验证的结果。

## 6. 防止“自我解释”形成证据闭环

模型生成的解释、类比、卦象映射、内部置信度都不是外部证据。证据来源应分级：

- OBSERVATION：实际观测或测量结果；
- DERIVED：从明确规则可复算的派生结果；
- MODEL_JUDGMENT：模型判断、解释或类比；
- EVALUATOR：独立评估器输出。

MODEL_JUDGMENT 不得单独使候选从 UNKNOWN 升级到 SUPPORTED，也不得作为自己的独立验证样本。EVALUATOR 数据必须位于 learner 无法访问的边界外；只有经授权的判定结果可以进入公开证据账本。

## 7. 易象结构在此模型中的位置

阴阳、四象、八卦、六十四卦、卦变、五行与类象，只能作为候选结构生成器或归纳偏置来源：

- 阴阳：提出二元对偶/互补候选；
- 四象：提出二阶状态分组候选；
- 八卦：提出三位状态编码与层级分解候选；
- 六十四卦：提出六位复合状态空间候选；
- 卦变：提出状态转移候选；
- 五行：提出多关系有向作用图候选；
- 类象：提出跨域结构映射候选。

这些映射不写入证据状态，也不直接改变 invocation policy。每个候选都必须与无先验、随机先验、错位先验和数据学习先验比较；若错配先验仍带来相同收益，收益可能来自容量或正则化，而非传统结构本身。

## 8. 必须新增的验收测试

- 同一 candidate 在两个 scope 中分别支持与反驳，状态不得互相污染。
- GATE_VALIDATED 后修改 AST，旧 Gate 不得验证新版本。
- REUSED 但没有增量贡献，不能记为有效复用收益。
- CHALLENGED 后只有模型解释、没有新观测，不得升级或修订为已验证。
- UNDERDETERMINED 必须保留竞争候选并允许 abstain。
- 在 scope A 中 REFUTED，不得自动在独立 scope B 中 RETIRED。
- SPECIALIZED 必须创建明确 lineage，旧候选不可被静默覆盖。
- learner 输入相同但 evaluator 隐藏标签变化时，learner trace 必须逐字节一致。
- 事件重放必须确定性地产生相同状态投影。
- 候选排序、事件批处理顺序变化不得改变语义相同的最终投影。

## 9. 研究判断与下一步

本设计的关键价值不是增加更多“认知状态”，而是把三个常被混淆的问题拆开：

1. 工作流走到哪一步？
2. 证据在什么范围内支持或反驳什么？
3. 当前运行时是否允许依赖它？

建议实现顺序：
1. CandidateVersion 与 ScopeContract 不可变 schema；
2. append-only LifecycleEvent；
3. 确定性 event reducer；
4. scope-aware transition validator；
5. invocation policy reducer；
6. evaluator firewall 与 mutation tests；
7. 将 E02-D 小世界作为首个端到端任务；
8. 最后才接入 A1/A2/A3/A4/A5/M2 提议器。

**停止条件：**在正交状态投影、范围隔离、版本冻结和 learner/evaluator 非干扰测试通过前，不应宣称 E12-A6 生命周期闭环已完成，也不应把易象先验接入最终决策层。

本文件是设计提案，不包含实现或实验结果。
