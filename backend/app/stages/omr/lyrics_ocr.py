"""Module 4: PaddleOCR 기반 한글 가사 추출."""
from __future__ import annotations
import re
import numpy as np
from functools import lru_cache

from app.core.config import paddleocr_lang
from app.stages.omr.types import BBox, LyricsResult

_PUNCT_RE = re.compile(r"[\s,\.\-\(\)\[\]·~]+")


@lru_cache(maxsize=1)
def _get_ocr_engine():
    """PaddleOCR 엔진을 싱글톤으로 로드한다 (첫 호출 시 모델 다운로드)."""
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR(use_angle_cls=False, lang=paddleocr_lang(), show_log=False)
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "paddleocr 패키지가 필요합니다: pip install paddleocr paddlepaddle"
        ) from e


def extract_lyrics(gray: np.ndarray, regions: list[BBox]) -> LyricsResult:
    """가사 영역에서 절별 가사를 추출한다.

    각 BBox가 1절에 해당한다고 가정한다.
    반환된 LyricsResult.verses[i]는 i번째 절의 음절 목록이다.
    """
    if not regions:
        return LyricsResult(verses=[])

    ocr = _get_ocr_engine()
    verses: list[list[str]] = []
    h, w = gray.shape

    for region in regions:
        y1 = max(0, region.y)
        y2 = min(h, region.y2)
        x1 = max(0, region.x)
        x2 = min(w, region.x2)
        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            verses.append([])
            continue
        results = ocr(crop)
        text = " ".join(r[1][0] for r in results[0]) if results and results[0] else ""
        verses.append(split_syllables(text))

    return LyricsResult(verses=verses)


def split_syllables(text: str) -> list[str]:
    """한국어 텍스트를 음절(글자) 단위로 분리한다. 구두점·공백 제거."""
    cleaned = _PUNCT_RE.sub("", text)
    return list(cleaned)
