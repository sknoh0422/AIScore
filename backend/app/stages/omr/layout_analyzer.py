"""Module 1: 투영 프로파일 기반 레이아웃 분석 (찬송가 전용)."""
from __future__ import annotations

import cv2
import numpy as np

from app.stages.omr.types import BBox, LayoutResult, StaffSystem


# 보표선 검출에 필요한 최소 연속 흑색 픽셀 비율
_STAFF_LINE_FILL_RATIO = 0.4
# 보표 시스템 간 최소 간격 (픽셀)
_MIN_SYSTEM_GAP = 30


def analyze_layout(gray: np.ndarray) -> LayoutResult:
    """그레이스케일 이미지에서 보표/제목/가사 영역을 분리한다."""
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 수평 투영 프로파일: 각 행의 흑색 픽셀 수
    h_proj = np.sum(binary > 0, axis=1).astype(float) / w

    staff_line_ys = _detect_staff_lines(h_proj, threshold=_STAFF_LINE_FILL_RATIO)
    staff_systems = _group_into_systems(staff_line_ys, w)

    # 제목 영역: 첫 보표 시스템 위
    title_region: BBox | None = None
    if staff_systems:
        top_y = staff_systems[0].bbox.y
        if top_y > 20:
            title_region = BBox(x=0, y=0, w=w, h=top_y)

    # 빠르기표 영역: 첫 보표 시스템 바로 위 좁은 띠
    tempo_region: BBox | None = None
    if staff_systems and title_region and title_region.h > 40:
        tempo_region = BBox(x=0, y=title_region.h - 40, w=w // 2, h=40)

    # 가사 영역: 마지막 보표 시스템 아래
    lyric_regions: list[BBox] = []
    if staff_systems:
        last_sys = staff_systems[-1]
        lyric_top = last_sys.bbox.y2 + 5
        if lyric_top < h - 20:
            lyric_regions = [BBox(x=0, y=lyric_top, w=w, h=h - lyric_top)]

    return LayoutResult(
        image_h=h,
        image_w=w,
        title_region=title_region,
        tempo_region=tempo_region,
        staff_systems=staff_systems,
        lyric_regions=lyric_regions,
    )


def _detect_staff_lines(h_proj: np.ndarray, threshold: float) -> list[int]:
    """투영 프로파일에서 보표선 후보 y좌표 목록을 반환한다."""
    return [int(y) for y, v in enumerate(h_proj) if v >= threshold]


def _group_into_systems(line_ys: list[int], image_w: int) -> list[StaffSystem]:
    """연속된 보표선들을 5개씩 묶어 StaffSystem 목록을 반환한다."""
    if not line_ys:
        return []

    # 연속 그룹으로 클러스터링
    groups: list[list[int]] = []
    current = [line_ys[0]]
    for y in line_ys[1:]:
        if y - current[-1] <= 3:
            current.append(y)
        else:
            groups.append(current)
            current = [y]
    groups.append(current)

    # 각 그룹의 대표 y (중앙값)
    line_centers = [int(np.median(g)) for g in groups]

    # 5개씩 묶어 보표 시스템 구성
    systems: list[StaffSystem] = []
    i = 0
    staff_idx = 0
    while i + 4 < len(line_centers):
        five = line_centers[i:i + 5]
        spacing = (five[-1] - five[0]) / 4
        # 너무 불규칙하면 건너뜀 (보표선이 아닐 가능성)
        if spacing < 5 or spacing > 40:
            i += 1
            continue
        # 다음 그룹과 간격이 너무 좁으면 같은 시스템의 일부
        if i + 5 < len(line_centers) and line_centers[i + 5] - five[-1] < _MIN_SYSTEM_GAP:
            i += 1
            continue
        top_y = five[0] - int(spacing)
        bot_y = five[-1] + int(spacing)
        # SATB 찬송가: 짝수 보표(0,2,4,...)는 treble, 홀수(1,3,5,...)는 bass
        clef = "treble" if staff_idx % 2 == 0 else "bass"
        systems.append(StaffSystem(
            bbox=BBox(x=0, y=max(0, top_y), w=image_w, h=bot_y - top_y),
            line_ys=five,
            clef=clef,  # Task 5에서 YOLOv8 검출 후 교체
        ))
        staff_idx += 1
        i += 5

    return systems
