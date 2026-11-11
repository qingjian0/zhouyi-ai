# E12-A10：签名评估回执与重放保护

日期：2026-11-11  
状态：Ed25519 签名回执原型；密钥部署与持久化重放状态尚未生产化。

## 1. 目标

E12-A9 的普通 EvaluatorVerdict / BoundEvaluation 可由同进程调用者伪造。E12-A10 将评估器输出改为由 evaluator 私钥签名的不可变回执，外部协调器只持有公钥。

## 2. 签名字段

签名覆盖：
- evaluator_id、key_id、evaluator_version；
- dataset_version、split_id；
- candidate_ref、scope_digest；
- episode_id、commit_digest；
- 单调 sequence；
- gold_label、scored、correct。

任何字段变更都会导致签名校验失败。回执 ID 由规范化 payload 与签名共同计算。

## 3. 验证顺序

1. 校验 receipt_id 与 payload/signature 一致；
2. 使用 evaluator 注册公钥验证 Ed25519 签名；
3. 校验调用方要求的数据集、split、候选版本等上下文；
4. 通过持久化 ReceiptReplayGuard 校验 sequence 连续递增、commit 未被重复使用；
5. 验证通过后，才允许转成 E12-A9 的 BoundEvaluation。

## 4. 信任边界

- 私钥只能部署在 evaluator 服务，learner/coordinator 不能读取；
- 公钥通过受信任的 evaluator key registry 分发；
- key_id 不是信任根，必须由 registry 将其绑定到正确公钥、有效期和撤销状态；
- ReplayGuard 当前是内存实现，生产必须持久化并具备并发原子性；
- Ed25519 签名证明回执来自持有私钥的一方，不证明标签本身正确，也不证明数据集没有污染；
- 测试生成临时密钥，不包含生产密钥。

## 5. 依赖

通过项目可选依赖 security 安装 cryptography。核心原型仍不强制所有用户安装该依赖。

## 6. 下一步

- 将签名回执适配为 E12-A9 BoundEvaluation 的唯一可信入口；
- evaluator 独立服务、密钥轮换/撤销与 key registry；
- ReplayGuard 数据库事务、并发竞态和灾难恢复测试；
- 数据集 manifest 签名、标签访问审计；
- 把 A2 主动测量请求/结果纳入签名证据链。

## 7. 结论

E12-A10 补上了 A8/A9 缺少的来源认证与防重放协议原型。它不等同于完整安全部署：密钥管理、评估服务隔离、持久化 replay state 和数据集可信性仍需独立工程验证。
