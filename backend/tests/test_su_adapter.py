import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.stages.omr.score_understanding_adapter import ScoreUnderstandingAdapter
from app.domain.ports import OmrPort

def test_adapter_implements_omr_port():
    assert issubclass(ScoreUnderstandingAdapter, OmrPort)

def test_adapter_recognize_returns_path(tmp_path):
    """모든 하위 모듈을 mock해서 파이프라인이 Path를 반환하는지 확인."""
    img = tmp_path / "score.png"
    img.write_bytes(b"PNG_DUMMY")

    with patch("app.stages.omr.score_understanding_adapter.preprocess") as p0, \
         patch("app.stages.omr.score_understanding_adapter.analyze_layout") as p1, \
         patch("app.stages.omr.score_understanding_adapter.OmrEngine") as p2, \
         patch("app.stages.omr.score_understanding_adapter.extract_meta") as p3, \
         patch("app.stages.omr.score_understanding_adapter.extract_lyrics") as p4, \
         patch("app.stages.omr.score_understanding_adapter.assemble") as p5:

        from app.stages.omr.types import LayoutResult, BBox, StaffSystem, ScoreMeta, LyricsResult
        import numpy as np

        p0.return_value = img
        p1.return_value = LayoutResult(1200, 900, None, None,
            [StaffSystem(BBox(0,100,900,80), [110,120,130,140,150], "treble")], [])
        p2.return_value.detect.return_value = []
        p3.return_value = ScoreMeta()
        p4.return_value = LyricsResult(verses=[])
        out_mxl = tmp_path / "score.mxl"
        out_mxl.touch()
        p5.return_value = out_mxl

        adapter = ScoreUnderstandingAdapter(work_dir=tmp_path)
        result = adapter.recognize(img)

    assert isinstance(result, Path)
    assert result.suffix == ".mxl"
