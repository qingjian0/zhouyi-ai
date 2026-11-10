# E02-H CI 实验结果（2026-11-10）

## 执行证据

- GitHub Actions run：`42815124887`
- workflow：`tests`
- job：`unit-tests`
- commit tested by PR merge ref：`01439eefa57f3f3cb53e3c9ad93e4b26b96f879a`
- conclusion：`success`
- E02-H experiment step：completed / success
- E02-H seeds：30，seed range 900–929

完整工作流中的 E01、E02-A 至 E02-G、单元测试及 E02-H 步骤均成功。

## 实验配置

- 8 个二值特征。
- 目标为隐藏三变量非仿射布尔关系，三个变量均为 essential。
- 生成器要求目标函数的最佳任意二变量 Bayes accuracy 不超过 0.75。
- train / gate / locked test：1024 / 512 / 512。
- 标签噪声：2%。
- 候选语言：全部 2- 与 3-特征子集上的完整 truth table。
- 子集数：C(8,2)+C(8,3)=28+56=84。
- 每个二阶子集有 16 张 truth table，每个三阶子集有 256 张 truth table；每轮候选表总数为 14,784。
- 目标成员和目标 truth table 仅用于数据生成与最终审计，不传给 discover。

## 30-seed 结果

| 指标 | 结果 |
|---|---:|
| member recovery | 30/30（100%） |
| exact truth-table recovery | 30/30（100%） |
| CREATE | 30/30（100%） |
| mean independent gate accuracy | 0.9806640625 |
| mean locked test accuracy | 0.9779296875 |
| mean pairwise test accuracy | 0.7240234375 |

以上结果来自 workflow 日志中 E02-H JSON 输出，而不是本地重新估算。

## 结论

在该受约束的合成分布、给定样本量和有限候选语言中，学习器能够同时恢复隐藏成员集合与完整非仿射布尔真值表，并在独立 gate 上优于 exhaustive pairwise truth-table baseline。

## 严格限制

1. 这是 8 特征、二值输入、三阶目标的合成实验。
2. 生成器排除了 pairwise-easy 目标；结果不能代表任意布尔函数分布。
3. 搜索空间被明确限制为 84 个子集和 14,784 张候选表；不是开放式规则生成。
4. 当前候选选择是训练集上的穷举拟合，gate 负责独立验收；不能把这称为通用因果发现。
5. CREATE 率 100% 只说明当前构造任务中 gate 门槛全部通过，不意味着真实环境中应该无条件持久化新关系。
6. 本实验没有验证流式漂移、成员变化、关系替换、长期遗忘或多关系并存。

因此，E02-H 是有限规则空间内的结构与语义恢复证据，不是开放域自主发现完成的证据。
