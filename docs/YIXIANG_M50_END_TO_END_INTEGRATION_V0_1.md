# M50：类象因果实验端到端集成 v0.1

## 目标与范围

M50 首次把 M45–M49 的事件账本、持久总体 SCM、统一指标/基线、配对消融和复现清单接入同一条可执行实验路径。它验证的是研究基础设施是否真正连通，而不是宣称类象理论或完整 Zhouyi-AI 已经完成。

## 实验设计

- 合成线性连续 SCM：共同原因 q 同时影响 a 与 c；目标 y 的直接父节点为 a、b；c 与 y 可因混杂而产生观察相关，但 do(c) 不改变 y。
- 每个 episode 使用固定总体单位；同一单位的外生噪声在观察与干预间复用。
- 干预适配器对候选 a、b、c 分别执行 do(x=0) 与 do(x=1)，以配对总体均值差估计干预效应，并选择效应绝对值最大的两个候选。
- 对照包括 seeded random intervention 与 observational correlation screening。后者只是相关性启发式，不是因果发现算法。
- evaluator 在所有 agent-facing 结果产生后读取 oracle 真值并计算直接父节点指标；oracle 信息不进入候选选择器或 baseline output。
- 每个 episode 写入 action、observation、policy_decision、final_claim 事件；M48 对 intervention adapter 与 observational ablation 进行同 episode 配对比较；M49 登记配置、seed、split family、摘要工件引用及账本摘要。

## 验收边界

可由 CI 验证：端到端执行、账本 hash chain、配对消融有效性、manifest 完整性、seed 确定性、oracle 隔离、预算与指标路径。

不能由本轮推出：真实 LLM/Agent 性能、类象理论优于 Transformer、跨 SCM 家族泛化、非线性/离散/隐藏变量机制适用性、外部数据集复现、持久化账本或真实工件存储。当前 intervention adapter 是手写算法适配器，不是大语言模型。

## 复现

```bash
python -m unittest tests.test_yixiang_end_to_end_m50 -v
python -c "from prototype.yixiang_end_to_end_m50 import run_benchmark; r=run_benchmark(); print(r['summaries']); print(r['paired_ablation'])"
```

默认 5 个 episode、seed 从 7 开始。当前 manifest 中 artifact URI 为内存占位符，episode split 全部登记为 test；它是运行清单审计，不是训练/验证/测试模型评估设计。

## 与传统类象理论的关系

M50 只把“同异需察其所以然”“不可偏观”等古典辨析原则转译为实验约束：观察相关与干预效应分开、直接父节点与祖先区分、主张必须绑定证据轨迹。它不把《墨子·小取》或《荀子·正名》追溯性解释成现代 SCM、随机试验或 bootstrap 理论。
