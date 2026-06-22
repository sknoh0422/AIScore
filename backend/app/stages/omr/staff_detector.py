"""Module 2a: 보표선 y좌표 정밀화."""
from __future__ import annotations

import numpy as np


def refine_staff_lines(gray_crop: np.ndarray, candidate_ys: list[int]) -> list[int]:
    """후보 y좌표들을 클러스터링해 정확한 보표선 5개를 반환한다.

    Args:
        gray_crop: 그레이스케일 이미지 (보표 영역 크롭)
        candidate_ys: 보표선 후보 y좌표 목록 (정렬 불필요)

    Returns:
        정렬된 보표선 y좌표 5개 리스트. 후보가 5개 미만이면 있는 것만 반환.
    """
    if not candidate_ys:
        return []

    # 가까운 후보끼리 클러스터링 (거리 ≤ 3px)
    clusters: list[list[int]] = []
    current = [sorted(candidate_ys)[0]]
    for y in sorted(candidate_ys)[1:]:
        if y - current[-1] <= 3:
            current.append(y)
        else:
            clusters.append(current)
            current = [y]
    clusters.append(current)

    centers = [int(np.median(c)) for c in clusters]

    # 5개 미만이면 있는 것만 반환
    if len(centers) <= 5:
        return sorted(centers)

    # 5개보다 많으면 등간격 기준으로 최적 5개 선택
    best: list[int] = centers[:5]
    best_score = _regularity_score(best)
    for i in range(len(centers) - 4):
        candidate = centers[i : i + 5]
        score = _regularity_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score
    return sorted(best)


def _regularity_score(ys: list[int]) -> float:
    """등간격일수록 낮은 점수(분산)를 반환한다."""
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    return float(np.var(gaps))
