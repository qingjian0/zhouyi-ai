# M62 — Gold admission and provenance gates v0.1

Status: implementation added; 17 focused tests passed on head `6032663924243c2ea65ba442fab4d59a1d8c9ead`; combined M61/M62 repository-wide workflow `43590149812` passed.

## Problem found

The M59 validator correctly required two annotators and supported pending adjudication, but its corpus audit counted every valid record in ordinary split counts. A record with pending adjudication could therefore appear indistinguishable from a gold example in aggregate counts. That is a data-governance defect: syntactic validity is not the same as gold admission.

## Admission stages

- discovery: bibliographic/source candidate; not a gold record.
- review_pending: evidence has been transcribed and annotated, but adjudication is pending.
- adjudicated: adjudication is complete, but the record is not eligible for core gold (for example, secondary/commentarial material or rejected/uncertain claims).
- gold: only pre-Qing core primary evidence with completed adjudication and all claim decisions accepted.
- excluded: explicitly excluded from the usable corpus.

For backwards compatibility, records without an explicit admission_status are classified from their adjudication state and evidence policy. Pending records are review_pending, never gold. Only records that satisfy the core evidence policy and have adjudicated all-accept decisions are counted as gold.

## Audit outputs

- records: all syntactically valid records.
- gold_records: only admitted gold records.
- review_pending_records, adjudicated_non_gold_records, discovery_records, excluded_records.
- split_counts: gold-only train/validation/test counts.
- all_record_split_counts: all records by assigned split, including pending and discovery records.
- source-period and evidence-policy counts are explicitly labelled as counts over all records.

Leakage checks still consider every record, not only gold records. This prevents pending or excluded records from being moved across splits to create accidental source leakage.

## Tests

The M62 tests verify that:
1. Pending adjudication does not increment gold counts.
2. A gold record requires final adjudication and all accepted claim decisions.
3. Secondary/commentarial or collation-only records cannot enter core gold.
4. Split counts distinguish all records from admitted gold records.
5. A record cannot enter gold when its cited transcription is unreviewed or lacks an accessible scan URI.

## Research source discovery (not gold)

A candidate source family has been identified for the first real source audit: the 四部丛刊初编影宋本《周易》, described by the CText catalog as a facsimile of a Song printed edition held by 上海涵芬楼. The CText page states that its text was automatically OCR-matched to the base edition, so the digital transcription is marked unreviewed and cannot enter gold until each cited span is checked against the actual scan.

For 咸卦, the source page contains the distinct textual layers:
- 《象传》 text: “象曰山上有泽咸君子以虚受人”
- 王弼注: “以虚受人物乃感应”

These must remain separate. The first is the received 《象传》 text, whose composition and attribution are historically layered and contested; the second is commentary attributed to Wang Bi. Neither line is being admitted as gold in this PR. The Song witness, 1920s facsimile, OCR transcription, and modern web rendering are separate provenance layers.

A separate 四库全书本 witness exists for the same work and passage. Its page explicitly identifies the base as 景印文渊阁四库全书第七册 and opens with “钦定四库全书”; it is a Qing witness and therefore a collation witness, not independent pre-Qing primary evidence.

## Layer separation and witness cautions

The received text and commentary must not be merged:

| Layer | Passage in the 咸卦 witness | Attribution/status |
|---|---|---|
| 《象传》 | 象曰山上有泽咸君子以虚受人 | Received canonical layer; traditional attribution is not equivalent to a settled composition date |
| 王弼注 | 以虚受人物乃感应 | Wei-period commentary layer, not the canonical 《象传》 wording |
| Modern transcription | punctuation, simplified/traditional conversion, OCR repairs | Editorial/digital layer; every normalization must retain a reversible link to the witness |

The Four Books Congkan catalog identifies the book as a facsimile of a Song printed edition held by Shanghai Hanfenlou. The precise printing lineage should remain qualified: Peking University's editorial/research center summarizes a bibliographic debate over whether the underlying copy is a Song Fuzhou Gongshi Ku edition and whether it was repaired in the Southern Song Ningzong period. Do not hard-code an exact Song reign date until the catalog record and physical copy are inspected.

A 2023 modern critical edition of 《周易注》 states that it uses the Four Books Congkan Song facsimile as its base and collates Dunhuang manuscripts, the National Library's Fuzhou Gongshi Ku copy, other Song printed editions, and other scholarly collation records. This is a valuable collation roadmap, but the modern edition itself is not a substitute for recording each underlying witness separately.

## Related concept research

See [Classical yixiang concept map](YIXIANG_CLASSICAL_CONCEPT_MAP_V0_1.md) for source-layer-separated notes on 《系辞上》《系辞下》《说卦传》 and the 咸卦 《象传》 example. The concept map is a research guide only; its quotations remain discovery-stage until verified against the scan-backed witness.

## References

- CText catalog for 《周易》 in 四部丛刊初编: https://ctext.org/library.pl?if=gb&remap=gb&res=77330
- CText volume four OCR text: https://ctext.org/wiki.pl?chapter=119825&if=en&remap=gb
- Wikisource 四部丛刊本, 卷四: https://zh.wikisource.org/wiki/周易_(四部叢刊本)/卷四
- Wikisource 四部丛刊本, 卷七（系辞上）: https://zh.wikisource.org/zh-hans/周易_(四部丛刊本)/卷七
- Wikisource 四部丛刊本, 卷八（系辞下）: https://wk.100ke.info/zh-hans/周易_(四部丛刊本)/卷八
- Wikisource 四库全书本, 卷四: https://zh.wikisource.org/wiki/周易註_(四庫全書本)/卷04
- CText bibliographic note on the 1919–1922 first series and 1924 reprint: https://ctext.org/wiki.pl?chapter=543417&if=gb&remap=gb
- Peking University Confucian Canon editorial center on the edition lineage and Song-printing debate: https://ruzang.pku.edu.cn/rzen/info/1017/1177.htm
- Commercial Press 2023 modern critical edition and its stated base/variant witnesses: https://www.cp.com.cn/book/4d4efcc9-9.html
- Commercial Press history records completion of the first series in 1922: https://www.cp.com.cn/ourselves/history/dsj.html

No historical claim is inferred from a modern web page alone. Image inspection, edition-level collation, and independent annotation remain required.
