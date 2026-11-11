# ZPCM N0.1：SQLite 事件账本与确定性认知状态物化原型

日期：2026-11-11  
状态：实现原型 / 待 CI 验证；不代表手机性能已达标。  
基线：ZPCM / DCMF PR #167，commit 9cade28cb90ad1cc5f2f62125ad11ffbab8366ff

## 1. 本轮目标

把 ZPCM-0/1 的最小核心从架构规格推进为标准库 Python 原型，验证：
- 事件追加与认知状态物化分离；
- 事件 ID 幂等；
- 事件 ID 冲突检测；
- 声明与撤回的事务性物化；
- 双时间语义的最小切片（valid time 与 recorded time 分开）；
- 物化游标与崩溃恢复；
- 有界批次物化；
- 从事件账本确定性重建投影；
- SQLite 完整性与事件内容哈希检查。

## 2. 新增实现

- prototype/zpcm_store.py
- tests/test_zpcm_store.py

存储基线：Python sqlite3 + SQLite WAL，无第三方依赖。

### 2.1 事件协议

每个事件包含 event_id、event_type、schema_version、observed_at、recorded_at、source_refs 和 payload。

canonical JSON 使用稳定键顺序和紧凑编码；SHA-256 仅用于检测事件内容是否与入库时一致，不代表来源可信或语义真实。

事件 ID 相同且规范化内容相同：返回 duplicate receipt，不追加第二条。
事件 ID 相同但内容不同：拒绝，抛出 EventConflictError。

调用方必须在重试时重用原事件对象及 recorded_at，不能重新生成时间戳后冒充同一事件。

### 2.2 追加与物化分离

append_event() 只追加不可变事件账本；materialize() 从投影游标继续应用事件。

该分离允许进程在“事件已持久化、投影尚未更新”时退出。重启后按 cursor 继续，不丢失已提交事件。

CLAIM_ASSERTED 创建一个不可静默覆盖的 claim 记录。
CLAIM_RETRACTED 为原 claim 写入 retracted_seq 和 reason，不删除历史记录。

其他事件类型可保存在账本中，当前 claims-v1 投影暂时忽略它们。

### 2.3 原子性

一个 materialize 批次在单个 SQLite 写事务中完成。批次中任何事件非法，整个批次回滚，cursor 不前进，账本事件仍保留以便诊断。

注意：坏事件会阻塞当前顺序投影；本原型不提供跳过坏事件的逃生通道，因为静默跳过会破坏重放确定性。未来应增加显式 QUARANTINED / projection-version migration 协议。

### 2.4 当前查询能力

query_claims 支持 subject、predicate、valid-time 和 include_retracted 过滤。该接口是原型 API，不等同于百万级索引检索，也没有复杂冲突裁决。

## 3. 正确性边界

已设计的测试覆盖：
- 相同事件重复追加；
- 同 ID 不同内容；
- 追加与物化分离；
- 撤回保留历史；
- 有效时间过滤；
- poison event 原子回滚；
- 关闭重开后的游标恢复；
- 有界批次；
- 确定性投影重建；
- SQLite 与事件哈希完整性；
- 输入校验。

这些测试必须由 CI 实际执行后，才能标记为通过。本 PR 创建时不声称已通过 CI。

## 4. 当前明确不支持

- 多进程并发写入压力测试；
- 加密、隐私删除和数据保留策略；
- 完整双时间断言历史查询；
- 多投影依赖图与增量失效传播；
- FTS5 / 向量检索 / 图路径索引；
- 大对象内容寻址 Blob；
- 快照压缩与备份轮换；
- Android Kotlin / Room / SQLite 原生适配；
- 真机 RAM、延迟、能耗和 1M 事件基准。

## 5. 下一阶段

1. 让 CI 执行现有完整测试套件。
2. 增加 schema migration 与 projection version。
3. 增加快照 manifest、备份恢复和账本校验。
4. 增加显式 quarantine / repair 工具，保持失败事件可审计。
5. 评估 SQLite 复合索引与游标分页。
6. 将参考实现移植为 Kotlin/JVM 与 Android SQLite/Room 适配器，再测真机。

本轮是 ZPCM 的第一个可执行持久化切片，不是完整长期记忆系统。
