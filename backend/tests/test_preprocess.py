from PIL import Image
from app.stages.omr.preprocess import ensure_resolution


def _img(tmp_path, w, h):
    p = tmp_path / "in.png"
    Image.new("RGB", (w, h), "white").save(p)
    return p


def test_upscales_small_image(tmp_path):
    src = _img(tmp_path, 500, 777)
    out = ensure_resolution(src, tmp_path / "out.png", min_long_edge=2000)
    w, h = Image.open(out).size
    assert max(w, h) >= 2000
    assert h > w  # 비율 유지


def test_keeps_large_image_dims(tmp_path):
    src = _img(tmp_path, 1600, 2400)
    out = ensure_resolution(src, tmp_path / "out.png", min_long_edge=2000)
    assert max(Image.open(out).size) == 2400
