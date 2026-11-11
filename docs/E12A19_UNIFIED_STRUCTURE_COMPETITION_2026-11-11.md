# E12-A19：统一结构竞争与公平比较协议

日期：2026-11-11  
状态：研究协议与实现阶段；尚无结构优胜结论

## 1. 研究问题

E12-A16、A17、A18 分别提出稀疏属性合取、类型化有向路径、分叉/汇合结构。它们目前各自使用不同的候选枚举、复杂度近似、支持度门槛与排序规则。直接比较各自的 MDL 分数是不成立的：不同原型的码长定义不同，分数尺度并不共享同一编码模型。

A19 的目标不是立即选出“最强结构”，而是建立统一的结构候选竞争协议，使候选家族在同一数据划分、同一预测损失、同一支持度定义和可核算搜索预算下接受比较。

## 2. 统一输入表示

每条样本包含：
- 稳定 observation_id；
- 原子属性集合 atoms；
- 类型化节点 nodes；
- 有向关系 edges（含可选 transition label）；
- 分类 outcome。

三种候选家族共享同一 observation，但只读取其声明所需的视图：
- SPARSE_CONJUNCTION：只读 atoms；
- TYPED_PATH：只读 nodes/edges；
- FORK_JOIN：只读 nodes/edges。

禁止候选家族读取 outcome 之外的隐藏生成器信息、测试标签、evaluator receipt 或其他候选家族的内部状态。

## 3. 统一候选接口

每个候选必须提供：
- family、canonical candidate key、grammar version；
- 对样本的确定性 match predicate；
- 从训练样本估计的 outcome likelihood；
- 支持度、训练数据摘要、训练 ID manifest；
- 结构编码成本的原始组成项，而非伪装成可直接比较的统一 MDL 分数。

A16/A17/A18 的现有 discover 函数是提案器，不是最终裁判。适配器必须将 validation_fraction 设为 0，让提案只由训练数据产生；验证集不得参与候选生成、候选筛选或排序。统一 evaluator 在提案冻结后计算所有候选的 held-out 指标。

## 4. 数据划分与泄漏防护

- 数据划分由显式 SplitManifest 提供，记录 train_ids、validation_ids、locked_test_ids 和 manifest digest。
- 三个集合必须两两不相交，且覆盖预先声明的数据总体。
- 同一个 manifest 必须供所有候选家族使用；不允许每个 family 自行按 ID 排序切分。
- A19 学习器只获得 train 与 validation 的公开数据；locked test gold labels 由独立 evaluator 保管，遵循 E12-A8 firewall。
- 候选集合和预测提交冻结后，evaluator 才可解封 locked test 标签。
- 不允许在 locked test 上调阈值、选家族、选特征、调参或重新定义语法。

当前 A16/A17/A18 提案器内部仍自行切分，因此 A19 适配器必须在训练子集上调用，并将其内部 validation_fraction 设为 0。正式集成前应将提案 API 重构为显式 train-only 输入，避免重复 split 和 ID 操纵。

## 5. 统一预测评估

对每个候选，使用相同的 categorical likelihood 估计器：
- outcome vocabulary 固定为训练集公开类别；
- Laplace alpha 固定；
- 条件概率仅由训练集内匹配样本估计；
- 未匹配样本回退到训练集全局先验；
- 统一计算 validation/test log loss、accuracy、Brier score；
- 报告 coverage、abstention（若后续家族支持）、calibration 和 per-class 指标。

不能仅报告 accuracy。主要指标预注册为平均 log loss；accuracy 与 Brier 为辅助指标。

## 6. 预算公平性

每个 family 使用同一组预算上限：
- max_generated_candidates；
- max_accepted_candidates；
- max_training_examples_scanned；
- max_feature_or_graph_signature_count；
- wall-clock time 仅作为观测量，不作为唯一预算，因为机器负载与实现语言会影响它。

报告实际消耗：generated/accepted candidate counts、predicate evaluations、训练样本扫描量、结构描述长度分项、运行时间和内存峰值（若可测）。当某家族无法在同一候选预算下完成搜索时，必须标记 truncated，不能将其候选缺失解释为结构无效。

结构复杂度不能直接用 A16/A17/A18 的历史 MDL gain 排名。A19 分开报告：
1. 统一预测质量；
2. family-specific structural code length；
3. 统一的可执行搜索成本；
4. 预测质量—复杂度 Pareto frontier。

若未来需要单一总分，必须先定义共享的 prefix code / universal code，并验证其编码完整性，不能把几个近似复杂度数字简单相加。

## 7. 对照组与易象语法

最低对照组：
- GLOBAL_PRIOR：仅训练集 outcome 先验；
- RANDOM_GRAMMAR：同规模随机候选结构；
- PERMUTED_LABEL_GRAMMAR：保持结构数量/复杂度但置换语义标签；
- FAMILY_ABLATION：分别去掉 atoms、关系方向、transition labels、fork/join 臂信息。

易象候选语法作为可替换 grammar adapter：
- 阴阳二态；
- 四象四态；
- 八卦八状态；
- 六十四卦状态与卦变；
- 太玄三分状态。

这些语法不得作为 gold label。必须与 generic grammar、random grammar、permuted grammar 在相同 split 与预算下比较；节点/状态编码的映射必须公开、版本化、可逆或明确说明有损性。

## 8. 稳定性与统计检验

- 使用成对随机种子与同一 split manifest；
- 报告每个 seed 的差值，不只报告均值；
- 对主指标报告置信区间；
- 多家族、多候选比较需控制多重比较或采用预注册的层级检验；
- 做 observation order、node renaming、edge ordering 的不变性测试；
- 做组合 OOD、关系 OOD、状态 OOD 与跨语法 OOD；
- validation 仅用于预先规定的模型选择；最终结论以锁定测试为准。

## 9. A19 的交付边界

A19 只负责候选提案、统一适配、预算审计与比较报告：
- 不修改 E12-A7 的 epistemic status；
- 不签发 E12-A10 evaluator receipt；
- 不把 validation 表现称为泛化定论；
- 不宣称 CPG-EI 已优于 Transformer；
- 不宣称传统易象语法具有先验正确性。

## 10. 验收标准

1. 同一 manifest 被所有家族复用，且 split 泄漏测试通过。
2. 候选提案阶段无法访问 validation/locked-test labels。
3. 所有 family 通过同一 likelihood evaluator 与指标实现。
4. 预算截断可检测、可复现，候选顺序不影响结果。
5. 随机/置换语法对照可运行。
6. 对相同数据的行序重排和图节点重命名不改变 canonical candidate identities（在语义不变条件下）。
7. 结果报告包含限制、失败候选与预算耗尽信息。

A19 完成协议与软件测试，不等于完成大规模模型训练，也不等于获得性能优势。

## 11. 首版实现范围与未完成项

首版原型已实现三类训练集候选提案器、共享 categorical likelihood evaluator、统一 validation log loss/accuracy/Brier、显式 split manifest、locked-test ID 隔离、候选数量预算与谓词评估预算。

首版仍有以下明确缺口，不能把 A19 首版称为完整验收：
- 当前每个 family 只比较单个候选谓词，不是多规则集成模型，也不是完整的结构组合搜索。
- 当前随机语法与置换标签语法尚未接入可执行 runner；它们仍是下一子阶段的必需对照。
- 复杂度字段只是 canonical JSON 字节数换算的代理值，不是经过证明的 prefix-free universal code。
- 当前预算尚未覆盖所有特征提取开销、候选接受数上限和峰值内存。
- 当前验证集评估器在同一进程内执行；locked-test 真正的进程隔离与签名评估仍由 E12-A8/A10 系统负责，A19 不得绕过它们。
- 当前未实现多随机种子汇总、置信区间、多重比较校正、OOD split 套件或正式 locked-test 解封流程。

因此，首版仅证明三类结构能够进入同一个可复现的候选评估接口。任何家族的 validation 优势都只是探索性结果，不能据此宣布胜出。

## 12. A19-B：惰性候选生成与共享特征缓存

A19-B 修正了首版搜索预算的一个重要缺陷：首版先构造完整候选全集，再按 max_candidates_per_family 截断，因此候选数量预算没有约束候选生成内存和枚举成本。

当前实现改为：
- 稀疏合取使用惰性组合迭代器；
- 路径与分叉/汇合签名按训练集特征提取后确定性排序；
- 每个 family 最多物化 max_candidates_per_family + 1 个候选，额外的一个只用于判断是否截断；
- generated_candidate_count 表示本轮实际物化的候选数，若候选空间未耗尽则它是下界，不再伪装成完整全集大小；
- candidate_space_exhausted 显式区分搜索自然结束与预算截断。

图结构特征现在对每条 train/validation observation 只提取一次，之后候选匹配使用缓存的 frozenset membership，不再为每个候选重复 DFS 或遍历边。所有 family 共享同一份 feature index，feature_signatures_indexed 记录实际索引规模。

新增 max_feature_signatures 硬预算。特征索引超限时 fail closed 并返回明确错误，不会静默丢弃结构特征或让不同 family 获得不公平的特征子集。predicate evaluation budget 继续按候选完整扫描 train + validation 所需的谓词检查次数预留；若预算不足则不启动该候选。

A19-B 仍未解决的事项：
- graph signature union/sort 本身仍需持有训练集观察到的不同签名集合；max_feature_signatures 限制其总规模，但不是外部排序算法。
- 单个候选只用一条规则；多规则联合、随机语法、置换标签语法仍在后续阶段。
- feature cache 以 observation_id 索引，输入 ID 唯一性检查是其安全前提。
- 当前复杂度仍是字节数代理，不是通用 prefix code。

本轮新增测试覆盖：候选只物化到预算上限加一个哨兵、feature cache 被三个 family 共享、特征预算超限时 fail closed。
