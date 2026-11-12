# N0.14：可学习频率的循环组合算子

**状态：已加入可执行模型、解析梯度测试和 OOD 训练测试，等待 CI。**

## 研究问题

N0.11–N0.13 使用固定 Fourier/tensor-product 表示，优势依赖明确提供的频率基。N0.14 向前推进一步：不再固定频率为 1，而是将共享频率 `omega` 与四个三阶张量系数、偏置一起训练。

## 模型

令每个角色的相位为 a、b、c，定义：

`cos(ω(a+b+c)) = cos(ωa)cos(ωb)cos(ωc) - cos(ωa)sin(ωb)sin(ωc) - sin(ωa)cos(ωb)sin(ωc) - sin(ωa)sin(ωb)cos(ωc)`

模型参数：
- 四个 rank-1 三阶张量项的可学习系数；
- 一个偏置；
- 一个可学习共享频率 `omega = exp(log_omega)`。

总计 **6 个参数**。频率通过解析导数参与 Adam 更新。初始化频率为 0.9，属于接近目标频率 1 的先验，不是从任意随机初始化开始。

## 实验

- 使用与 N0.11 相同的 train / validation / held-out phase test 划分。
- validation 只负责选择 logit 方向。
- 对比 6 参数 learnable operator 与 35 参数 SROK。
- 记录每个种子的 learned omega、OOD accuracy、balanced accuracy 和 BCE。
- 单测用有限差分验证解析频率梯度。

## 复现

```bash
python -m unittest tests.test_n14_learnable_cyclic_operator -v
python -m prototype.n14_learnable_cyclic_operator --seeds 5 --start-seed 7 --train-samples 3000 --validation-samples 750 --test-samples 1500 --epochs 120 --json
```

## 解释边界

这是一个可学习的参数化代数算子，不是从原始文本中端到端发现任意关系的通用认知模型。目标函数族、Fourier 形式和 rank-4 分解已知，模型只学习频率与系数。若该实验成功，下一步要扩大到未知频率、多个关系族、不同组合算子和从数据学习角色表示。
