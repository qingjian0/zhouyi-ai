# E12-A11：主动测量证据闭环

日期：2026-11-11  
状态：独立执行器与签名回执原型；尚非生产安全边界。

## 目标与数据流

Learner 提交不可变测量请求（候选版本、scope、协议、目标摘要、参数摘要、估算成本和成本上限）；它不提交观测结果。授权执行器检查候选/scope 白名单、协议注册表与预算，再调用执行器内部注册的测量协议。执行结果由独立 Ed25519 私钥签名，验证端检查签名、上下文和重放状态后，才可转换为 E12-A11 MeasurementEvidence。

## 状态语义

- SELECT：成功获得可用观测；仅此状态可转为证据。
- NO_DISCRIMINATING_MEASUREMENT：测量完成但没有区分性；不更新认知状态。
- BUDGET_EXHAUSTED：预算不足或执行成本超过剩余预算；不更新认知状态。
- INVALID_INPUT：请求无效、协议未注册或候选/scope 未授权。
- EXECUTION_FAILED：协议异常或返回值/成本违反协议。

所有状态均产生签名回执，便于审计；失败状态不是负面观测，也不能作为候选反例。

## 成本与信任边界

预算由执行器维护，不采信 learner 声称的实际成本。请求估算成本不得超过请求上限和当前预算；执行器回报的实际成本必须有限、非负且不超过上限。超出预算时不扣减预算、不生成观测证据。

执行器注册的 callback 属于可信计算基；本原型没有 OS 沙箱，不能防止恶意协议代码伪造观测。预算与 replay guard 均为单进程内存状态，生产环境需要数据库事务、并发原子扣款、持久化幂等键、崩溃恢复和审计日志。

## 证据接入

receipt_to_evidence 先验签、核对 scope digest、执行 replay guard，再只接受 SELECT。产物绑定 candidate_ref、scope_id、scope_digest、request digest、receipt ID、协议和观测值。它尚未自动写入 A7 lifecycle ledger 或 A9 统计聚合：原始观测不能直接等同于候选正确性；后续必须由候选预测对观测的预注册似然/可证伪判据解释，再进入证据聚合。

## 主动选择与 EIG

E12-A2-M 的有限假设 EIG 选择器可用于提出测量候选，但 EIG 是基于假设集与观测模型的策略估计，不是观测本身。必须记录模型版本、假设先验、预测分布和成本模型，并以小域 oracle 校验。不得允许 learner 自报 EIG 或把 EIG 高误认为结果真实。

## 剩余工作

1. 将 request authorization、预算预留/结算改为事务化服务。
2. 注册协议采用版本化 manifest、输入输出 schema、校准数据与噪声模型。
3. 引入可信 key registry、轮换/撤销和持久化 replay guard。
4. 把 MeasurementEvidence 通过预注册 likelihood / counterexample classifier 接入 A7/A9，区分噪声、shift、scope violation 与真正反例。
5. 测试并发预算竞态、执行器崩溃、超时/部分执行、重试幂等和恶意协议。
6. 进行 learner/evaluator label noninterference 与 candidate-order mutation 测试。

## 当前结论

A11 首版实现了请求/结果分离、候选-scope 授权、执行器侧成本核算、签名回执、重放保护和仅成功观测进入证据的转换门槛。它是可测试原型，不代表测量本身无偏或因果识别成立。
