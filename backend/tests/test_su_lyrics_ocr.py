import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from app.stages.omr.types import BBox, LyricsResult
from app.stages.omr.lyrics_ocr import extract_lyrics, split_syllables

def test_split_syllables_korean():
    """한국어 음절을 하나씩 분리한다."""
    result = split_syllables("주님의크신사랑")
    assert result == ["주", "님", "의", "크", "신", "사", "랑"]

def test_split_syllables_mixed():
    """공백·구두점 제거 후 음절만 반환한다."""
    result = split_syllables("주 님의, 사랑")
    assert result == ["주", "님", "의", "사", "랑"]

def test_extract_lyrics_empty_regions():
    gray = np.full((800, 600), 230, dtype=np.uint8)
    result = extract_lyrics(gray, [])
    assert result.verse_count == 0

def test_extract_lyrics_returns_lyrics_result():
    gray = np.full((800, 600), 230, dtype=np.uint8)
    regions = [BBox(0, 500, 600, 50), BBox(0, 560, 600, 50)]
    mock_ocr = MagicMock()
    mock_ocr.return_value = [[("주님의 사랑", 0.95)]]
    with patch("app.stages.omr.lyrics_ocr._get_ocr_engine", return_value=mock_ocr):
        result = extract_lyrics(gray, regions)
    assert isinstance(result, LyricsResult)
