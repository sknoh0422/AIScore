"""Module 0: 이미지 전처리 — DPI 정규화 + 기울기 보정."""
from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.stages.omr.preprocess import ensure_resolution


def preprocess(src: Path, dst: Path, min_long_edge: int = 2000) -> Path:
    """악보 이미지를 전처리해 dst에 저장하고 dst를 반환한다.

    1. 업스케일 (장변 < min_long_edge 시)
    2. 그레이스케일 유지
    3. 기울기 보정 (±10° 이내)
    """
    # Step 1: 해상도 정규화 (기존 preprocess.py 재사용)
    ensure_resolution(src, dst, min_long_edge=min_long_edge)

    # Step 2: 기울기 보정
    img = cv2.imread(str(dst), cv2.IMREAD_GRAYSCALE)
    img = _deskew(img)
    cv2.imwrite(str(dst), img)
    return dst


def _deskew(gray: np.ndarray) -> np.ndarray:
    """수평 투영 프로파일로 기울기(±10°)를 감지해 보정한다."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5 or abs(angle) > 10:
        return gray
    h, w = gray.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)
