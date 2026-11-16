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

`EvidenceLedger` 校验 commit/reveal 的 ID、scope、digest 绑定；通过显式 `seal_commits()` 强制预测批次先封存，封存后不可追加预测，封存前不可 reveal。当前 runner 将 learner 与 evaluator 放入独立 spawn 子进程：learner 只收到不含 targets 的 `PublicExample`，完成全部预测并由协调器封存提交批次后，才启动 evaluator 并向其提供测试标签。协调器进程仍持有测试标签；子进程默认同一 OS 用户，因此这属于**进程级隔离原型，不是安全边界**，不能防御 root、ptrace、同 UID 恶意进程或宿主机失陷。生产级隔离仍需独立服务/账户、文件权限或容器沙箱，并让 evaluator 私有标签存储不被 learner 访问。

## 本阶段不证明什么

- 不证明自然语言理解、开放域推理或通用智能。
- 不证明结构 OOD 泛化。
- 不证明 CPG-EI 优于 Transformer、GNN 或超图网络。
- 不证明易象先验有效。
- 不证明手机端内存和延迟目标。

## MTS-0 验收门

| 门 | 验收标准 | 当前状态 |
|---|---|---|
| T0 可执行 | 单命令训练并输出 JSON | 已实现；MTS-0 smoke step 成功 |
| T1 确定性 | 固定 seed/config 输出一致 | 单测通过 |
| T2 先提交后揭示 | 全部预测提交数等于锁定揭示数 | sealed-batch 单测通过，smoke 成功 |
| T3 标签隔离策略 | learner/selector 看不到 locked-test | 同进程策略测试通过；非安全边界 |
| T4 证据绑定 | reveal 绑定 commit digest、query、scope | 单测通过 |
| T5 进程级审计 | learner/evaluator 独立进程，标签只传给 evaluator，且 evaluator 在封存后启动 | 已实现原型；等待当前头 CI；同 UID、协调器持有标签，非安全边界 |
| T6 多种子报告 | 至少 5 seeds，均值/标准差及逐 seed 结果 | 5 seeds × 1,200 train / 400 locked-test，当前头 CI 已通过；仅为 E01 IID 合成任务 |
| T7 OOD 验证 | entity/composition/rule-family/domain OOD | 下一步 |

## 已验证的 CI 记录

- Run 43092157613：当前 MTS-0 PR 头 `e95022d0e11c9b89d2695cd15dc96ddeea372047` 的完整 tests workflow 成功。
- 五种子正式样本规模：每种子 1,200 条训练、400 条锁定测试、180 epochs；总计 6,000 条训练和 2,000 条锁定测试。
- Exact Match：`0.9220 ± 0.0212`；Micro-F1：`0.9740 ± 0.0071`（5 seeds，样本标准差）。
- 各种子 Exact Match：seed 7 `0.9375`；8 `0.9075`；9 `0.9300`；10 `0.8925`；11 `0.9425`。
- 五个种子均通过预测先提交、批次封存后揭示；每个种子 400 commits / 400 reveals，learner 与 selector 可见 locked-test 标签均为 0。
- JSON Artifact：`mts0-five-seed-results`，workflow run 43092157613。
- 解释边界：结果只验证当前 E01 线性合成 IID 任务；不证明结构 OOD、独立 evaluator 安全隔离或完整认知能力。

## 下一阶段

1. 在 CI 中执行全量单测和 MTS-0 smoke run。
2. 运行 5-seed runner，保存真实结果、失败案例和资源成本。
3. 建立严格组合 OOD 和机制族 OOD 数据生成器。
4. 增加固定预算对照：随机、邻接、线性学习器、符号 oracle。
5. 将进程级 evaluator 进一步隔离为独立 OS 账户/服务，确保协调器与 learner 无权读取 evaluator 私有标签存储。
6. 只有 T0–T6 通过后，才将结果称为可审计训练闭环；随后引入关系/超边学习器，而不是直接扩大参数规模。
