# ZNCA N3-C：持久化事件日志与事务恢复

日期：2026-11-11  
状态：SQLite 标准库参考实现；不是分布式事件存储或生产级移动端数据库。

## 1. 设计原则

N3-B 的内存提交只能保证进程存活期间的状态一致性。N3-C 将认知状态变化写入追加式事件流，事件流是权威记录，当前认知状态是可重建投影。

事件溯源的标准做法包括不可变事件追加、乐观并发校验、幂等处理、重放恢复和必要时的快照。参见 Microsoft Azure Architecture Center 的 Event Sourcing Pattern 文档。

## 2. 事件结构

每个事件包含 stream_id、sequence、transaction_id、event_type、规范化 JSON payload、previous_hash 和 event_hash。

哈希使用 SHA-256 对规范化事件 envelope 计算，形成前向哈希链。它可检测事件内容或顺序被意外篡改，但不能抵御拥有数据库和代码双重控制权的恶意攻击者重写整条链；如需外部防篡改，需要把 head hash 锚定到独立信任域。

## 3. 提交协议

1. 调用方提供 expected_version。
2. 事务开始后先检查 transaction_id 是否已存在。
3. 同一 transaction_id 且请求指纹完全一致，返回原事件；不同请求则报 IdempotencyConflict。
4. 检查当前流版本是否等于 expected_version，不等则 VersionConflict。
5. 生成下一个 sequence、previous_hash 和 event_hash。
6. 在同一个 SQLite 事务中插入事件并 CAS 更新 stream head。
7. 只有 COMMIT 成功后才向调用方返回成功。

BEGIN IMMEDIATE 串行化 SQLite 写事务；流版本的条件更新是第二道 CAS 防线。两个写者基于同一版本竞争时，只有一个能成功。

## 4. 恢复协议

verify() 检查序号连续性、前向哈希链、事件数量与流版本、流头哈希。recover() 通过从初始状态按序重放 HypothesisCommitted 事件，重建当前状态。

当前版本尚未做快照压缩。未来应增加周期快照，但快照只能是可重建优化，不能替代事件流作为事实来源。

## 5. 运行测试

python -m unittest tests.test_znca_n3c_event_store -v
python -m unittest discover -s tests -v

测试覆盖：CAS 冲突、重复事务幂等、事务 ID 冲突、进程重开恢复、事件重放、哈希篡改检测、证据门控、事件分页、双写者竞争。

## 6. 边界与未实现内容

- 单机 SQLite，不是多设备分布式一致性协议。
- WAL + synchronous=FULL 是 SQLite 持久化配置，不等于对所有文件系统/硬件故障的绝对保证。
- 哈希链不是数字签名，也不提供可信时间戳。
- 当前只有 HypothesisCommitted 事件类型，没有完整的候选生命周期事件、回滚补偿事件、证据对象存储或 schema upcaster。
- 没有压缩快照、加密、保留策略、用户数据删除设计、移动端功耗/闪存磨损基准。
- 当前 replay 只接受已知事件类型；未知事件 fail closed，未来需显式 schema version 与 upcaster。

## 7. 后续 N3-D

在持久化提交之上加入反事实比较和补偿事件：保留被否决的分支，不覆盖历史；通过新事件记录撤销、修正和证据更新。之后再做状态快照和增量恢复性能评估。
