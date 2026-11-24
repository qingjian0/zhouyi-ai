from __future__ import annotations

import math

from prototype.classiang_multiscale_training import BANDS, build_band_records, train_all_bands


def test_four_scale_synthetic_training_is_group_disjoint_and_reproducible():
    result = train_all_bands(seed=17)
    assert tuple(result["bands"]) == BANDS
    for band, report in result["bands"].items():
        assert report["group_disjoint"] is True
        assert report["train_records"] > 0
        assert report["validation_records"] > 0
        metrics = report["validation"]
        assert metrics["records"] == report["validation_records"]
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["f1"] <= 1.0
        assert math.isfinite(metrics["f1"])
        assert report["cross_chunk_memory"] is False
        assert report["metric_scope"] == "chunk_level_only"
        assert report["data_origin"] == "synthetic_generated"


def test_long_context_chunks_keep_document_groups_and_global_offsets():
    for band in ("long_document", "ultra_long_context"):
        rows = build_band_records(band)
        assert len({row.group_id for row in rows}) == 4
        assert len(rows) > 4
        for row in rows:
            assert any(item.startswith("global_char_offset=") for item in row.context)
            assert any(item == f"length_band={band}" for item in row.context)
            assert len(row.text) <= 220
