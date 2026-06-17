"""OMR 전처리: 저해상도 업스케일 + 그레이스케일. (저해상도가 OMR 실패 근본원인)"""
from __future__ import annotations
from pathlib import Path
from PIL import Image


def ensure_resolution(src: Path, dst: Path, min_long_edge: int = 2000) -> Path:
    im = Image.open(src).convert("L")
    w, h = im.size
    long_edge = max(w, h)
    if long_edge < min_long_edge:
        scale = min_long_edge / long_edge
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    im.save(dst)
    return dst
