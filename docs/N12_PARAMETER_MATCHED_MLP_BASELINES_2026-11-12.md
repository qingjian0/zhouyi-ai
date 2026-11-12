# N0.12：参数预算匹配的 MLP 对照

**状态：五种子正式基准已通过 N0.12 CI gate，结果 artifact 已生成。**

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

## 五种子结果

正式配置：5 个种子；每个种子 3,000 train / 750 validation / 1,500 held-out-region test；120 epochs。所有模型的 logit 方向只由同分布 validation 选择。

| 模型 | 参数量 | OOD accuracy（均值 ± 样本标准差） |
|---|---:|---:|
| SROK | 35 | **92.41% ± 0.62%** |
| MLP-4 | 33 | 66.55% ± 3.32% |
| MLP-5 | 41 | 73.32% ± 2.75% |
| MLP-12 | 97 | 90.83% ± 1.37% |

本任务下，35 参数 SROK 比最接近预算的 33 参数 MLP-4 高 25.86 个百分点；也比 41 参数 MLP-5 高 19.09 个百分点。97 参数 MLP-12 达到 90.83%，与 SROK 接近，但参数量约为 SROK 的 2.77 倍。

**不能据此宣称 SROK 普遍优于 MLP。**五个种子不足以证明 SROK 对 MLP-12 的小幅准确率差距具有统计显著性；MLP 只测试了三个预先指定宽度，未做完整超参数搜索。这个结果支持的是：在当前已知 Fourier 输入和当前 OOD 划分上，显式三阶张量分解呈现出值得继续验证的参数效率优势。

- N0.12 CI workflow： [Run 43138049581](https://github.com/qingjian0/zhouyi-ai/actions/runs/43138049581)
- N0.12 专项实验和 artifact 上传步骤已通过；同一 workflow 后续既有 E01/E02 步骤仍在执行中。
- Artifact：`n12-mlp-baseline-results`，ID `13908865898`。

## 解释边界

- MLP 输入与 SROK 的角色相位信息相同，但不直接获得三阶乘积特征。
- 这是单一小型 tanh MLP 家族，不代表所有 MLP/GNN/Transformer。
- MLP 宽度是预先指定的预算点，不是全面超参数搜索；不能把某个宽度的结果当作整个 MLP 家族上限。
- 参数量接近不等于 FLOPs、内存访问或训练 wall-clock 完全匹配；后续需补充实测资源成本。
- 任务仍是已知解析规则的合成相位 OOD，不代表语义规则学习或自然语言推理。
- 只有在同一数据、验证策略、计算预算和多任务族上反复胜出，才有依据把显式高阶组合设为默认核心结构。
