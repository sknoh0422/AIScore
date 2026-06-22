"""Module 3: 조성·박자·제목·빠르기 추출."""
from __future__ import annotations
import re
import numpy as np

from app.stages.omr.types import LayoutResult, RawDetection, ScoreMeta

_SHARP_KEYS = ["C major", "G major", "D major", "A major",
               "E major", "B major", "F# major", "C# major"]
_FLAT_KEYS  = ["C major", "F major", "Bb major", "Eb major",
               "Ab major", "Db major", "Gb major", "Cb major"]
_BPM_RE = re.compile(r"♩\s*=\s*(\d+)|(\d+)\s*bpm", re.IGNORECASE)
_TIME_SIGS = {(4, 4), (3, 4), (2, 4), (6, 8), (3, 8), (2, 2)}


def accidentals_to_key(count: int, kind: str) -> str:
    """임시표 개수와 종류로 조성 문자열을 반환한다."""
    if kind == "sharp":
        return _SHARP_KEYS[min(count, 7)]
    return _FLAT_KEYS[min(count, 7)]


def extract_meta(
    layout: LayoutResult,
    detections: list[RawDetection],
    gray: np.ndarray,
) -> ScoreMeta:
    """레이아웃·검출 결과·이미지에서 메타정보를 추출한다."""
    # 조성: 조성기호 개수로 판단
    sharp_count = sum(1 for d in detections if d.class_name == "key_sig_sharp")
    flat_count  = sum(1 for d in detections if d.class_name == "key_sig_flat")
    if sharp_count > 0:
        key = accidentals_to_key(sharp_count, "sharp")
    elif flat_count > 0:
        key = accidentals_to_key(flat_count, "flat")
    else:
        key = "C major"

    # 박자: time_sig_num 검출 개수로 추정 (위=분자, 아래=분모)
    time_dets = sorted(
        [d for d in detections if d.class_name == "time_sig_num"],
        key=lambda d: d.bbox.y,
    )
    time_num, time_den = 4, 4
    if len(time_dets) >= 2:
        # 숫자 자체는 YOLOv8이 분류 — 여기선 개수만으로 4/4 추정
        time_num, time_den = 4, 4  # Task 5 학습 완료 후 실제 분류로 교체

    # 제목·빠르기: PaddleOCR (Task 8 이후 통합). 지금은 빈 문자열
    title = ""
    tempo_text = ""
    bpm: int | None = None

    return ScoreMeta(
        title=title,
        key=key,
        time_num=time_num,
        time_den=time_den,
        tempo_text=tempo_text,
        bpm=bpm,
    )
