# N0.10 高阶必要性基准：三元奇偶关系

状态：新增可执行诊断基准；当前头完整 CI 已通过。  
代码：`prototype/n10_higher_order_benchmark.py`  
测试：`tests/test_n10_higher_order_benchmark.py`

## 1. 研究问题

现有 N0.10 训练样本给每个角色的正确节点植入明显单点特征，unary 检索就可能完成任务。因此，虽然模型实现了 pairwise/triple 特征，但旧任务不能证明第三阶交互是必要的。

本基准刻意构造一个三元奇偶任务：

`y = 1[x_0 x_1 x_2 = +1]`

其中三个角色的特征取值于 `{-1,+1}`。数据按 8 种完整因子组合分周期采样，并在周期内随机打乱，因此每个数据集都精确平衡；标签与任何单一角色特征、任何二元乘积都正交，只有三元乘积携带标签信息。

## 2. 对照

使用相同数据、初始化、优化器、训练步数和评估样本，分别训练：

- Unary-only：仅保留角色一元特征；
- Unary + pairwise：增加全部二元逐维交互；
- Unary + pairwise + triple：增加三元逐维交互。

第三阶模型另做一次归因干预：推理时只屏蔽 triple 特征块，保留已训练的 unary 和 pairwise 权重。若准确率退回机会水平，说明在这个受控任务上预测依赖第三阶特征块。

参数数量（feature_dim=1、3 个角色）：unary 3；unary+pairwise 6；完整三阶 7。该对照不是等参数量模型比较，后续仍需补充容量匹配的 MLP/Set/Graph 基线。

## 3. 默认复现实验

```bash
python -m unittest tests.test_n10_higher_order_benchmark -v
python -m prototype.n10_higher_order_benchmark --seeds 5 --start-seed 7 --train-samples 3000 --test-samples 1504 --epochs 120 --json
```

CI 将对五个种子执行正式样本规模运行，并保存 JSON Artifact。报告的准确率阈值只用于验证基准构造和实现是否按预期工作，不构成真实世界能力门槛。

## 4. 解释边界

- 这是已知规则的合成 IID 机制诊断，不是规则族 OOD。
- 它证明的是该显式三阶特征模型能拟合三元奇偶信号，而低阶特征在此分布下缺少标签信息。
- 它不证明开放域高阶推理、语义理解、因果发现、易象先验有效或 CPG-EI 优于 Transformer/GNN。
- 需要继续做保留二元投影的结构扰动、对象/规则族 OOD、参数与计算预算匹配对照。


## CI 验收记录

- Exact head: `8dd89ab73ea798635c18f6432a60afbcf736834a`
- Workflow run: https://github.com/qingjian0/zhouyi-ai/actions/runs/43094303391
- 全仓库单测通过；五种子 parity 基准步骤通过；JSON Artifact `n10-higher-order-results` 已生成。
- CI 检查：完整三阶模型平均准确率不低于 0.95；低阶模型与三阶模型屏蔽 triple 后的平均准确率均在 0.40–0.60。
- 这是一组预设实现验收阈值，不是独立领域泛化或模型优越性结论。
