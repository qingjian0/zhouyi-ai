# E12-A20-1：同步 Sum-Product Belief Propagation

状态：首版参考实现；不是已验证的高速通用推理引擎。

## 实现

- 复用 A20-0 的离散变量与 HARD/SOFT/EVIDENCE/PRIOR 因子定义。
- 在 log domain 中执行 variable-to-factor 与 factor-to-variable 消息。
- 每轮严格同步：本轮所有消息只读取上一轮消息，禁止更新顺序造成异步差异。
- 消息归一化、可配置 damping、最大概率差收敛阈值。
- 输出变量边缘分布、迭代次数、消息更新次数、因子表规模、证据引用。
- 硬预算：最大迭代数、消息更新数、因子局部状态组合数。
- 状态区分 CONVERGED、ITERATION_LIMIT、BUDGET_EXHAUSTED、INCONSISTENT_MESSAGES。

## 数学定义

对变量 (x) 与因子 (f)：

`m_{x\to f}(x) \propto \prod_{g\in N(x)\\setminus f}m_{g\to x}(x)`

`m_{f\to x}(x) \propto \sum_{\mathbf{x}_{N(f)\\setminus x}} \phi_f(\mathbf{x}_{N(f)})\prod_{y\in N(f)\\setminus x}m_{y\to f}(y)`

其中 `φ_f = exp(-cost_f)`；HARD forbidden assignment 的势为 0。所有运算在 log-space 中完成。

## 验证

- 树状图边缘分布与精确分布方向一致。
- 硬约束对禁止状态赋予零概率。
- 孤立变量保持均匀边缘分布。
- 因子表/消息预算耗尽 fail closed。
- 迭代上限不伪装成收敛。
- 输入变量和因子顺序置换不改变结果。

## 重要限制

1. **只有树状图上的 sum-product 在常见正则条件下保证精确边缘分布**；有环图是近似算法，可能不收敛或收敛到有偏结果。
2. 当前每个因子的局部配置表仍需枚举，复杂度随因子作用域域大小乘积增长；高阶超因子可能昂贵。
3. 当前同步消息更新为单进程顺序循环实现；同步语义不等于多核/分布式并行执行。
4. 目前仅输出边缘分布，不输出联合 MAP 解；边缘最大值组合不一定是全局 MAP。
5. 证据引用只是 provenance 字段，不验证签名、不校准似然。
6. damping 和 tolerance 需要按任务校准；收敛不等于推理正确。
7. 当前没有自动从数据学习因子，也没有接入易象/太玄语法。

## 下一步 A20-2

- 构造随机小图，逐例与 A20-0 精确边缘概率对照。
- 分离树图与有环图结果，报告误差/收敛率。
- 加入环路检测和因子图拓扑统计。
- 之后再评估并行执行后端与运行时性能。
