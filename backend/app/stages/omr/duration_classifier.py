"""Module 2c: 음표 형태 → 음가(quarterLength) 분류."""
from __future__ import annotations
from app.stages.omr.types import RawDetection

_REST_DURATIONS = {
    "rest_whole": 4.0,
    "rest_half": 2.0,
    "rest_quarter": 1.0,
    "rest_eighth": 0.5,
    "rest_16th": 0.25,
}

_NEARBY_THRESHOLD_PX = 40  # 점/깃발이 음표로부터 이 거리 이내면 연관


def classify_duration(
    det: RawDetection, nearby: list[RawDetection]
) -> tuple[float, bool]:
    """음표 검출 결과와 인근 기호로부터 음가를 반환한다.

    Returns:
        (quarterLength, is_dotted)
    """
    cls = det.class_name

    # 쉼표
    if cls in _REST_DURATIONS:
        return _REST_DURATIONS[cls], False

    # 온음표 후보 (open, 줄기/깃발 없음)
    if cls == "notehead_open":
        close = [n for n in nearby if _is_close(det, n)]
        has_flag = any(n.class_name.startswith("flag_") for n in close)
        has_beam = any(n.class_name == "beam" for n in close)
        is_dotted = any(n.class_name == "augmentation_dot" for n in close)
        if not has_flag and not has_beam:
            return 4.0, is_dotted   # 온음표
        return 2.0, is_dotted       # 2분음표

    # 채운 음표머리
    if cls == "notehead_filled":
        close = [n for n in nearby if _is_close(det, n)]
        is_dotted = any(n.class_name == "augmentation_dot" for n in close)
        flag_count = sum(1 for n in close if n.class_name.startswith("flag_"))
        beam_count = sum(1 for n in close if n.class_name == "beam")
        subdivisions = max(flag_count, beam_count)
        ql = 1.0 / (2 ** subdivisions) if subdivisions > 0 else 1.0
        return ql, is_dotted

    return 1.0, False  # 미분류 → 4분음표 기본값


def _is_close(a: RawDetection, b: RawDetection) -> bool:
    dx = abs(a.bbox.center_x - b.bbox.center_x)
    dy = abs(a.bbox.center_y - b.bbox.center_y)
    return dx <= _NEARBY_THRESHOLD_PX and dy <= _NEARBY_THRESHOLD_PX
