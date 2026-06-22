"""Module 2b: 보표 내 y좌표 → 피치 문자열 변환."""
from __future__ import annotations

from app.stages.omr.types import StaffSystem

# 음이름 인덱스: C=0, D=1, E=2, F=3, G=4, A=5, B=6
_NOTE_NAMES = ["C", "D", "E", "F", "G", "A", "B"]

# 절대 step = octave * 7 + note_index
# 트레블 클레프: 최하선(line_ys[-1]) = E4 → abs_step = 4*7 + 2 = 30
# 베이스 클레프: 최하선(line_ys[-1]) = G2 → abs_step = 2*7 + 4 = 18
_TREBLE_BOTTOM_STEP = 4 * 7 + 2  # E4 = 30
_BASS_BOTTOM_STEP = 2 * 7 + 4    # G2 = 18


def y_to_pitch(y: int, staff: StaffSystem) -> str:
    """보표 내 y좌표를 피치 문자열로 변환한다.

    이미지 좌표계에서 y가 작을수록 위(높은 음정)이다.
    보표선 간격(space)의 절반(half_space)마다 반음계 한 스텝이 변한다.
    최하선(line_ys[-1])을 기준으로 위로 갈수록 스텝이 증가한다.

    Args:
        y: 이미지 내 절대 y좌표
        staff: 보표선 위치 및 클레프 정보를 담은 StaffSystem

    Returns:
        피치 문자열 ("G4", "D5" 등, 임시표 없음)
    """
    space = staff.staff_space
    if space <= 0:
        return "C4"

    bottom_line_y = staff.line_ys[-1]   # 최하선 (y값 최대 = 음악적으로 가장 낮은 선)
    base_step = (
        _TREBLE_BOTTOM_STEP if staff.clef == "treble" else _BASS_BOTTOM_STEP
    )

    # 최하선에서 위로 갈수록(y 감소) step_offset 증가
    # half_space 단위(space/2)로 step이 1씩 변한다
    half_spaces_from_bottom = (bottom_line_y - y) / (space / 2)
    step_offset = round(half_spaces_from_bottom)
    abs_step = base_step + step_offset

    octave, note_idx = divmod(abs_step, 7)
    return f"{_NOTE_NAMES[note_idx]}{octave}"
