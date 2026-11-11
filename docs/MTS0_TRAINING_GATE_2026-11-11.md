# MTS-0：最小预序列训练与验证门

**状态：首个可执行原型；不代表完整 CPG-EI 模型已经训练。**

## 目标

把现有 E01 可学习稀疏组合基线接入统一的 prediction-before-reveal 流程，验证最小训练闭环的工程语义：

1. 使用 support 样本训练模型。
2. 对锁定测试输入生成预测。
3. 将预测、输入摘要、模型版本和作用域写入不可变提交记录。
4. 显式封存整个预测批次；封存后禁止追加预测，封存前禁止揭示任何标签。
5. 所有预测提交完成并封存后才揭示测试标签。
6. learner/selector 不可见 locked-test 标签；evaluator 可见。
7. 记录可复现配置和审计计数。

## 当前实现

- 运行器：`prototype/mts0_runner.py`
- 测试：`tests/test_mts0_runner.py`
- 复用模型：`prototype/e01_learned_ranker.py`
- 依赖：Python 标准库；无新增第三方依赖。

## 运行

```bash
python -m unittest discover -s tests -p 'test_mts0_runner.py' -v
python -m prototype.mts0_runner --seed 7 --train-samples 1200 --test-samples 400 --epochs 180 --json
```

## 证据与隔离边界

`EvidenceLedger` 校验 commit/reveal 的 ID、scope、digest 绑定；通过显式 `seal_commits()` 强制预测批次先封存，封存后不可追加预测，封存前不可 reveal；并按角色过滤可见记录。当前实现位于同一 Python 进程中，**只是协议与逻辑测试，不构成安全隔离**。正式锁定测试必须迁移到独立 evaluator 进程或服务，learner 只拿到签名/不可伪造的提交回执，不能读取标签文件或评估数据库。

## 本阶段不证明什么

- 不证明自然语言理解、开放域推理或通用智能。
- 不证明结构 OOD 泛化。
- 不证明 CPG-EI 优于 Transformer、GNN 或超图网络。
- 不证明易象先验有效。
- 不证明手机端内存和延迟目标。

## MTS-0 验收门

| 门 | 验收标准 | 当前状态 |
|---|---|---|
| T0 可执行 | 单命令训练并输出 JSON | 已实现，待 CI |
| T1 确定性 | 固定 seed/config 输出一致 | 已实现单测，待 CI |
| T2 先提交后揭示 | 全部预测提交数等于锁定揭示数 | 已实现单测，待 CI |
| T3 标签隔离策略 | learner/selector 看不到 locked-test | 仅同进程策略测试 |
| T4 证据绑定 | reveal 绑定 commit digest、query、scope | 已实现单测，待 CI |
| T5 独立审计 | evaluator 独立进程/服务 | 未实现 |
| T6 多种子报告 | 至少 5 seeds，均值/标准差及逐 seed 结果 | 已实现 5-seed API 与测试，待 CI/实际运行 |
| T7 OOD 验证 | entity/composition/rule-family/domain OOD | 下一步 |

## 下一阶段

1. 在 CI 中执行全量单测和 MTS-0 smoke run。
2. 运行 5-seed runner，保存真实结果、失败案例和资源成本。
3. 建立严格组合 OOD 和机制族 OOD 数据生成器。
4. 增加固定预算对照：随机、邻接、线性学习器、符号 oracle。
5. 把 evaluator 拆为独立进程，检查数据访问权限。
6. 只有 T0–T6 通过后，才将结果称为可审计训练闭环；随后引入关系/超边学习器，而不是直接扩大参数规模。
