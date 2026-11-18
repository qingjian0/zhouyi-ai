# CPG-EI 实验结果审计（2026-11-18）

> 本报告只汇总可追溯到 GitHub Actions exact-head 工作流产物的结果。所有结果均限定于对应的有限合成任务；不得外推为自然语言理解、通用推理、因果发现、真实《周易》类象能力或 Transformer 优越性。

## 1. 可复现结果摘要

### 1.1 未见教师族 few-shot 符号基线

**来源**：PR #517 的 exact-head 工作流，提交 `3530160da95a3e65fc1c44325bfc70736498f051`；工作流 Run [44242069962](https://github.com/qingjian0/zhouyi-ai/actions/runs/44242069962)，产物 `zhouyi-cpg-ei-heldout-family-fewshot-v1`（Artifact ID `14399986761`）。

协议要点：

- 每个随机种子生成 1,600 个教师规则族，按族隔离为 meta-train 960、validation 320、locked test 320。
- 3 个独立种子；测试聚合覆盖 960 个 family-seed 测试单元。
- 每个未见测试族分别提供 16/32/64 个有标签 support 状态；query 标签仅由评估器在候选选择完成后读取。
- 候选选择是在固定有限布尔算子语法内做符号枚举，不是学习型 meta-learner；不是 zero-shot。

Locked test 汇总（均值 ± 跨 family-seed 样本标准差）：

| Support 状态数 | 方法 | Bit accuracy | Exact-state accuracy |
|---:|---|---:|---:|
| 16 | 符号候选选择 | 88.86% ± 4.45% | 43.54% ± 15.36% |
| 16 | 同 support 多数类基线 | 78.26% ± 3.89% | 12.57% ± 6.16% |
| 32 | 符号候选选择 | 97.08% ± 1.93% | 80.72% ± 10.57% |
| 32 | 同 support 多数类基线 | 78.59% ± 3.56% | 12.92% ± 6.06% |
| 64 | 符号候选选择 | 99.12% ± 0.83% | 93.47% ± 5.66% |
| 64 | 同 support 多数类基线 | 78.58% ± 3.47% | 12.81% ± 5.94% |

解释：在已声明的有限候选语法、合成布尔关系和给定 support 条件下，符号枚举基线明显优于多数类基线；support 增加时指标提升。该实验没有训练跨族神经 meta-model，不能证明开放世界类象发现或真实领域迁移。

### 1.2 组合算子语法 OOD

**来源**：PR #517 exact-head 提交同上；工作流 Run [44242070018](https://github.com/qingjian0/zhouyi-ai/actions/runs/44242070018)，产物 `zhouyi-cpg-ei-compositional-ood-v1`（Artifact ID `14399717282`）。

协议将教师输出定义为两个合取项的 XOR 组合，而符号候选语法只包含单个声明算子，不包含该组合结构。各方法均在每个 family 自己的训练划分上适配；development 用于选择，locked 仅报告。因此这是**算子语法 OOD**，不是未见教师族 zero-shot。

3 个种子的 locked 指标（均值 ± 样本标准差；每种子 8 个 family、512 行）：

| 方法 | Bit accuracy | Exact-state accuracy |
|---|---:|---:|
| 符号基线 | 68.95% ± 0.59% | 32.29% ± 5.92% |
| Full polynomial learner | 46.68% ± 3.99% | 14.06% ± 2.34% |
| Symbolic-support hybrid | 56.84% ± 1.79% | 11.98% ± 0.90% |

解释：当前三种方法在该组合语法 OOD 任务上均未达到高准确率。符号基线在这组有限设置中优于两个学习型对照，但仍有明显错误；这不能作为模型总体能力排名，也不能据此推断神经方法普遍较弱。下一轮应检查候选语法覆盖、组合深度、support 数量和数据生成机制，并加入参数量/计算预算匹配的更强基线。

### 1.3 混合算子发现基线

**来源**：PR #517 exact-head；工作流 Run [44242070004](https://github.com/qingjian0/zhouyi-ai/actions/runs/44242070004)，产物 `zhouyi-cpg-ei-mixed-operator-discovery-v1`（Artifact ID `14400740292`）。

- 400 个教师族，分层为 train 240、development 80、locked 80；每族 8 个输出。
- 候选假设 3,864 个；其中 3,388 个不同真值函数、476 个结构别名。
- 候选选择规则：最小训练误差；训练并列时由 development 误差打破平局；locked 标签仅用于报告。
- locked 共 80 个 family / 640 个输出。

| 指标 | Locked 结果 |
|---|---:|
| 平均 bit accuracy | 99.9707% |
| 完整真值表 exact rate | 99.5313% |
| 语义函数恢复率 | 99.5313% |
| 算子恢复率 | 92.0313% |
| 精确规则恢复率 | 91.5625% |
| 教师函数可识别率 | 63.7500% |
| 在可识别子集上的算子恢复率 | 100.0000% |

解释：这证明有限候选空间内的穷举符号基线能恢复大部分合成规则。语义函数恢复、算子恢复和结构规则恢复是不同指标；当教师函数本身存在结构等价别名时，不能要求唯一恢复其原始写法。该结果不是神经网络训练结果，也不是开放域关系发现结果。

### 1.4 扩展混合算子语料 v2

**来源**：PR #520 exact-head；工作流 Run [44243081847](https://github.com/qingjian0/zhouyi-ai/actions/runs/44243081847)，产物 `zhouyi-cpg-ei-expanded-mixed-operators-v2`（Artifact ID `14400283200`）。

- 1,600 个独立教师族；每族 8 个输入、8 个输出、256 个完整布尔状态。
- 总计 409,600 行、12,800 条教师规则。
- 相对 v1 的 400 个参考教师族，独立教师族数量扩大 4 倍。
- 语料 SHA-256：`ce5b87c0d6c2b42f058fc9ef22ea9d2f0f2df274db34470941d627de7795459b`。

**重要边界**：这是数据集扩容与生成完整性产物，不是模型训练成绩。必须在该语料上完成预注册的训练、验证、锁定测试和独立种子复现后，才能报告学习能力或跨族迁移结论。

### 1.5 经验贝叶斯未见教师族 few-shot 基线

**来源**：PR #528 exact-head 提交 c5589a299093f459622623ed6b2be730c8ac5513；工作流 Run [44268759812](https://github.com/qingjian0/zhouyi-ai/actions/runs/44268759812)，产物 zhouyi-cpg-ei-empirical-bayes-meta-v1（Artifact ID 14412082613）。

- 每个种子 1,600 个教师族，按族隔离为 meta-train 960、validation 320、locked test 320。
- 3 个独立种子：20261114、20261115、20261116；输入/输出各 8 维，每族 256 个完整状态。
- 固定候选语法包含 3,864 个规则假设；验证集选择的先验强度在三个种子、三种 support 规模下均为 alpha=0.01。
- 下表为三个种子 locked-test family 平均值再做等权平均；不是把不同 support 规模混合计算。

| Support 状态数 | Empirical-Bayes bit accuracy | 多数类 bit accuracy | Empirical-Bayes exact-state | 多数类 exact-state |
|---:|---:|---:|---:|---:|
| 16 | 92.60% | 78.26% | 57.34% | 12.57% |
| 32 | 98.55% | 78.59% | 89.44% | 12.92% |
| 64 | 99.51% | 78.58% | 96.27% | 12.81% |

解释：在这个有限布尔规则语法与合成教师族分布中，meta-train 估计的经验贝叶斯规则先验，在锁定测试族上优于 alpha=0 支持集基线与多数类基线；support 增加时表现继续提升。它是**符号经验贝叶斯 few-shot 基线**，不是神经 meta-model、开放规则发现或真实类象迁移证据。完整逐族结果、语料摘要和 prior 摘要保存在工作流产物中。

## 2. 本轮工程验证状态

截至 2026-11-18 09:04 UTC：

- **已合并到 dev**：#519（N0.10 out-of-core）、#520（扩展语料 v2）、#521（历史审计标记）、#523（M1 Manifest / bounded reads）、#524（M2 lazy store / paging）、#526（CPG-EI workflow path filters）、#527（本结果审计）、#528（经验贝叶斯 few-shot 基线）。以上均采用 squash merge；main 未改动。
- **#517 待验收**：专项 CPG-EI 工作流已通过。首轮 full-validation 发现研究分支工作流缺少 NumPy；补入后，第二轮又确认向量化与标量回退路径的特征编码计数口径不同（128 对 1536）。测试现已按实际后端分别核验，最新 full-validation Run [44272993658](https://github.com/qingjian0/zhouyi-ai/actions/runs/44272993658) 正在执行；未合并。
- **#518 待依赖重整**：类象关系保持 OOD 专项工作流成功，但其分支基于 #517 的旧提交；旧提交的 full-validation 同样受到上述依赖/断言问题影响。需在 #517 通过后将 #518 与最新基线重新衔接，再做完整验证。
- #519、#520、#523、#524 的精确提交均有完整测试与相关专项工作流成功记录；#526 的精确提交通过通用 tests 与 Orchestrator tests（2 项）。
- dev 集成后的整仓验证已通过 push 触发：tests Run [44273325406](https://github.com/qingjian0/zhouyi-ai/actions/runs/44273325406) 与 Orchestrator tests Run [44273325588](https://github.com/qingjian0/zhouyi-ai/actions/runs/44273325588) 当前排队执行。

工作流成功仅代表对应自动化检查通过。合成基准不等同真实古籍 Gold 数据或现实任务效能；Draft/未验收 PR 不视为已发布功能。

## 3. 下一轮实验门禁

1. **跨族学习**：现已实现经验贝叶斯符号规则先验，并在 3 个种子、3 种 support 规模的 locked test 上优于 alpha=0 基线；下一步仍需扩展到可学习的神经/非有限语法 meta-learner，并做更强基线与分布迁移验证。
2. **组合 OOD**：扩大组合深度与算子组合；加入更强的 MLP/神经符号基线，严格隔离规则模板、教师族与随机种子。
3. **语义可识别性**：持续分别报告 truth-function、operator、exact-rule 三层恢复率，不把结构别名误记为学习失败或成功。
4. **易象独立贡献**：在相同任务、参数量和计算预算下，对比无先验、随机编码、可学习编码、结构编码及传统关系先验；先完成独立 Gold 语料与校勘，再进入真实类象效益评估。
5. **资源审计**：所有大规模实验绑定数据摘要、代码 commit、种子、环境、训练预算、峰值 RSS、耗时和失败案例。
6. **报告更新**：任何后续结果必须由 exact-head 产物生成；旧提交的成功记录不能替代新提交验证。

## 4. 结论

截至本报告所覆盖的实验，Zhouyi-AI 已拥有有限语法符号搜索、经验贝叶斯跨族先验、组合算子 OOD 诊断、未见教师族 few-shot 评估和扩展合成语料。**尚未证明完整 CPG-EI 模型在真实类象任务、自然语言任务或公平的强基线对照中取得优势。** 当前最重要的科学缺口仍是更广泛的跨族学习、严格组合 OOD、真实 Gold 类象数据和易象先验消融。
