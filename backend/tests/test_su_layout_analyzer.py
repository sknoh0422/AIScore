import numpy as np
import pytest
from app.stages.omr.layout_analyzer import analyze_layout
from app.stages.omr.types import LayoutResult


def _make_hymn_image(h=1200, w=900) -> np.ndarray:
    """보표선 5개짜리 4시스템 + 가사 영역을 흉내낸 합성 이미지."""
    img = np.full((h, w), 255, dtype=np.uint8)
    # 4개 보표 시스템 (y=200, 450, 700, 950), 각각 5줄 간격 15px
    for sys_y in [200, 450, 700, 950]:
        for i in range(5):
            y = sys_y + i * 15
            if y < h:
                img[y, 50:w-50] = 0
    # 가사 영역 대략 표시 (텍스트처럼 점 뿌리기)
    for row in range(1050, 1150, 20):
        if row < h:
            img[row, 100:800:5] = 0
    return img


def test_analyze_layout_returns_correct_type():
    img = _make_hymn_image()
    result = analyze_layout(img)
    assert isinstance(result, LayoutResult)


def test_analyze_layout_detects_staff_systems():
    img = _make_hymn_image()
    result = analyze_layout(img)
    assert len(result.staff_systems) >= 1


def test_analyze_layout_image_dimensions():
    img = _make_hymn_image(h=1200, w=900)
    result = analyze_layout(img)
    assert result.image_h == 1200
    assert result.image_w == 900
