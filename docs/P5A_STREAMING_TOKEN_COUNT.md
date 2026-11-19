# P5-A Token 级精确计量：首个实现

状态：增量实现已加入；真实生产 tokenizer adapter、1M 规模设备曲线和 exact-head CI 仍待验收。

## 为什么不能直接累加 chunk token_count

BPE、Unigram 等 tokenizer 的分词结果可能跨越任意输入块边界。分别执行 encode(chunk_1)、encode(chunk_2) 再求和，通常不保证等于 encode(chunk_1 + chunk_2)。因此 M1 中原有可选的 chunk-local `tokenizer(text)` 字段只能作为块级诊断数据，不能作为整篇文档的精确 Token 数。

## 新增接口

`prototype/streaming_token_count.py` 定义有状态 `IncrementalTokenizer` 协议：

- 同一文档只创建一个 tokenizer 状态，逐块调用 `feed(text, final=False)`。
- adapter 只能输出已确定、不会被后续文本改变的 token IDs；可能与后续文本合并的后缀必须留在内部缓冲。
- 文档结束时调用一次 `feed("", final=True)` 刷出剩余 token。
- 所有输出 ID 必须为非负整数；记录稳定 tokenizer_id。
- `count_evidence_document` 按 SQLite 页读取完整原文，但跨页不重置 tokenizer 状态，不累加历史 chunk-local token_count。

## 验收与限制

- 单元测试使用一个跨 chunk 合并的 BPE 风格测试 tokenizer，验证切块后的增量计数与整篇文档编码一致。
- 该测试验证的是流式协议，不是任何真实生产 tokenizer 的正确性或 1M 能力。
- 真实 tokenizer adapter 必须用其官方 whole-document encode 结果做边界一致性测试，覆盖 UTF-8、多字节字符、空白、标点、长连续文本和各种 chunk 边界。
- tokenizer ID、词表/模型版本、预分词规则与 normalizer 版本必须进入数据 manifest；版本不匹配时禁止复用计数或 checkpoint。
- 最终 1M 输入验收必须同时证明：输入字节/文本完整、增量 token 序列与 whole-document tokenizer 输出一致、资源峰值可复现。

运行：

```bash
python -m unittest tests.test_streaming_token_count tests.test_streaming_evidence_ingest -v
```
