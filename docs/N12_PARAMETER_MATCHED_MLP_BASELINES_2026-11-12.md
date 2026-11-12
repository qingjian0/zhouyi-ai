# N0.12：参数预算匹配的 MLP 对照

**状态：已加入可执行基准与单元测试，等待 CI 和正式五种子结果。**

## 研究问题

N0.11 的 SROK 使用 35 个参数，但输入特征已经显式包含三阶 Fourier 张量分解。下一步必须回答：优势来自三阶关系组合结构，还是只因为 SROK 拥有一个手工构造的高阶特征基？

N0.12 在完全相同的 N0.11 train / validation / held-out phase test split 上加入普通 tanh MLP。MLP 只接收相同的信息量：三个角色各自的 sin/cos，共 6 个输入，不直接接收显式三阶乘积。

## 参数预算

| 模型 | 参数量 | 目的 |
|---|---:|---|
| SROK unary+pairwise+triple | 35 | 显式张量组合基线 |
| MLP-4 | 33 | 最接近 SROK 的参数预算 |
| MLP-5 | 41 | 参数量略高的近邻对照 |
| MLP-12 | 97 | 更高容量参照 |

MLP 使用一层 tanh 隐藏层和 sigmoid 二分类输出，训练使用确定性 full-batch Adam。各模型都只允许用训练分布内的 validation 选择 logit 方向；OOD test 不参与模型选择。

## 复现

```bash
python -m unittest tests.test_n12_parameter_matched_baselines -v
python -m prototype.n12_parameter_matched_baselines --seeds 5 --start-seed 7 --train-samples 3000 --validation-samples 750 --test-samples 1500 --epochs 120 --json
```

## 解释边界

- MLP 输入与 SROK 的角色相位信息相同，但不直接获得三阶乘积特征。
- 这是单一小型 tanh MLP 家族，不代表所有 MLP/GNN/Transformer。
- MLP 宽度是预先指定的预算点，不是全面超参数搜索；不能把某个宽度的结果当作整个 MLP 家族上限。
- 参数量接近不等于 FLOPs、内存访问或训练 wall-clock 完全匹配；后续需补充实测资源成本。
- 任务仍是已知解析规则的合成相位 OOD，不代表语义规则学习或自然语言推理。
- 只有在同一数据、验证策略、计算预算和多任务族上反复胜出，才有依据把显式高阶组合设为默认核心结构。
