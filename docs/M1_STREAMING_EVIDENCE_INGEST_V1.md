# M1 流式证据摄取原型 v1

状态：首个可执行原型；精确 head `f55171bd7db33aa1df342c4f7bd5450e1f9533ec` 的 Run #1616 已完整通过。后续 benchmark 与恢复覆盖增强仍需新 head CI 和压力测试验收。  
模块：`prototype/streaming_evidence_ingest.py`

## 目标

以固定上限的 UTF-8 字节块读取输入，将原文与字节跨度写入 SQLite；提交每个块时，同一事务更新恢复游标。进程中断后从最后一个已提交字节偏移继续，不把全文载入内存。

## 数据契约

- `document_id`：调用方提供的稳定文档标识。
- `chunk_id`：由协议版本、文档 ID、块序号和内容 SHA-256 确定。
- `byte_start/byte_end`：原始 UTF-8 字节半开区间 `[start, end)`。
- `text_utf8`：原文块，不用摘要替代。
- `content_sha256`：单块原文完整性摘要。
- `token_count`：只有调用方提供真实 tokenizer 时才填写；不以字符数/字节数伪装 Token 数。
- `next_byte_offset/next_ordinal`：与块写入在同一 SQLite 事务内更新。
- WAL 与外键开启；查询接口分页返回，不提供全量加载接口。

## 快速验证

```bash
python -m unittest tests.test_streaming_evidence_ingest -v
python -m unittest discover -s tests -v
```

## 使用示例

```python
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor

store = SQLiteEvidenceIngestor("evidence.sqlite3")
with open("large_input.txt", "rb") as source:
    result = store.ingest(
        "stable-document-id",
        "large_input.txt",
        source,
        chunk_bytes=8192,
        tokenizer=my_exact_tokenizer,  # 可选；必须返回真实 Token 数
        max_chunks=100,                # 可选：模拟批次/中断
    )
```

再次使用相同的 `document_id`、`source_name`、`chunk_bytes` 和完整源文件即可从持久游标继续。恢复或对已完成文档执行幂等重试时，系统会逐块重读已提交前缀并校验 SHA-256；若源内容、长度、跨度或游标不一致则 fail closed。该校验需要 O(已摄取字节数) 的额外磁盘读取时间，但只保留单块缓冲，内存仍为 O(chunk_bytes)。文档 ID 仍应绑定不可变输入对象/版本，以避免无意义的重复校验。

## 内存边界与非声明

- 单次读取缓冲最多为 chunk 上限加 4 字节；SQLite/Python/OS 的额外 RSS 仍须由 M0 进程测量。
- SQLite 页缓存、WAL、Python 对象和底层分配器会带来额外内存；“块大小固定”不等于“整个进程峰值等于块大小”。
- 当前原型要求 seekable binary stream；网络流需要先接入具备持久偏移语义的 spool 层。
- 当前只做原文分块持久化，不做 Observation grounding、语义单元生成、易象算子、超图构建或检索质量承诺。
- 字节块边界保证 UTF-8 码点完整，不保证语义边界；Token 计数必须由实际 tokenizer 提供。
- 幂等保证针对同一文档 ID 和同一输入版本的已完成/已提交批次；输入内容变更时必须使用新文档 ID。

## 基准测量

新增 `prototype/benchmark_streaming_ingest.py`，将 M0 RSS 采样、OS high-water、吞吐、SQLite/WAL 文件大小整合为单次可复现报告；脚本会创建缺失的数据库父目录，但拒绝覆盖已有数据库。新增 `tests/test_streaming_ingest_benchmark.py` 覆盖嵌套输出目录端到端摄取及已有数据库保护。详见 `docs/M1_STREAMING_INGEST_BENCHMARK_V1.md`。每个规模必须在新进程和新数据库执行。

## M1 验收仍需补齐

1. 新增 benchmark 与 tokenizer coverage 变更的精确 head CI。
2. 1M Token 测试：使用项目真实 tokenizer 的增量接口或可证明边界一致的 adapter；不能用字符数估算，也不能简单把独立块 token 数冒充整文 token 数。
3. 1M 输入期间 RSS/OS high-water、SQLite/WAL 磁盘占用、吞吐和延迟。
4. 当前测试覆盖两类子进程硬退出：第 5 个块处理时退出，以及在 0、1、4、8、14 个块已提交后的多个边界退出。每次均由新 SQLite store 重开，核对恢复游标、完整字节、连续跨度、块数和唯一 Chunk ID。仍需更大规模故障注入，以及针对事务内部/存储故障的测试。
5. 对 8K/128K/256K/512K/1M 输入重复运行，报告内存曲线和输入正确性。
6. 多进程并发写入/重复请求的锁冲突和幂等语义测试。

M1 通过只证明原文可有界摄取和持久恢复，不代表 M2 认知工作集、K1 持续认知或 K2 原生表达通过。

## CI wiring

The M0 target branch now explicitly includes this M1 head branch in the repository test workflow's pull-request branch filter. Exact-head CI status must still be read from the GitHub Actions run; configuration alone is not validation.
