"""Module 2a: 보표선 검출 단위 테스트."""
import numpy as np
from app.stages.omr.staff_detector import refine_staff_lines


def _staff_image():
    img = np.full((100, 500), 255, dtype=np.uint8)
    for y in [20, 30, 40, 50, 60]:
        img[y, :] = 0
    return img


def test_refine_returns_five_lines():
    img = _staff_image()
    lines = refine_staff_lines(img, candidate_ys=[20, 30, 40, 50, 60])
    assert len(lines) == 5


def test_refine_preserves_order():
    img = _staff_image()
    lines = refine_staff_lines(img, candidate_ys=[20, 30, 40, 50, 60])
    assert lines == sorted(lines)


def test_refine_with_noise_candidates():
    """노이즈 후보가 섞여도 5개 핵심 선을 찾는다."""
    img = _staff_image()
    lines = refine_staff_lines(img, candidate_ys=[19, 20, 21, 30, 40, 50, 51, 60])
    assert len(lines) == 5
