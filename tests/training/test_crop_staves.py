"""crop_staves 모듈 단위 테스트."""
from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from training.scripts.crop_staves import find_system_boundaries, crop_system


def _make_hymn_image(num_systems: int = 2, width: int = 800) -> Image.Image:
    """시스템이 num_systems개인 가짜 악보 이미지 생성.

    실제 악보처럼 시스템 영역 전체에 잉크가 분포하도록:
    - 보표 5선을 sys_h 전체에 균등 배치
    - 음표 머리 역할의 작은 점을 보표 위에 추가
    """
    sys_h = 200
    gap_h = 40
    margin = 8
    total_h = margin + num_systems * sys_h + (num_systems - 1) * gap_h + margin
    img = Image.new("L", (width, total_h), color=255)
    draw = ImageDraw.Draw(img)
    y = margin
    staff_spacing = sys_h // 4  # 4성부를 sys_h 전체에 균등 배분
    for _ in range(num_systems):
        for staff in range(4):
            base = y + staff * staff_spacing
            # 보표 5선
            for line in range(5):
                lx = base + line * 4
                draw.line([(0, lx), (width - 1, lx)], fill=0, width=1)
            # 음표 머리 (잉크를 sys_h 전체에 분포시킴)
            for x in range(30, width, 60):
                draw.ellipse([x - 3, base + 8, x + 3, base + 14], fill=0)
        y += sys_h + gap_h
    return img


def _save_tmp(img: Image.Image, tmp_path: Path, name: str = "test.png") -> Path:
    p = tmp_path / name
    img.save(p)
    return p


# ── find_system_boundaries ──────────────────────────────────────────────────

def test_returns_at_least_one_system(tmp_path):
    p = _save_tmp(_make_hymn_image(1), tmp_path)
    result = find_system_boundaries(p)
    assert len(result) >= 1


def test_two_system_image_detects_two(tmp_path):
    p = _save_tmp(_make_hymn_image(2), tmp_path)
    result = find_system_boundaries(p)
    assert len(result) == 2


def test_three_system_image_detects_three(tmp_path):
    p = _save_tmp(_make_hymn_image(3), tmp_path)
    result = find_system_boundaries(p)
    assert len(result) == 3


def test_boundaries_cover_image_height(tmp_path):
    img = _make_hymn_image(2)
    p = _save_tmp(img, tmp_path)
    result = find_system_boundaries(p)
    assert result[0][0] == 0 or result[0][0] < 50      # 상단 가까이 시작
    assert result[-1][1] >= img.height - 50             # 하단 가까이 끝


def test_boundaries_nonoverlapping_sorted(tmp_path):
    p = _save_tmp(_make_hymn_image(3), tmp_path)
    result = find_system_boundaries(p)
    for i in range(len(result) - 1):
        assert result[i][1] <= result[i + 1][0]


def test_each_boundary_has_positive_height(tmp_path):
    p = _save_tmp(_make_hymn_image(2), tmp_path)
    for y0, y1 in find_system_boundaries(p):
        assert y1 > y0


# ── crop_system ─────────────────────────────────────────────────────────────

def test_crop_returns_pil_image(tmp_path):
    img = _make_hymn_image(2)
    p = _save_tmp(img, tmp_path)
    boundaries = find_system_boundaries(p)
    y0, y1 = boundaries[0]
    cropped = crop_system(p, y0, y1)
    assert isinstance(cropped, Image.Image)


def test_crop_width_equals_original(tmp_path):
    img = _make_hymn_image(2, width=800)
    p = _save_tmp(img, tmp_path)
    y0, y1 = find_system_boundaries(p)[0]
    cropped = crop_system(p, y0, y1)
    assert cropped.width == 800


def test_crop_height_less_than_original(tmp_path):
    img = _make_hymn_image(2)
    p = _save_tmp(img, tmp_path)
    y0, y1 = find_system_boundaries(p)[0]
    cropped = crop_system(p, y0, y1)
    assert cropped.height < img.height
