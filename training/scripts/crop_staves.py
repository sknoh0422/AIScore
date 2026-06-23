"""악보 이미지 → 시스템(보표 그룹) 단위 경계 탐지 + 크롭."""
from __future__ import annotations

import numpy as np
from pathlib import Path
from PIL import Image


def find_system_boundaries(
    img_path: Path,
    min_gap: int = 15,
    thresh_ratio: float = 0.04,
) -> list[tuple[int, int]]:
    """이미지에서 각 시스템(보표 그룹)의 (y_start, y_end) 목록을 반환.

    Args:
        img_path: 악보 PNG 경로.
        min_gap: 시스템 구분으로 인정할 최소 공백 픽셀 수.
        thresh_ratio: row 픽셀 밀도 최대값 대비 공백 판정 비율.

    Returns:
        [(y_start, y_end), ...] — 이미지 상단부터 순서대로.
    """
    img = np.array(Image.open(img_path).convert("L"))
    dark = (img < 200).astype(np.float32)
    row_density = dark.sum(axis=1)

    # 20px 이동 평균으로 보표 선 잔물결 제거
    kernel = np.ones(20) / 20
    smoothed = np.convolve(row_density, kernel, mode="same")

    threshold = smoothed.max() * thresh_ratio
    is_gap = smoothed < threshold
    h = img.shape[0]

    # min_gap 픽셀 이상인 공백 구간 수집
    gaps: list[tuple[int, int]] = []
    in_gap, gap_start = bool(is_gap[0]), 0
    for i in range(1, h):
        cur = bool(is_gap[i])
        if cur != in_gap:
            if in_gap and (i - gap_start) >= min_gap:
                gaps.append((gap_start, i))
            in_gap, gap_start = cur, i
    if in_gap and (h - gap_start) >= min_gap:
        gaps.append((gap_start, h))

    # 공백 중점을 시스템 경계로 사용
    boundaries: list[tuple[int, int]] = []
    prev = 0
    for gs, ge in gaps:
        mid = (gs + ge) // 2
        if mid > 30:  # 상단 여백 무시
            boundaries.append((prev, mid))
            prev = mid
    boundaries.append((prev, h))

    # 전체 높이의 1/15 미만인 구간 제거
    min_height = max(h // 15, 1)
    return [(s, e) for s, e in boundaries if (e - s) > min_height]


def crop_system(
    img_path: Path,
    y_start: int,
    y_end: int,
    padding: int = 5,
) -> Image.Image:
    """이미지에서 (y_start, y_end) 구간을 크롭하여 반환."""
    img = Image.open(img_path).convert("RGB")
    y0 = max(0, y_start - padding)
    y1 = min(img.height, y_end + padding)
    return img.crop((0, y0, img.width, y1))
