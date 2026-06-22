"""Module 2b: 피치 변환 단위 테스트.

보표 설정: line_ys=[100, 110, 120, 130, 140], spacing=10
  이미지 좌표계: y가 작을수록 위(높은 음정)
  트레블 클레프:
    line_ys[0]=100 (최상선) = F5
    line_ys[1]=110           = D5
    line_ys[2]=120 (중간선)  = B4
    line_ys[3]=130           = G4
    line_ys[4]=140 (최하선)  = E4  ← 음악 표기 1번째 선
  베이스 클레프:
    line_ys[4]=140 (최하선)  = G2
    line_ys[0]=100 (최상선)  = A3
"""
from app.stages.omr.types import BBox, StaffSystem
from app.stages.omr.pitch_converter import y_to_pitch


def _treble_staff():
    # 보표선 y: 100, 110, 120, 130, 140 → spacing=10
    return StaffSystem(
        bbox=BBox(0, 90, 500, 60),
        line_ys=[100, 110, 120, 130, 140],
        clef="treble",
    )


def _bass_staff():
    return StaffSystem(
        bbox=BBox(0, 90, 500, 60),
        line_ys=[100, 110, 120, 130, 140],
        clef="bass",
    )


def test_treble_middle_line_is_B4():
    """트레블 클레프 3번째 선(인덱스 2, y=120) = B4."""
    staff = _treble_staff()
    assert y_to_pitch(120, staff) == "B4"


def test_treble_bottom_line_is_E4():
    """트레블 클레프 최하선(음악 1번째 선, y=140) = E4."""
    staff = _treble_staff()
    assert y_to_pitch(140, staff) == "E4"


def test_treble_first_space_is_F4():
    """트레블 클레프 1번째 칸(최하선 바로 위, y=135) = F4."""
    staff = _treble_staff()
    assert y_to_pitch(135, staff) == "F4"


def test_bass_bottom_line_is_G2():
    """베이스 클레프 최하선(음악 1번째 선, y=140) = G2."""
    staff = _bass_staff()
    assert y_to_pitch(140, staff) == "G2"
