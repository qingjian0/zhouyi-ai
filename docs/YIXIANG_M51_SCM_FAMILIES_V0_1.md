# M51：异质 SCM 家族基准 v0.1

## 目的

M50 只覆盖线性连续 SCM。M51 新增两个机制不同的合成因果环境：二元 Logistic 结构方程与含乘性交互项的非线性连续结构方程，并保持固定总体外生噪声，使同一单位的观察/干预形成配对潜在结果。

## 家族 A：二元 Logistic 混杂

图结构：q -> a，q -> c，a -> y，b -> y。a 与 c 共享 q，因此观察数据中 c 可能与 y 相关；但 c 不是 y 的直接原因。每个二元节点用固定单位级 Uniform 外生噪声实现 Bernoulli(logistic(logit))，同一 unit 在不同干预下复用该噪声。

## 家族 B：非线性交互

目标 y 的结构方程含 x*z 乘性交互。单独解释系数并不足以恢复该机制；在共享总体上执行 do(x=0/1)、do(z=0/1) 的配对对照，能够检验交互机制的联合响应。w 是 x 的后代，但不是 y 的直接父节点。

## 统一评估

每个候选变量执行 do(0) 与 do(1)，使用总体平均结果差排序，选取 top-k 后才查询 evaluator oracle，并计算直接父节点 precision/recall/F1。Oracle 不进入候选选择过程。该选择器是手写干预效应算法，不是 LLM。

## 运行

```bash
python -m unittest tests.test_yixiang_scm_families_m51 -v
python -c "from prototype.yixiang_scm_families_m51 import run_family_suite; print(run_family_suite())"
```

## 限制

- 仅两个合成家族，不是全面因果发现 benchmark。
- 尚未覆盖多类别离散、非线性阈值网络、时序/反馈、潜在选择、干扰效应、测量误差与机制漂移。
- 还没有真实 LLM/Agent adapter、外部数据集复现或跨家族统计功效分析。
- 二元 Logistic 的固定 Uniform 噪声构成特定 structural coupling；不同 coupling 可能改变个体层潜在结果，不能将其视为唯一自然机制。
- M51 的结果只能证明实验设施在这两种合成机制上可运行，不能证明类象理论普遍有效或优于 Transformer。
