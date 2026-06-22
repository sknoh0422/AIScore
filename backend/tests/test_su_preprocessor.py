import numpy as np
import pytest
from pathlib import Path
from PIL import Image
from app.stages.omr.preprocessor import preprocess


@pytest.fixture
def small_gray_png(tmp_path) -> Path:
    """100×80 px 회색조 PNG (저해상도 시뮬레이션)."""
    img = Image.fromarray(np.full((80, 100), 200, dtype=np.uint8), mode="L")
    p = tmp_path / "input.png"
    img.save(p)
    return p


def test_preprocess_creates_output(small_gray_png, tmp_path):
    dst = tmp_path / "out.png"
    result = preprocess(small_gray_png, dst)
    assert result == dst
    assert dst.exists()


def test_preprocess_upscales_short_edge(small_gray_png, tmp_path):
    """장변이 min_long_edge(기본 2000)보다 작으면 업스케일한다."""
    dst = tmp_path / "out.png"
    preprocess(small_gray_png, dst)
    out = Image.open(dst)
    assert max(out.size) >= 2000


def test_preprocess_output_is_grayscale(small_gray_png, tmp_path):
    dst = tmp_path / "out.png"
    preprocess(small_gray_png, dst)
    out = Image.open(dst)
    assert out.mode == "L"


def test_preprocess_large_image_not_downscaled(tmp_path):
    """이미 충분히 큰 이미지는 축소하지 않는다."""
    img = Image.fromarray(np.full((3000, 2200), 200, dtype=np.uint8), mode="L")
    src = tmp_path / "big.png"
    img.save(src)
    dst = tmp_path / "out.png"
    preprocess(src, dst)
    out = Image.open(dst)
    assert out.size == (2200, 3000)
