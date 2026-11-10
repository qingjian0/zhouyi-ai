# Zhouyi-AI 跨研究线审计与下一阶段研究计划

日期：2026-11-11  
范围：仓库当前可见的 main、E01/E02/E03/E04、E09/E10/E11/E12 研究分支及相关开放 PR  
性质：研究审计与路线整合；不是模型能力声明，也不替代各实验的原始报告。

## 0. 执行摘要

项目已从 CPG-EI v0.3 的概念架构推进到多条可运行的符号研究原型。最有价值的进展不是“已经造出新 AI”，而是逐步建立了可审计的机制研究基础：候选生成、Train/Gate/Locked-Test 隔离、反例驱动修正、序贯证据账本、主动观测、有限原语发现和稀疏组合。

当前最大缺口是：这些能力仍分散在不同任务、分支和有限符号语法中，尚未形成一个端到端、可学习、可对照的 CPG-EI 生成/认知系统。

下一阶段不应继续无边界增加实验分支，而应优先建立跨模块接口和统一基准，把“发现原语—验证原语—组合原语—选择观测—更新知识—生成输出”连成闭环。

## 1. 仓库现状与治理结论

### 1.1 main 与研究分支状态

- main 上的 README/ROADMAP 仍保留较早的 M1/M2 阶段描述，不能代表当前全部研究进展。
- 当前研究成果分布在大量隔离分支和 Draft PR 中；必须以具体分支、commit、CI run 和实验报告为准。
- 本审计不修改 main，不合并任何研究 PR。
- 研究 PR 的存在不等于代码已验证；测试文件存在不等于测试执行通过；单元测试通过也不等于模型效果成立。

### 1.2 已核实的关键成果

| 研究线 | 已有成果 | 当前边界 |
|---|---|---|
| E01 | 稀疏选择与组合泛化原型 | 合成任务，不代表自然语言理解 |
| E02 | 高阶关系候选、动态关系生命周期、身份/谱系与多环境实验 | 受限任务和候选空间；需持续防元数据泄漏 |
| E03 | 多关系并行候选与全局预算协调研究 | 必须确保共享预算真正激活，并与独立求解器比较 |
| E04 | 易象结构先验的预注册与状态编码工具 | 先验是否有效仍须消融，不得预设传统映射正确 |
| E09 | Predict→Commit→Reveal→Append 等序贯证据协议 | 部分旧实现仍有 batch-refit 语义；必须区分真正增量更新 |
| E10-A | Support-only 有限机制学习、对象隔离与结构 OOD 研究 | 仍依赖有限属性键/关系符号；不是开放世界感知或因果发现 |
| E11 | 概念层级与稳健生成器方向 | 需独立审计可观测性、概念匹配与层级指标 |
| E12-A1/A2 | 类型谓词、关系谓词、信息增益主动观测与精确 oracle | 有限语法/假设集；oracle 只对声明的有限空间最优 |
| E12-A3 | 多提议器、预算竞争、跨家族去重 | 已得到重要负结果：固定平均分配未胜过专业提议器 |
| E12-A3-M1 | UCB1 分配器组件 | 独立审计指出尚未集成真实提议器、真实成本与增量收益 |
| E12-A4 | 并行原语提议、非连续稀疏组合、证据竞争的架构设计；另有反例触发的有界算子扩展原型 | 架构文档不等于端到端实现；算子扩展不等于开放式发明 |
| E12-M2 | 无监督离散 motif 挖掘与边际保持置换检验 | motif 是统计候选，不是语义原语；OOD、功效、校准和成本仍待验证 |

### 1.3 E12-A3 的正式负结果

E12-A3-M0 在 20 seeds × 2 task families、每个 episode 31 个 proposal slots 的声明协议下，完整工作流通过。选择覆盖率为：

- STAT：15.0%
- RELATIONAL：42.5%
- RANDOM：25.0%
- BOUNDED_ENUM：35.0%
- PORTFOLIO：27.5%

E12-A3-M0.1 对跨提议器表达式去重后，PORTFOLIO 覆盖率降至 17.5%，而 RELATIONAL 仍为 42.5%。这不是“去重本身有害”的证明，而是说明当前队列归属和平均预算分配对候选池结构敏感。

结论：保留去重与来源谱系；停止把固定轮询/平均分配当作默认优选方案。下一步应测试共享候选池、增量组合效用、重复候选信用归因和真实计算成本。

### 1.4 当前验证状态必须保留的限制

- E12-A3-M1 的独立审计指出，现有 UCB 回放使用预生成奖励流，不是真实 proposer 集成基准。
- E12-A4 的并行竞争文档属于架构假设和实验协议，不能称为已训练的非自回归模型。
- E12-A4 反例门控算子扩展、E12-A5 残差诊断、E12-M2.1 等分支需逐一核对最新 CI；不得把“已写测试”报告成“测试通过”。
- E10-A 有界原语扩展只在生成器提供的属性键、关系符号和上下文谓词空间中搜索，不是从原始感知中发现任意新特征。
- 所有有限 oracle 的最优性只对其声明的候选空间成立。

## 2. 架构总审：把系统拆成六个可独立验证的层

建议把 CPG-EI 从当前按实验编号组织的模块，收敛为六层协议。各层可独立替换，避免一个实验同时改变多个变量。

### L0：观测与表征层（Perception / Observation）

输入可来自文本、图像、音频、表格、传感器或环境接口。该层输出带类型和来源的观测记录，而不是直接把原始输入硬编码成“已知概念”。

必须区分：
- 原始观测；
- 可测量属性；
- 模型提出的语义解释；
- 环境/标注方提供的真值。

后续神经编码器应在这一层接入；在此之前，符号实验只能说明下游机制。

### L1：原语提议层（Primitive Proposers）

不同提议器并行产生带类型的候选关系/机制：
- 统计提议器；
- 类型化谓词提议器；
- 关系提议器；
- 反例触发的有界算子扩展；
- 无监督 motif 候选；
- 未来的神经/连续表征提议器。

每个候选必须带有可执行定义、输入类型、适用条件、证据引用、不确定性、复杂度和成本。提议器不能读取 Gate-Final 或 Locked-Test 标签。

### L2：辨识与主动测量层（Identification / Active Measurement）

对当前不可区分的候选，选择能最大程度减少不确定性的观测。E12-A2 的 expected information gain 可作为有限候选基线。

必须区分：
- 被动观测选择；
- 主动测量；
- 真实干预/因果实验。

信息增益高不自动意味着因果识别；动作成本、可执行性和观测噪声必须进入协议。

### L3：稀疏组合层（Sparse Composition）

组合已验证或暂定的原语，构成有类型的 DAG/超图。支持非连续组合，例如 A+C+E，同时显式记录：
- 操作数与角色；
- 关系类型；
- 跳过的位置或成员；
- 深度/复杂度；
- 原语版本与证据谱系；
- 组合状态（proposed / tested / accepted / rejected）。

组合层不得暗中重新发现原语，否则无法区分提议器贡献和组合器贡献。

### L4：竞争、联盟与全局协调层（Competition / Coalition）

候选不是按置信度或投票简单排序。应使用独立 Gate 上的预测收益，并扣除：
- 描述长度/结构复杂度；
- proposal、验证和推理的实际计算成本；
- 与已有候选的重复；
- 跨任务迁移失败风险。

联盟只有在联合 held-out 增益超过额外复杂度与成本时才保留。UCB1 只能作为一个启发式分配基线，必须与 equal allocation、round-robin、successive halving/racing 和小规模 exact allocation oracle 比较。

### L5：序贯学习、记忆与生成层（Learning / Memory / Generation）

通过证据账本执行严格的时序：
Predict → Commit → Reveal → Append → Revise。

必须区分：
- 临时工作记忆更新；
- 结构/原语的增量修订；
- 神经参数训练；
- 批量重新拟合。

生成层输出可以是集合、图、结构化动作或文本。文本 tokenizer/decoder 可以保留为外部接口；若最终 decoder 是自回归，系统应准确称为 hybrid，而不是宣称端到端完全非自回归。

## 3. 外部研究定位与创新边界

已有工作已经覆盖若干邻近思想，项目不能把单项技术重新命名为原创：

1. CoCoMix（ICLR 2026）将连续概念预测与 token hidden representations 交错结合，说明“概念级表示辅助语言模型”已有直接研究。CPG-EI 的差异不能只写成使用 concept，而应检验动态原语生命周期、非连续结构组合、证据门控与结构级生成是否有独立贡献。
2. C³（NeurIPS 2025）研究 comparison→latent concept discovery→composition，并给出特定可辨识条件和视觉未见类别结果。CPG-EI 需要明确自己的可辨识条件、任务域和结构演化机制，不能宣称首次提出比较与组合式认知。
3. 终身学习与功能组合的综述已指出持续学习与组合式知识复用之间的联系。CPG-EI 的贡献应落实到可复现的原语提议、证据验证、组合复用与抗遗忘协议，而不是笼统宣称把两者结合。

参考：
- Microsoft Research, “LLM Pretraining with Continuous Concepts” (ICLR 2026): https://www.microsoft.com/en-us/research/publication/llm-pretraining-with-continuous-concepts/
- Fu et al., “From Comparison to Composition” (NeurIPS 2025): https://openreview.net/forum?id=eF2lcYSF0V
- Mendez-Mendez & Eaton, “How to Reuse and Compose Knowledge for a Lifetime of Tasks” (TMLR 2023): https://arxiv.org/abs/2207.07730

## 4. 下一阶段研究优先级

### P0：跨分支协议与接口冻结

先建立统一的 Candidate / Evidence / Cost / Composition / Prediction / Revision 数据契约。将每个候选绑定：
- immutable candidate_id 和 canonical expression；
- proposer family 与全部 supporting_families；
- Train/Gate-Dev/Gate-Final/Locked-Test split role；
- source observation IDs；
- proposal/evaluation/inference cost；
- model / grammar / generator version；
- prediction、abstention 和 revision 状态。

这是后续集成的前置条件。不要先把所有分支合并成一个巨大模块。

### P1：真实提议器集成的自适应预算实验

以 E12-A3 M0/M0.1 为基线，构建真实 episode runner：
1. 同一 Support snapshot 输入多个 proposer；
2. canonicalize 并保留多源谱系；
3. 统一计算 proposal 与 evaluation 成本；
4. 在 Gate-Dev 上计算候选的增量组合效用，而非绝对分数；
5. allocator 根据历史 Gate-Dev 反馈分配下一批预算；
6. 冻结 allocator 后才允许 Gate-Final；
7. Locked-Test 只由 evaluator 运行一次。

比较 equal、round-robin、UCB1、racing/successive-halving、novelty-aware 和 tiny exact oracle。增加任务分布漂移、奖励非平稳、候选重复、强弱提议器混合和预算不足条件。

### P2：原语发现与稀疏组合的正交实验

将 E12-A3 proposer 与 E12-A4 composition engine 分开测试，再做完整 2×2 因子实验：
- 单一 proposer / 多 proposer；
- 无组合 / 稀疏组合。

另加 dense composition、随机组合、局部邻接组合、精确 oracle。测试集应分别留出：
- 已知原语的新组合；
- 新关系实例；
- 未见 gap length / position pattern；
- 新任务族；
- 观察等价的不可辨识情况。

这能回答增益来自“更多候选”还是“更好的组合”。

### P3：从符号基线迈向可学习表征

只在 P1/P2 通过后，引入小型神经编码器。先从结构化观测开始，再扩展文本/视觉。至少比较：
- 固定手工特征；
- 学习型连续表示；
- 统计/符号 proposer；
- 神经 proposer；
- 神经与符号混合 proposer。

所有方案匹配参数量、数据、调参预算和实测计算成本。神经编码器的输出必须经过同一候选与证据协议，避免额外标签泄漏。

### P4：易象先验的独立因果贡献检验

易象模块不应直接作为硬编码语义标签。把阴阳互补、四象/八卦分层、卦变/状态转移、五行关系拆成独立因素，并比较：
- 无先验；
- 可学习随机初始化；
- 传统结构初始化；
- 映射打乱；
- 反向/错配先验；
- 训练数据学习出的先验。

在 aligned、misaligned、anti-aligned、distribution-shift 和 observational-equivalence 任务中分别评估准确率、校准、拒绝率、样本效率与计算成本。若传统先验在错配环境导致过度自信，应视为真实失败结果。

## 5. 统一验收标准

任何模块只有满足以下条件才能升级研究状态：

1. 代码 commit、数据版本、环境、种子和完整配置可追溯。
2. Train、Gate-Dev、Gate-Final、Locked-Test 的权限边界由代码执行，而非仅靠文档约定。
3. 至少多种子重复；报告均值、离散程度和适当置信区间。
4. 与简单、强且预算匹配的基线比较。
5. 报告 coverage 与 selective accuracy，不能把 abstention 排除后只报高准确率。
6. 报告真实 proposal/evaluation/inference 成本，不能只匹配候选槽位。
7. 包含负对照、泄漏攻击、OOD 和反例。
8. 失败结果必须保留，不能因不利结果改变主指标或筛选种子。
9. 任何“非自回归”声明都报告输出依赖深度、串行阶段、端到端延迟和 decoder 类型。
10. 任何“易象有效”声明都必须通过预注册消融和错配先验测试。

## 6. 当前建议的决策

- 保留 CPG-EI 作为研究总架构，不把它描述成已经成立的新模型。
- 保留 E12-A3 的负结果，暂不把 UCB1 定为默认分配器。
- E12-A4 先做机制分离和正交基准，不急于扩大网络规模。
- E10-A 的 bounded primitive expansion 作为有界机制学习基线，不命名为 open-world discovery。
- E12-M2 motif 只作为无监督统计候选来源，必须经过独立验证才能进入原语库。
- E09 evidence ledger 作为跨实验基础设施优先统一。
- main 保持不动；本文件只作为研究分支上的跨线审计与后续计划。

## 7. 本文件的状态

- [事实] 仓库 README、理论、架构、实验文档及列出的 PR/实验记录中明确存在的内容。
- [结果] E12-A3-M0/M0.1 报告中记录的结果与 CI 状态。
- [审计] E12-A3-M1 独立静态审计中记录的问题。
- [建议] 本文提出的六层架构、P0-P4 优先级与统一验收协议。
- [假设] 上述整合路线能够降低跨分支重复劳动，并让局部机制的贡献可辨识；仍需实际集成实验验证。
