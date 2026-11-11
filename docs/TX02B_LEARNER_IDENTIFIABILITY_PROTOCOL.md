# TX-02B：跨 Episode 可训练学习器与可辨识性协议

状态：TX-02B-1 精确可辨识性审计器已实现并通过 CI；TX-02B 可训练学习器尚未实现，尚无性能结果。
关联：TX-02A、TX-02B-0、E02-B、E02-D。

## 1. 本轮代码审计结论

仓库已有 `prototype/e02_ternary_learners.py`，但它不是 TX-02B 的有效替代实现：

- 任务固定为单一的三值模 3 加法关系 `(a+b+c) mod 3 == 0`。
- 训练、验证、测试集都会重复覆盖相同的九种 `(a,b)` 查询；它们是不同采样顺序/候选顺序，不是未见规则 episode。
- 二阶模型有 36 个参数，三阶模型有 63 个参数；模型容量不匹配。
- 验证集门控只能在这一个固定任务中比较模型阶数，不能证明自主状态基数选择。
- 该实验仍有价值：它是 E02-B 固定规则、三值有限域关系的诊断基线。应保留原实验及其历史结果，不应把它改名或包装成 TX-02B。

TX-02B 必须直接消费 TX-02A 的 episode 协议，并在 episode 之间切分规则实例。

## 2. 首要问题：任务是否可辨识

TX-02A 的隐藏规则为：

\[
c=(\alpha a+\beta b+\delta)\bmod K
\]

可见符号还可能经过 episode 独立随机双射。仅有少量 support 样本时，可能存在多个隐藏规则/符号映射同时解释全部 support，却对 query 给出不同答案。

因此，不能假设每个 episode 都能由给定 support 唯一恢复。训练任何模型前，先建立**可辨识性审计**：

1. 对每个 episode 枚举符合任务定义的候选假设（至少覆盖所有系数；在 permuted 条件下还需覆盖合法符号映射）。
2. 保留所有与 support 完全一致的假设。
3. 对每个 query 统计候选答案的后验频数。
4. 记录 posterior ambiguity、Bayes-optimal query accuracy 和可辨识 query 比例。
5. 将模型错误拆分为：信息论/任务歧义、表示损失、优化失败、泛化失败。

如果 exact enumeration 成本过高，先对小 K 做精确审计，再对较大 K 使用明确标注的采样近似；不得把近似结果称为精确 Bayes 上界。

## 3. TX-02B-1 已实现：精确可辨识性审计

实现：`prototype/tx02_identifiability.py`；测试：`tests/test_tx02_identifiability.py`。

- canonical：枚举 K³ 个仿射系数假设，固定恒等符号映射。
- permuted：枚举 K³ 个系数与 K! 个潜在到可见符号双射。
- 对每个假设检查 support 是否全部一致；对每个 query 累计各候选答案的假设计数。
- 输出规则假设数、规则唯一性、逐 query 后验、答案熵、Bayes-optimal accuracy 和 query 可辨识率。
- 不读取 `hidden_rule`、`visible_symbols` 或 `targets`；目标标签仅可由外部 evaluator 用于核验。
- 设置 `max_hypotheses` 上限，超过时明确报错，不会悄悄切换成近似算法。

**概率解释边界：** 当前 posterior 是在 TX-02A 生成器的仿射规则族内，对系数和允许的符号双射采用均匀先验所得。它不是对所有可能函数的无先验 Bayes 上界。规则假设可能多于一个，但只要某 query 的所有一致假设都给出同一答案，该 query 仍可辨识。

运行示例：

```bash
python -m prototype.tx02_identifiability --cardinality 3 --support-size 2 --query-count 2 --symbol-mapping permuted
python -m unittest tests.test_tx02_identifiability -v
```

## 4. 数据协议修订要求

### 4.1 分割单位

- 以完整 episode 为最小分割单位。
- train / validation / locked-test 使用互不相交的 episode seeds。
- 增加 rule-family split：锁定测试集中的系数组合不得出现在训练集。
- canonical 与 permuted 分层报告，不得混合后只报一个总分。
- 每个 K 独立报告；K=2、3、4、5 不得只汇总平均值。

### 4.2 Support 难度扫描

不能只使用 support_size=2。至少扫描：

- 极少证据：2；
- 低证据：4；
- 中等证据：8；
- 高证据：接近 K²，但保留至少一个未见 query pair。

每个配置必须检查 support/query 输入对无交集，并记录有效 episode 数、无效/歧义 episode 比例。对每个 K，support_size 必须严格小于 K²。

### 4.3 规则覆盖

当前生成器从 Z_K 中独立采样 alpha、beta、delta。对复合 K，系数不一定可逆；alpha 或 beta 为零也可能产生退化关系。实验应分层标注：

- 可逆/单位系数与非单位系数；
- 非退化与退化规则；
- 规则系数的训练/验证/测试覆盖。

不得静默删除困难规则。若增加受限规则子集，必须作为独立任务条件报告。

## 5. TX-02B 学习器比较矩阵

先实现可复现、低依赖的基线，再考虑深度模型：

1. **Uniform / Majority**：无结构下限基线。
2. **Exact-Hypothesis Posterior**：在可计算的小 K 上枚举候选规则，给出可辨识性与 Bayes 基准；这是推断基准，不应冒称神经学习器。
3. **One-hot learned baseline**：类别身份无几何假设。
4. **Binary code learner**：使用 TX-02B-0 的 BINARY 编码。
5. **Ternary code learner**：使用 TERNARY 编码。
6. **Hybrid code learner**：使用 HYBRID 编码。
7. **Learned embedding learner**：嵌入参数必须由训练目标更新；LEARNED_INIT 不能被当作训练完成。
8. **Permuted-code control**：使用 PERMUTED 编码，控制收益是否来自特定符号编号/几何对齐。

每个可训练模型必须实现同一接口：`fit(train_episodes, validation_episodes, budget, seed)`、`predict(episode)`、`state_dict()/metadata()`。推理时只能读取 learner-visible episode 字段，不能读取 `hidden_rule`、`visible_symbols` 或任何 evaluator-only 元数据。

## 6. 公平比较

- 首选统一训练样本、优化器更新次数、早停规则和硬件环境。
- 同时报告参数量、训练步数、运行时间、峰值内存；可测时报告 FLOPs。
- 由于编码维度不同，不能只说“训练步数相同”就宣称计算预算完全相同。
- 同时提供 parameter-matched 与 compute-matched 两种对照；无法精确匹配的差异必须公开。
- 所有随机性拆分为 episode seed、初始化 seed、训练顺序 seed，并逐项记录。
- 超参数只能由 validation 选择；locked-test 在实验方案、模型和阈值锁定后运行一次。

## 7. 评价指标

必须报告：

- query accuracy 与 episode exact-match accuracy；
- posterior ambiguity / Bayes-optimal accuracy；
- identifiable-query accuracy 与 all-query accuracy；
- canonical / permuted 分层准确率；
- 每个 K、每个 support_size、每种规则子类的结果；
- calibration、错误自信率、abstention / defer coverage；
- 达到目标准确率所需 support 数；
- 参数量、更新次数、运行时间、峰值内存；
- 多随机种子均值、标准差及置信区间；
- 失败 episode 的类别和证据摘要。

## 8. 证伪标准

- 若 TERNARY 不优于容量/计算匹配的 ONE_HOT 或 LEARNED，不能声称三值编码有学习优势。
- 若 PERMUTED 与 TERNARY 相当，不能把结果归因于规范三值结构。
- 若优势只出现在 canonical，不出现在 permuted，结论只能是“规范符号对齐提供了归纳偏置”，不能泛化为普遍认知优势。
- 若模型成绩接近 Bayes 上界但上界本身较低，应报告任务证据不足，而非模型能力差。
- 若模型远低于 Bayes 上界，应优先定位表示、优化或学习算法瓶颈。
- 若优势来自更多参数/算力，结论必须限定为资源优势。
- 只在合成有限环任务上成立的结论，不得外推为自然语言理解或通用智能。

## 9. 实施顺序

- TX-02B-1：实现可辨识性审计器与小 K exact posterior 基线。
- TX-02B-2：实现统一 episode learner API 与 one-hot / binary / ternary / hybrid / learned embedding 基线。
- TX-02B-3：完成 canonical / permuted、K、support、规则子类分层实验。
- TX-02C：参数与计算预算匹配、多种子锁定测试。
- TX-02D：在验证集上训练表示选择器，并加入 DEFER / fallback。
- TX-02E：未知 K、非均匀状态划分、噪声和规则族外测试。

**当前结论：** E02-B 是固定三值规则诊断；TX-02B-1 精确审计器及生成器真值覆盖测试已通过 CI run #85（156 tests passed）；TX-02B 可训练学习器尚未实现。下一步进入 support 难度扫描与跨 episode learner。


## 10. TX-02B-2 首批实现：规则族隔离与标签隔离

新增 `prototype/tx02_splits.py` 与 `tests/test_tx02_splits.py`。

- TX-02A `make_episode()` 增加可选的显式 `rule=(alpha,beta,delta)` 参数；不传时保持原随机生成行为。
- 规则族按完整系数三元组分割，train / validation / locked-test 的系数集合互不相交，而不只是 episode seed 不同。
- 每个规则可生成多个 episode，并独立采样 canonical/permuted 映射和 support/query/candidate 顺序。
- 定义 `LearnerInput`，只包含 cardinality、mapping condition、support、queries、candidates；不包含 targets、hidden_rule 或 visible_symbols。
- `SupervisedEpisode` 将训练 targets 与输入对象分开；`EvaluationEpisode` 将验证/锁定测试 targets 放在 evaluator 记录中。模型的 `predict()` 只接收 `LearnerInput`。
- 测试覆盖规则集合互斥、标签/隐藏元数据隔离、固定 seed 可复现、K=2..5 三个 split 非空和非法参数拒绝。

**边界：** 当前 held-out 是 TX-02A 仿射系数三元组的组合留出，不是规则函数族外泛化；同一系数在不同映射下仍属于同一规则组。该协议也尚未自动按单位/非单位系数、退化关系分层汇总。当前实现建立数据边界，不是 learner，也没有性能结果。


## 11. TX-02B-3 首个可训练基线：support-set MLP

新增 `prototype/tx02_learners.py` 与 `tests/test_tx02_learners.py`。

### 模型结构

- 输入是单个 support 三元组 `(s_a,s_b,s_c)`、query `(q_a,q_b)` 和一个候选符号 `c*`。
- 六个符号分别经同一表示表编码，拼接后进入共享两层打分器（一个 tanh 隐层 + 标量输出）。
- 对一个候选，跨全部 support 行的分数取均值；再对候选行做 softmax。
- support 行均值池化使模型对 support 行顺序不敏感；候选顺序仅决定输出索引，不参与候选身份编码。
- 交叉熵梯度更新 MLP。`LEARNED` 模式还会更新符号 embedding 表；BINARY / TERNARY / HYBRID / ONE_HOT / PERMUTED 使用固定 codebook。
- `predict()` 只接收 `LearnerInput`，不接收 episode targets 或隐藏元数据。

### 当前实验边界

- 这是第一个可训练神经基线，不是已调优模型，也没有性能优势结论。
- 当前实现是纯 Python 小型 MLP，适合验证接口、梯度链路与低 K 原型，不适合宣称大规模训练效率。
- `fit()` 当前按 query 顺序执行 SGD；epoch 数是训练预算的一部分。正式对照还需加入显式更新步数/时间预算、批量训练和多种子统计。
- 各编码维度不同，当前同 hidden size 不等于参数量匹配；后续实验必须同时报告参数量并构造 parameter-matched / compute-matched 对照。
- `LEARNED` 与固定编码的差异同时包含可训练 embedding 的自由度；要单独归因 embedding 学习效果，必须增加同维度固定随机 embedding 对照。
- 规则族 holdout 只覆盖 TX-02A 仿射系数三元组，不能称为任意规则 OOD。

### 运行

```bash
python -m unittest tests.test_tx02_learners -v
```

**当前状态：** TX-02B-3 已有统一的最小预测接口和首个可训练 support-set learner；仍需完成端到端训练曲线、support 难度扫描、预算匹配和 locked-test 实验。
