"""Module 2c: 성부 분리 — 보표 내 음표 위치 기반 휴리스틱."""
from __future__ import annotations
from app.stages.omr.types import RawDetection, StaffSystem


def assign_voice(det: RawDetection, staff: StaffSystem) -> int:
    """음표의 보표 내 위치로 성부를 결정한다.

    Returns:
        1 = Soprano(treble) / Tenor(bass)
        2 = Alto(treble) / Bass(bass)
    """
    if not staff.line_ys:
        return 1
    mid_y = staff.line_ys[2]   # 3번째 선(중간선)
    return 1 if det.bbox.center_y <= mid_y else 2
