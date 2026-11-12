# M0 内存测量引擎：实现说明

状态：首个可执行测量切片；PR #258 精确代码提交 `6f3e1acca9ce2a09dfc6be14942f44c1c22f3eba` 已通过 GitHub Actions Run #1609 的完整工作流；尚未通过设备内存预算验收。  
模块：`prototype/memory_budget.py`

## 快速使用

在仓库根目录执行：

```bash
python -m prototype.memory_budget
python -m prototype.memory_budget --json
python -m prototype.memory_budget --json --tracemalloc
python -m unittest tests.test_memory_budget -v
python -m unittest discover -s tests -v
```

- Linux：优先读取 `/proc/self/status` 中的 `VmRSS` 与 `VmHWM`。
- Windows：使用 PSAPI 的 `GetProcessMemoryInfo`。
- 其他平台：可选使用 psutil；OS high-water 可由 resource 提供。
- 所有字节换算使用 MiB = 1,048,576 bytes。

## 对一个操作测量增量 RSS

```python
from prototype.memory_budget import ProcessMemoryMeasurement

with ProcessMemoryMeasurement(interval_seconds=0.01) as measurement:
    run_context_operation()

print(measurement.report.to_dict())
```

报告包含基线 RSS、采样峰值 RSS、结束 RSS、峰值增量、结束增量和样本数。采样器是一个轻量轮询线程，会带来少量测量开销；短于采样间隔的瞬时分配可能被漏掉。

## 逻辑内存池

`MemoryPoolLedger` 用于声明式预算与淘汰计数：

```python
from prototype.memory_budget import MemoryPoolLedger, MIB

ledger = MemoryPoolLedger(total_limit_bytes=64 * MIB)
ledger.register_pool("active_state", 16 * MIB)
ledger.register_pool("relation_working_set", 32 * MIB)
ledger.register_pool("retrieval", 32 * MIB)

ledger.reserve("active_state", 2 * MIB)
ledger.record_eviction("active_state", 1 * MIB)
print([row.to_dict() for row in ledger.snapshot()])
```

池计数是应用声明的逻辑占用，不会分配实际 RAM，也不能代替 RSS。全局上限在每次 reserve 前检查；各池单独上限可以总和大于全局上限。

## 验收边界

本模块当前提供的是 M0 的测量基础，不表示 8K/16 MiB 或 1M/64 MiB 已达成。

后续正式验收还需要：
1. 在隔离子进程中执行 workload，避免进程既有 high-water 影响阶段峰值。
2. 固定 Python 版本、操作系统、分配器、线程数和硬件。
3. 同时报告 RSS、逻辑池、磁盘 I/O、延迟和任务正确性。
4. 用锁定测试集检查长上下文信息保持，不以压缩率代替能力指标。
5. 将轮询采样结果与 OS high-water / cgroup 峰值交叉核对。

## CI 触发

仓库测试工作流的 push 与 pull_request 分支过滤已加入本研发分支。提交新的 M0 head 后应触发完整 unittest 工作流；是否触发及最终状态以 GitHub Actions 实际运行记录为准。

## 运行环境说明

CI 的 pull_request 分支过滤此前没有包含长上下文规格分支。为使本 PR 的精确 head 能触发仓库测试工作流，已在父规格分支补入对应目标分支过滤项。没有将“未触发”误报为“通过”。
