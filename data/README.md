# 古籍类象来源目录

- `classical_yixiang_source_catalog.json`：Zhouyi-AI 第一版传统古籍候选来源目录，共 111 个工作条目（跨领域候选来源持续扩充）。
- 清代以前材料为研究主体；清代及清以后条目仅用于辑佚、校勘、目录补漏和现代学术审查。
- 所有条目初始状态均为 `candidate_not_ingested`。这表示已纳入候选书目，不表示原文已经下载、校勘、逐篇索引或完成语义标注。
- 入库时必须补齐可靠底本、版本信息、篇章定位、原文转录状态、异文和许可信息。关键主张需定位到具体段落。
- 不允许根据书名或后世注释自动生成古义；不允许将晚出解释回填为早期文本原义。

来源目录由 `schemas/classical-yixiang-source-catalog.schema.json` 描述，`tests/test_classical_yixiang_catalog.py` 检查 JSON 可解析性、来源 ID 唯一性与史料状态边界。来源 ID 使用稳定的小写 ASCII 标识符，不以中文书名或空格作为机器键。

主规范见 [传统古籍类象研究总纲与语料建设规范](../docs/CLASSICAL_YIXIANG_CORPUS_AND_RESEARCH_PROTOCOL.md)。


## 结构化语料与来源目录的区别

`classical_yixiang_source_catalog.json` 是候选作品/篇章目录；它不表示文本已入库或已校勘。具体短引与主张级证据记录保存在 `classical_xiang_corpus.v0.1.json`，其格式见 `../schemas/classical-xiang-corpus.schema.json`。只有完成底本定位、文本核验和审核的条目才能升级状态。
