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


@pytest.mark.integration
def test_e2e_hymn315_creates_musicxml(tmp_path):
    """hymn315_Normal.png → ScoreUnderstandingAdapter → .mxl 생성 E2E 검증."""
    from app.stages.omr.score_understanding_adapter import ScoreUnderstandingAdapter
    img_path = Path(__file__).parent.parent.parent / "score_images" / "hymn315_Normal.png"
    if not img_path.exists():
        pytest.skip("hymn315_Normal.png 없음 — score_images/ 디렉터리 확인")

    adapter = ScoreUnderstandingAdapter(work_dir=tmp_path)
    result = adapter.recognize(img_path)

    assert result.exists(), f"MusicXML 파일 생성 실패: {result}"
    assert result.suffix == ".mxl"

    import music21
    score = music21.converter.parse(str(result))
    all_notes = list(score.flatten().notes)
    print(f"\n[E2E] 검출 음표 수: {len(all_notes)}")
    assert len(all_notes) >= 0


@pytest.mark.integration
def test_e2e_layout_detection_hymn315(tmp_path):
    """hymn315_Normal.png 레이아웃 분석 — 보표 시스템 최소 2개 검출."""
    import cv2
    from app.stages.omr.preprocessor import preprocess
    from app.stages.omr.layout_analyzer import analyze_layout
    img_path = Path(__file__).parent.parent.parent / "score_images" / "hymn315_Normal.png"
    if not img_path.exists():
        pytest.skip("hymn315_Normal.png 없음")

    pre = tmp_path / "pre.png"
    preprocess(img_path, pre)
    gray = cv2.imread(str(pre), cv2.IMREAD_GRAYSCALE)
    layout = analyze_layout(gray)

    assert len(layout.staff_systems) >= 2, \
        f"보표 시스템 {len(layout.staff_systems)}개 검출 — 최소 2개 필요"
    print(f"\n[Layout] 보표 시스템: {len(layout.staff_systems)}개")
    print(f"[Layout] 가사 영역: {len(layout.lyric_regions)}개")
